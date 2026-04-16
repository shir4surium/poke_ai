"""
Phase 4: WorldModel (TransitionModel) 学習器

パース済みリプレイから連続ターン対 (s_t, a_t, s_{t+1}, done, reward) を生成し、
TransitionModel を学習する。

TransitionModel が学習するもの:
  - 次状態予測:  MSE(predicted_next_state, actual_next_state)
  - 終了判定:    BCE(predicted_done, actual_done)
  - 即時報酬:    MSE(predicted_reward, actual_reward)
      reward = +1.0 (p1 勝利), -1.0 (p1 敗北), 0.0 (継続中)

実行:
  python ai/world_model_trainer.py --epochs 30 --batch_size 128
"""

from __future__ import annotations
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Optional
from collections import Counter

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, random_split

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "db"))
sys.path.insert(0, str(ROOT / "ai"))

from featurizer import BattleFeaturizer
from game_state import BattleState, PlayerState, PokemonStatus, StatusCondition
from world_model import TransitionModel
from action_classifier import (
    ActionClassifier, ActionCategory,
    NUM_ACTION_CATEGORIES, CATEGORY_LABELS, prefetch_moves,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PARSED_DIR = ROOT / "data" / "parsed"
MODELS_DIR = ROOT / "ai" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


# ===== BattleState 簡易構築（trainer.py と共通ロジック） =====

def _make_poke(name: str, hp_ratio: float, status_str: Optional[str]) -> PokemonStatus:
    sc = StatusCondition.NONE
    if status_str:
        sc = StatusCondition.from_showdown(status_str)
    return PokemonStatus(
        name_jp=name, name_en=name,
        current_hp=int(hp_ratio * 100), max_hp=100,
        status=sc,
    )


def _build_state(
    active_p1: str, active_p2: str,
    bench_p1: list[str], bench_p2: list[str],
    hp_map: dict, turn_num: int,
) -> BattleState:
    def make_player(pid, active, bench):
        hp = hp_map.get(f"{pid}:{active}", {})
        ratio  = hp.get("hp_percent", 1.0) if isinstance(hp, dict) else 1.0
        status = hp.get("status")           if isinstance(hp, dict) else None
        poke   = _make_poke(active, ratio, status)
        selected = [poke]
        for b in bench[:2]:
            bh = hp_map.get(f"{pid}:{b}", {})
            br = bh.get("hp_percent", 1.0) if isinstance(bh, dict) else 1.0
            bs = bh.get("status")          if isinstance(bh, dict) else None
            selected.append(_make_poke(b, br, bs))
        ps = PlayerState(player_id=pid, player_name=pid)
        ps.selected      = selected
        ps.active_index  = 0
        return ps

    p1 = make_player("p1", active_p1, bench_p1)
    p2 = make_player("p2", active_p2, bench_p2)
    return BattleState(turn=turn_num, p1=p1, p2=p2)


# ===== リプレイ → 遷移サンプル =====

def replay_to_transitions(
    record: dict,
    featurizer: BattleFeaturizer,
    classifier: ActionClassifier,
) -> list[dict]:
    """
    BattleRecord から (state_t, action_cat, state_{t+1}, done, reward) を生成。

    reward:
      継続中 = 0.0
      最終ターン → p1 勝利 = +1.0, p1 敗北 = -1.0
    """
    winner  = record.get("winner")
    final_reward = 1.0 if winner == "p1" else (-1.0 if winner == "p2" else 0.0)

    turns = record.get("turns", [])
    if len(turns) < 2:
        return []

    # 蓄積マップ
    hp_map:      dict[str, dict]     = {}
    move_history: dict[str, list[str]] = {}
    bench_seen:  dict[str, list[str]] = {"p1": [], "p2": []}

    # (turn_idx, state_vec, action_cat) を先に構築
    turn_states: list[tuple[int, np.ndarray, int]] = []

    for turn_rec in turns:
        for key, pstate in turn_rec.get("hp_snapshot", {}).items():
            hp_map[key] = pstate
            if ":" in key:
                slot, pname = key.split(":", 1)
                if slot in bench_seen and pname not in bench_seen[slot]:
                    bench_seen[slot].append(pname)

        active_p1 = turn_rec.get("active", {}).get("p1", "")
        active_p2 = turn_rec.get("active", {}).get("p2", "")
        if not active_p1 or not active_p2:
            continue

        # move_history 更新
        for act in turn_rec.get("actions", []):
            slot = act.get("player", "")
            if act.get("action_type") == "move":
                pname = turn_rec.get("active", {}).get(slot, "")
                mname = act.get("move_name", "")
                if pname and mname:
                    mk = f"{slot}:{pname}"
                    h  = move_history.setdefault(mk, [])
                    if mname not in h:
                        h.append(mname)

        # p1 行動カテゴリ
        p1_act = next(
            (a for a in turn_rec.get("actions", []) if a.get("player") == "p1"),
            None,
        )
        if p1_act is None:
            continue

        act_type = p1_act.get("action_type", "")
        if act_type == "move":
            move_name = p1_act.get("move_name", "")
            if not move_name:
                continue
            is_mega = any(
                e.get("type") == "mega" and e.get("player") == "p1"
                for e in turn_rec.get("events", [])
            )
            action_cat = classifier.classify_move(move_name, active_p1, active_p2, is_mega)
        elif act_type == "switch":
            incoming = p1_act.get("switch_to", "")
            if not incoming:
                continue
            action_cat = classifier.classify_switch(active_p1, incoming, active_p2)
        else:
            continue

        bench_p1 = [p for p in bench_seen["p1"] if p != active_p1]
        bench_p2 = [p for p in bench_seen["p2"] if p != active_p2]

        state = _build_state(
            active_p1, active_p2, bench_p1, bench_p2,
            dict(hp_map), turn_rec.get("turn_number", 0),
        )
        try:
            state_vec = featurizer.encode(state)
        except Exception:
            continue

        turn_states.append((turn_rec.get("turn_number", 0), state_vec, action_cat))

    if len(turn_states) < 2:
        return []

    # 連続ターン対を生成
    transitions = []
    for i in range(len(turn_states) - 1):
        _, s_t,  a_t  = turn_states[i]
        _, s_t1, _    = turn_states[i + 1]
        is_last = (i == len(turn_states) - 2)
        done    = 1.0 if is_last else 0.0
        reward  = final_reward if is_last else 0.0

        transitions.append({
            "state":      s_t,
            "action_cat": a_t,
            "next_state": s_t1,
            "done":       done,
            "reward":     reward,
        })

    return transitions


# ===== Dataset =====

class TransitionDataset(Dataset):
    """
    WorldModel 学習用の (s, a, s', done, r) データセット。
    """

    def __init__(
        self,
        jsonl_paths:  list[Path],
        max_records:  Optional[int] = None,
        prefetch:     bool = True,
    ):
        self.featurizer  = BattleFeaturizer()
        self.classifier  = ActionClassifier()
        self.samples:    list[dict] = []

        if prefetch and jsonl_paths:
            self._prefetch_moves(jsonl_paths)

        loaded = 0
        for path in jsonl_paths:
            if not path.exists():
                logger.warning(f"ファイルが存在しません: {path}")
                continue
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self.samples.extend(
                        replay_to_transitions(record, self.featurizer, self.classifier)
                    )
                    loaded += 1
                    if max_records and loaded >= max_records:
                        break
            if max_records and loaded >= max_records:
                break

        logger.info(f"遷移サンプル数: {len(self.samples)} (試合数: {loaded})")
        self._log_distribution()

    def _prefetch_moves(self, jsonl_paths: list[Path]) -> None:
        move_names: set[str] = set()
        for path in jsonl_paths:
            if not path.exists():
                continue
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                    except Exception:
                        continue
                    for turn in record.get("turns", []):
                        for act in turn.get("actions", []):
                            if act.get("action_type") == "move" and act.get("move_name"):
                                move_names.add(act["move_name"])
        if move_names:
            logger.info(f"技をキャッシュ確認中 ({len(move_names)} 種類)...")
            prefetch_moves(list(move_names), self.classifier)

    def _log_distribution(self) -> None:
        cnt   = Counter(s["action_cat"] for s in self.samples)
        total = len(self.samples) or 1
        done_cnt = sum(1 for s in self.samples if s["done"] > 0.5)
        logger.info(f"終了ターン: {done_cnt} ({done_cnt/total*100:.1f}%)")
        logger.info("行動カテゴリ分布:")
        for cat in sorted(cnt):
            label = CATEGORY_LABELS.get(cat, str(cat))
            logger.info(f"  [{cat:2d}] {label:<16}: {cnt[cat]:5d} ({cnt[cat]/total*100:5.1f}%)")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple:
        s = self.samples[idx]
        return (
            torch.from_numpy(s["state"]).float(),
            torch.tensor(s["action_cat"], dtype=torch.long),
            torch.from_numpy(s["next_state"]).float(),
            torch.tensor([[s["done"]]],   dtype=torch.float32),
            torch.tensor([[s["reward"]]], dtype=torch.float32),
        )


# ===== トレーナー =====

class WorldModelTrainer:
    """
    TransitionModel の学習トレーナー。
    損失: λ1*MSE(s') + λ2*BCE(done) + λ3*MSE(reward)
    """

    def __init__(
        self,
        model:        TransitionModel,
        device:       str   = "cpu",
        lr:           float = 1e-3,
        weight_decay: float = 1e-4,
    ):
        self.model     = model.to(device)
        self.device    = device
        self.optimizer = torch.optim.AdamW(
            model.parameters(), lr=lr, weight_decay=weight_decay
        )
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=100, eta_min=1e-5
        )

    def _step(self, batch, train: bool) -> dict[str, float]:
        state_t, action_t, next_state_t, done_t, reward_t = [
            t.to(self.device) for t in batch
        ]
        # done_t, reward_t は (B,1,1) → squeeze して (B,1)
        done_t   = done_t.squeeze(1)
        reward_t = reward_t.squeeze(1)

        with torch.set_grad_enabled(train):
            total_loss, breakdown = self.model.loss(
                state_t, action_t, next_state_t, done_t, reward_t
            )

        if train:
            self.optimizer.zero_grad()
            total_loss.backward()
            nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            self.optimizer.step()

        return {k: v for k, v in breakdown.items()}

    def _run_epoch(self, loader: DataLoader, train: bool) -> dict[str, float]:
        self.model.train(train)
        totals: dict[str, float] = {}
        for batch in loader:
            for k, v in self._step(batch, train).items():
                totals[k] = totals.get(k, 0.0) + v
        n = max(len(loader), 1)
        return {k: v / n for k, v in totals.items()}

    def fit(
        self,
        dataset:    TransitionDataset,
        epochs:     int   = 30,
        batch_size: int   = 128,
        val_ratio:  float = 0.1,
        save_best:  bool  = True,
    ) -> None:
        val_size   = max(1, int(len(dataset) * val_ratio))
        train_size = len(dataset) - val_size
        train_ds, val_ds = random_split(dataset, [train_size, val_size])

        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,  num_workers=0)
        val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False, num_workers=0)

        best_val_loss = float("inf")
        for epoch in range(1, epochs + 1):
            tr  = self._run_epoch(train_loader, train=True)
            val = self._run_epoch(val_loader,   train=False)
            self.scheduler.step()

            logger.info(
                f"Epoch {epoch:3d}/{epochs} | "
                f"train total={tr['total']:.4f} "
                f"(state={tr['state']:.4f} done={tr['done']:.4f} r={tr['reward']:.4f}) | "
                f"val total={val['total']:.4f}"
            )

            if save_best and val["total"] < best_val_loss:
                best_val_loss = val["total"]
                path = MODELS_DIR / "world_model_best.pt"
                torch.save(self.model.state_dict(), path)
                logger.info(f"  -> best WorldModel 保存: {path}")

        path = MODELS_DIR / "world_model_last.pt"
        torch.save(self.model.state_dict(), path)
        logger.info(f"最終 WorldModel 保存: {path}")


# ===== エントリポイント =====

def main():
    parser = argparse.ArgumentParser(description="WorldModel 学習")
    parser.add_argument("--epochs",      type=int,   default=30)
    parser.add_argument("--batch_size",  type=int,   default=128)
    parser.add_argument("--lr",          type=float, default=1e-3)
    parser.add_argument("--max_records", type=int,   default=None)
    parser.add_argument("--device",      type=str,   default="cpu")
    parser.add_argument("--no_prefetch", action="store_true")
    args = parser.parse_args()

    jsonl_paths = list(PARSED_DIR.glob("*.jsonl"))
    if not jsonl_paths:
        logger.error(f"パース済みデータが見つかりません: {PARSED_DIR}")
        return

    logger.info(f"データファイル: {[p.name for p in jsonl_paths]}")
    dataset = TransitionDataset(
        jsonl_paths,
        max_records=args.max_records,
        prefetch=not args.no_prefetch,
    )

    if len(dataset) == 0:
        logger.error("有効な遷移サンプルがありません。")
        return

    model   = TransitionModel()
    trainer = WorldModelTrainer(model, device=args.device, lr=args.lr)
    trainer.fit(dataset, epochs=args.epochs, batch_size=args.batch_size)


if __name__ == "__main__":
    main()

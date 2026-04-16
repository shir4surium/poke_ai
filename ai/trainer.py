"""
Phase 3-D: 模倣学習トレーナー (ActionClassifier 対応版)

Showdown パーサーが出力した JSONL から
(状態ベクトル, ActionCategory, 勝敗ラベル) のデータセットを構築し、
PolicyValueNetwork を模倣学習で事前訓練する。

行動分類ロジック:
  技   → ActionClassifier.classify_move(技名, 使用者名, 相手名, is_mega)
  交代 → ActionClassifier.classify_switch(現在者名, 交代先名, 相手名)

損失:
  L = CE(policy, expert_action_category) + λ * MSE(value, outcome)

実行:
  python ai/trainer.py --epochs 30 --batch_size 128
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
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, random_split

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "db"))
sys.path.insert(0, str(ROOT / "ai"))

from featurizer import BattleFeaturizer, MAX_ACTIONS
from game_state import (
    BattleState, PlayerState, PokemonStatus,
    StatusCondition,
)
from network import PolicyValueNetwork, save_checkpoint, load_checkpoint
from action_classifier import (
    ActionClassifier, ActionCategory, NUM_ACTION_CATEGORIES,
    CATEGORY_LABELS, prefetch_moves, prefetch_pokemon,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PARSED_DIR = ROOT / "data" / "parsed"
MODELS_DIR = ROOT / "ai" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

LAMBDA_VALUE = 0.5


# ===== BattleState 簡易構築 =====

def _make_poke(name: str, hp_ratio: float, status_str: Optional[str]) -> PokemonStatus:
    sc = StatusCondition.NONE
    if status_str:
        sc = StatusCondition.from_showdown(status_str)
    return PokemonStatus(
        name_jp=name, name_en=name,
        current_hp=int(hp_ratio * 100), max_hp=100,
        status=sc,
    )


def _make_player(player_id: str, active_name: str,
                 hp_map: dict, bench_names: list[str]) -> PlayerState:
    hp_info = hp_map.get(f"{player_id}:{active_name}", {})
    hp_ratio  = hp_info.get("hp_percent", 1.0) if isinstance(hp_info, dict) else 1.0
    status    = hp_info.get("status")          if isinstance(hp_info, dict) else None

    active_poke = _make_poke(active_name, hp_ratio, status)
    selected = [active_poke]

    for bname in bench_names[:2]:
        binfo = hp_map.get(f"{player_id}:{bname}", {})
        brat  = binfo.get("hp_percent", 1.0) if isinstance(binfo, dict) else 1.0
        bstat = binfo.get("status")          if isinstance(binfo, dict) else None
        selected.append(_make_poke(bname, brat, bstat))

    ps = PlayerState(player_id=player_id, player_name=player_id)
    ps.selected = selected
    ps.active_index = 0
    return ps


# ===== リプレイ → サンプル =====

def replay_to_samples(
    record: dict,
    featurizer: BattleFeaturizer,
    classifier: ActionClassifier,
) -> list[dict]:
    """
    BattleRecord (dict) から (state_vec, action_category, outcome) のリストを生成。

    outcome: +1.0 = p1 勝利, -1.0 = p1 敗北, 0.0 = 不明
    """
    winner  = record.get("winner")
    outcome = 1.0 if winner == "p1" else (-1.0 if winner == "p2" else 0.0)

    samples: list[dict] = []
    turns = record.get("turns", [])

    # 蓄積マップ
    hp_map: dict[str, dict]     = {}   # "slot:poke_name" → hp_snapshot dict
    move_history: dict[str, list[str]] = {}  # "slot:poke_name" → 使用技リスト(順)
    bench_seen: dict[str, list[str]]   = {"p1": [], "p2": []}  # 登場ポケモン順

    for turn_rec in turns:
        # hp_snapshot 蓄積
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

        # 全アクションで move_history を更新
        for act in turn_rec.get("actions", []):
            slot = act.get("player", "")
            if act.get("action_type") == "move":
                pname = turn_rec.get("active", {}).get(slot, "")
                mname = act.get("move_name", "")
                if pname and mname:
                    mk = f"{slot}:{pname}"
                    history = move_history.setdefault(mk, [])
                    if mname not in history:
                        history.append(mname)

        # p1 の行動を抽出
        p1_action = next(
            (a for a in turn_rec.get("actions", []) if a.get("player") == "p1"),
            None,
        )
        if p1_action is None:
            continue

        act_type = p1_action.get("action_type", "")

        # ── 行動カテゴリ分類 ──
        if act_type == "move":
            move_name = p1_action.get("move_name", "")
            if not move_name:
                continue
            is_mega = any(
                e.get("type") == "mega" and e.get("player") == "p1"
                for e in turn_rec.get("events", [])
            )
            action_cat = classifier.classify_move(
                move_name, active_p1, active_p2, is_mega=is_mega
            )

        elif act_type == "switch":
            incoming = p1_action.get("switch_to", "")
            if not incoming:
                continue
            action_cat = classifier.classify_switch(active_p1, incoming, active_p2)

        else:
            continue

        # ── BattleState 構築 ──
        bench_p1 = [p for p in bench_seen["p1"] if p != active_p1]
        bench_p2 = [p for p in bench_seen["p2"] if p != active_p2]

        p1 = _make_player("p1", active_p1, hp_map, bench_p1)
        p2 = _make_player("p2", active_p2, hp_map, bench_p2)
        state = BattleState(turn=turn_rec.get("turn_number", 0), p1=p1, p2=p2)

        try:
            state_vec = featurizer.encode(state)
        except Exception:
            continue

        samples.append({
            "state_vec":  state_vec,
            "action_cat": action_cat,
            "outcome":    outcome,
        })

    return samples


# ===== Dataset =====

class ImitationDataset(Dataset):
    """
    JSONL パース済みファイルを読み込み模倣学習用データセットを構築。
    """

    def __init__(
        self,
        jsonl_paths: list[Path],
        max_records: Optional[int] = None,
        prefetch: bool = True,
    ):
        self.featurizer = BattleFeaturizer()
        self.classifier = ActionClassifier()
        self.samples: list[dict] = []

        # 使用技を事前フェッチ
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
                        replay_to_samples(record, self.featurizer, self.classifier)
                    )
                    loaded += 1
                    if max_records and loaded >= max_records:
                        break
            if max_records and loaded >= max_records:
                break

        logger.info(f"サンプル数: {len(self.samples)} (試合数: {loaded})")
        self._log_distribution()

    def _prefetch_moves(self, jsonl_paths: list[Path]) -> None:
        """使用される技名・ポケモン名を先にまとめてフェッチ"""
        move_names:  set[str] = set()
        poke_names:  set[str] = set()
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
                        active = turn.get("active", {})
                        for pname in active.values():
                            if pname:
                                poke_names.add(pname)
                        for key in turn.get("hp_snapshot", {}):
                            if ":" in key:
                                poke_names.add(key.split(":", 1)[1])

        if move_names:
            logger.info(f"技をフェッチ中 ({len(move_names)} 種類)...")
            prefetch_moves(list(move_names), self.classifier)
        if poke_names:
            logger.info(f"ポケモンタイプをフェッチ中 ({len(poke_names)} 種類)...")
            prefetch_pokemon(list(poke_names), self.classifier)

    def _log_distribution(self) -> None:
        cnt = Counter(s["action_cat"] for s in self.samples)
        total = len(self.samples) or 1
        logger.info("行動カテゴリ分布:")
        for cat in sorted(cnt):
            label = CATEGORY_LABELS.get(cat, str(cat))
            logger.info(f"  [{cat:2d}] {label:<16}: {cnt[cat]:5d} ({cnt[cat]/total*100:5.1f}%)")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        s = self.samples[idx]
        return (
            torch.from_numpy(s["state_vec"]).float(),
            torch.tensor(s["action_cat"], dtype=torch.long),
            torch.tensor(s["outcome"],    dtype=torch.float32),
        )


# ===== トレーナー =====

class ImitationTrainer:
    def __init__(
        self,
        net: PolicyValueNetwork,
        device: str = "cpu",
        lr: float = 1e-3,
        weight_decay: float = 1e-4,
    ):
        self.net = net.to(device)
        self.device = device
        self.optimizer = torch.optim.AdamW(
            net.parameters(), lr=lr, weight_decay=weight_decay
        )
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=100, eta_min=1e-5
        )

    def _step(self, batch, train: bool) -> dict[str, float]:
        state_t, action_t, outcome_t = [t.to(self.device) for t in batch]
        outcome_t = outcome_t.unsqueeze(1)

        with torch.set_grad_enabled(train):
            log_policy, value = self.net(state_t)
            loss_policy = F.nll_loss(log_policy, action_t)
            loss_value  = F.mse_loss(value, outcome_t)
            loss = loss_policy + LAMBDA_VALUE * loss_value

        if train:
            self.optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.net.parameters(), 1.0)
            self.optimizer.step()

        acc = (log_policy.argmax(dim=-1) == action_t).float().mean().item()
        return {
            "loss": loss.item(), "loss_policy": loss_policy.item(),
            "loss_value": loss_value.item(), "accuracy": acc,
        }

    def train_epoch(self, loader: DataLoader) -> dict[str, float]:
        self.net.train()
        totals: dict[str, float] = {}
        for batch in loader:
            for k, v in self._step(batch, True).items():
                totals[k] = totals.get(k, 0.0) + v
        n = len(loader)
        return {k: v / n for k, v in totals.items()}

    def eval_epoch(self, loader: DataLoader) -> dict[str, float]:
        self.net.eval()
        totals: dict[str, float] = {}
        for batch in loader:
            for k, v in self._step(batch, False).items():
                totals[k] = totals.get(k, 0.0) + v
        n = len(loader)
        return {k: v / n for k, v in totals.items()}

    def fit(
        self,
        dataset: ImitationDataset,
        epochs: int = 30,
        batch_size: int = 128,
        val_ratio: float = 0.1,
        save_best: bool = True,
    ) -> None:
        val_size   = max(1, int(len(dataset) * val_ratio))
        train_size = len(dataset) - val_size
        train_ds, val_ds = random_split(dataset, [train_size, val_size])

        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,  num_workers=0)
        val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False, num_workers=0)

        best_val_loss = float("inf")
        for epoch in range(1, epochs + 1):
            tr  = self.train_epoch(train_loader)
            val = self.eval_epoch(val_loader)
            self.scheduler.step()

            logger.info(
                f"Epoch {epoch:3d}/{epochs} | "
                f"train loss={tr['loss']:.4f} acc={tr['accuracy']:.3f} | "
                f"val loss={val['loss']:.4f} acc={val['accuracy']:.3f}"
            )

            if save_best and val["loss"] < best_val_loss:
                best_val_loss = val["loss"]
                path = MODELS_DIR / "policy_value_best.pt"
                save_checkpoint(self.net, self.optimizer, epoch, val["loss"], path)
                logger.info(f"  → best モデル保存: {path}")

        path = MODELS_DIR / "policy_value_last.pt"
        save_checkpoint(self.net, self.optimizer, epochs, val["loss"], path)
        logger.info(f"最終モデル保存: {path}")


# ===== エントリポイント =====

def main():
    parser = argparse.ArgumentParser(description="Champions AI 模倣学習")
    parser.add_argument("--epochs",      type=int,   default=30)
    parser.add_argument("--batch_size",  type=int,   default=128)
    parser.add_argument("--lr",          type=float, default=3e-4)
    parser.add_argument("--max_records", type=int,   default=None)
    parser.add_argument("--checkpoint",  type=str,   default=None)
    parser.add_argument("--device",      type=str,   default="cpu")
    parser.add_argument("--no_prefetch", action="store_true")
    args = parser.parse_args()

    jsonl_paths = list(PARSED_DIR.glob("*.jsonl"))
    if not jsonl_paths:
        logger.error(f"パース済みデータが見つかりません: {PARSED_DIR}")
        return

    logger.info(f"データファイル: {[p.name for p in jsonl_paths]}")
    dataset = ImitationDataset(
        jsonl_paths,
        max_records=args.max_records,
        prefetch=not args.no_prefetch,
    )

    if len(dataset) == 0:
        logger.error("有効なサンプルがありません。")
        return

    net = PolicyValueNetwork()
    if args.checkpoint:
        epoch, loss = load_checkpoint(net, None, args.checkpoint, args.device)
        logger.info(f"チェックポイント読み込み: epoch={epoch}, loss={loss:.4f}")

    trainer = ImitationTrainer(net, device=args.device, lr=args.lr)
    trainer.fit(dataset, epochs=args.epochs, batch_size=args.batch_size)


if __name__ == "__main__":
    main()

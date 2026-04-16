"""
Phase 5: 自己対戦ワーカー
=========================

AlphaZero スタイルの自己対戦でトレーニングサンプルを生成する。

1エピソードのフロー:
  初期状態ベクトル
    → MCTS 探索 (PolicyValueNetwork + Dirichlet ノイズ)
    → 確率的行動サンプリング
    → TransitionModel で次状態・終了判定
    → 繰り返し (最大 max_steps ターン)
  ゲーム終了
    → 各ステップに outcome を割り当て
    → (state_vec, mcts_probs, outcome) のリストを返す

出力サンプル:
  state_vec  : np.ndarray (STATE_DIM,)
  mcts_probs : np.ndarray (MAX_ACTIONS,)  — MCTS 訪問率
  outcome    : float ∈ [-1.0, +1.0]      — ゲーム結果

初期状態の供給方法:
  - データ供給: parsed JSONL の第 1 ターン状態を使う (推奨)
  - ランダム:   featurizer から均一な初期状態を生成

実行:
  python ai/self_play.py
"""

from __future__ import annotations
import sys
import json
import logging
import math
import time
from pathlib import Path
from typing import Optional

import numpy as np
import torch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "db"))
sys.path.insert(0, str(ROOT / "ai"))

from featurizer import BattleFeaturizer, MAX_ACTIONS
from network import PolicyValueNetwork, load_checkpoint
from world_model import TransitionModel
from mcts import MCTS, NUM_SIMS, DIRICHLET_α, DIRICHLET_ε
from action_classifier import ActionCategory

logger = logging.getLogger(__name__)

PARSED_DIR = ROOT / "data" / "parsed"
MODELS_DIR = ROOT / "ai" / "models"

# 自己対戦デフォルト設定
SELF_PLAY_MAX_STEPS   = 80    # 1エピソードの最大ターン数
SELF_PLAY_TEMPERATURE = 1.0   # 探索序盤の温度 (ランダム性大)
TEMP_THRESHOLD        = 20    # このターン数以降は温度を 0 に下げる
VALID_MASK_DEFAULT: np.ndarray = np.ones(MAX_ACTIONS, dtype=np.float32)
# MEGA カテゴリは自己対戦では常に除外 (別途フラグで制御)
VALID_MASK_DEFAULT[int(ActionCategory.MEGA_MOVE)] = 0.0


# ===== SelfPlayWorker =====

class SelfPlayWorker:
    """
    MCTS + TransitionModel を用いて自己対戦エピソードを生成する。

    1 インスタンスで複数エピソードを繰り返し生成できる。
    ネットワークウェイトを外部から更新して渡すことで、
    最新モデルによる継続的な自己対戦が可能。

    Args:
        net:        PolicyValueNetwork (eval モードで使用)
        world_model: TransitionModel (eval モードで使用)
        num_sims:   MCTS シミュレーション回数
        device:     推論デバイス
    """

    def __init__(
        self,
        net:         PolicyValueNetwork,
        world_model: TransitionModel,
        num_sims:    int  = NUM_SIMS,
        device:      str  = "cpu",
    ):
        self.mcts        = MCTS(net, world_model, num_sims=num_sims,
                                device=device, add_noise=True)
        self.world_model = world_model.to(device)
        self.featurizer  = BattleFeaturizer()
        self.device      = device

    # ── 遷移 ─────────────────────────────────────────────────────

    @torch.no_grad()
    def _step(
        self, state_vec: np.ndarray, action: int
    ) -> tuple[np.ndarray, bool, float]:
        """TransitionModel で 1 ステップ進める"""
        s = torch.from_numpy(state_vec).float().unsqueeze(0).to(self.device)
        a = torch.tensor([action], dtype=torch.long, device=self.device)
        ns, done_logit, r = self.world_model(s, a)
        next_vec  = ns.squeeze(0).cpu().numpy()
        done      = torch.sigmoid(done_logit).item() > 0.5
        reward    = float(r.squeeze().item())
        return next_vec, done, reward

    # ── エピソード生成 ─────────────────────────────────────────────

    def run_episode(
        self,
        initial_state_vec: np.ndarray,
        valid_mask:        np.ndarray | None = None,
        max_steps:         int   = SELF_PLAY_MAX_STEPS,
        temp_threshold:    int   = TEMP_THRESHOLD,
    ) -> list[dict]:
        """
        1 エピソードの自己対戦を実行し、トレーニングサンプルを返す。

        Args:
            initial_state_vec: 初期状態ベクトル (STATE_DIM,)
            valid_mask:        有効な ActionCategory マスク (None=デフォルト)
            max_steps:         最大ターン数
            temp_threshold:    このターン以降は温度 0 (決定的) にする

        Returns:
            list of dict — 各ステップのサンプル
                {"state_vec", "mcts_probs", "outcome"}
        """
        if valid_mask is None:
            valid_mask = VALID_MASK_DEFAULT.copy()

        state_vec  = initial_state_vec.copy()
        states:     list[np.ndarray] = []
        probs_list: list[np.ndarray] = []
        done       = False
        outcome    = 0.0

        for step in range(max_steps):
            if done:
                break

            temperature = SELF_PLAY_TEMPERATURE if step < temp_threshold else 0.0

            # MCTS 探索
            mcts_probs = self.mcts.search(state_vec, valid_mask, temperature)

            states.append(state_vec.copy())
            probs_list.append(mcts_probs.copy())

            # 行動サンプリング (温度に応じて確率的 or 決定的)
            if temperature > 0:
                action = int(np.random.choice(MAX_ACTIONS, p=mcts_probs))
            else:
                action = int(np.argmax(mcts_probs))

            # WorldModel で遷移
            state_vec, done, reward = self._step(state_vec, action)
            if done:
                outcome = float(np.clip(reward, -1.0, 1.0))

        # エピソード終了後、全ステップに outcome を割り当て
        # AlphaZero 方式: 奇数ターンは符号反転 (交互プレイ想定)
        samples: list[dict] = []
        for t, (sv, mp) in enumerate(zip(states, probs_list)):
            # p1 視点のアウトカム (偶数ターン=p1手番 で符号一定)
            z = outcome * (1.0 if t % 2 == 0 else -1.0)
            samples.append({
                "state_vec":  sv,
                "mcts_probs": mp,
                "outcome":    z,
            })

        return samples


# ===== 初期状態の供給 =====

def load_initial_states(
    jsonl_paths:  list[Path],
    featurizer:   BattleFeaturizer,
    max_states:   int  = 500,
) -> list[np.ndarray]:
    """
    parsed JSONL から各試合の第 1 ターン状態ベクトルを抽出する。

    MCTS 自己対戦の出発点として使用する。
    """
    from game_state import BattleState, PlayerState, PokemonStatus, StatusCondition

    def _make_poke(name: str, hp_pct: float, status_str: str | None) -> PokemonStatus:
        sc = StatusCondition.NONE
        if status_str:
            sc = StatusCondition.from_showdown(status_str)
        return PokemonStatus(
            name_jp=name, name_en=name,
            current_hp=int(hp_pct * 100), max_hp=100,
            status=sc,
        )

    states: list[np.ndarray] = []

    for path in jsonl_paths:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line.strip())
                except Exception:
                    continue

                turns = record.get("turns", [])
                if not turns:
                    continue

                # 第 1 ターンのみ
                turn = turns[0]
                hp_map  = turn.get("hp_snapshot", {})
                active  = turn.get("active", {})
                ap1     = active.get("p1", "")
                ap2     = active.get("p2", "")
                if not ap1 or not ap2:
                    continue

                bench_p1: list[str] = []
                bench_p2: list[str] = []
                for key in hp_map:
                    if ":" in key:
                        slot, pname = key.split(":", 1)
                        if slot == "p1" and pname != ap1:
                            bench_p1.append(pname)
                        elif slot == "p2" and pname != ap2:
                            bench_p2.append(pname)

                def make_player(pid, active_name, bench):
                    info = hp_map.get(f"{pid}:{active_name}", {})
                    hp   = info.get("hp_percent", 1.0) if isinstance(info, dict) else 1.0
                    st   = info.get("status") if isinstance(info, dict) else None
                    ps   = PlayerState(player_id=pid, player_name=pid)
                    ps.selected = [_make_poke(active_name, hp, st)]
                    for b in bench[:2]:
                        bi   = hp_map.get(f"{pid}:{b}", {})
                        bhp  = bi.get("hp_percent", 1.0) if isinstance(bi, dict) else 1.0
                        bst  = bi.get("status") if isinstance(bi, dict) else None
                        ps.selected.append(_make_poke(b, bhp, bst))
                    ps.active_index = 0
                    return ps

                p1 = make_player("p1", ap1, bench_p1)
                p2 = make_player("p2", ap2, bench_p2)
                state = BattleState(turn=1, p1=p1, p2=p2)

                try:
                    sv = featurizer.encode(state)
                    states.append(sv)
                except Exception:
                    continue

                if len(states) >= max_states:
                    return states

    logger.info(f"初期状態ロード完了: {len(states)} 件")
    return states


def make_random_initial_state(featurizer: BattleFeaturizer) -> np.ndarray:
    """フォールバック用: ランダムな初期状態ベクトルを生成"""
    from game_state import BattleState, PlayerState, PokemonStatus
    def make_ps(pid):
        ps = PlayerState(player_id=pid, player_name=pid)
        ps.selected = [
            PokemonStatus(name_jp="dummy", name_en="garchomp",
                          current_hp=300, max_hp=300),
            PokemonStatus(name_jp="dummy2", name_en="ferrothorn",
                          current_hp=300, max_hp=300),
        ]
        ps.active_index = 0
        return ps
    state = BattleState(turn=1, p1=make_ps("p1"), p2=make_ps("p2"))
    return featurizer.encode(state)


# ===== 動作確認 =====

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    net   = PolicyValueNetwork()
    world = TransitionModel()

    ckpt = MODELS_DIR / "policy_value_best.pt"
    if ckpt.exists():
        load_checkpoint(net, None, ckpt)
        logger.info(f"PolicyValueNet 読み込み: {ckpt}")

    world_ckpt = MODELS_DIR / "world_model_best.pt"
    if world_ckpt.exists():
        world.load_state_dict(
            torch.load(str(world_ckpt), map_location="cpu", weights_only=True)
        )
        logger.info(f"WorldModel 読み込み: {world_ckpt}")

    net.eval()
    world.eval()

    worker     = SelfPlayWorker(net, world, num_sims=30)
    featurizer = BattleFeaturizer()

    # 初期状態を実データから取得
    jsonl_paths = list(PARSED_DIR.glob("*.jsonl"))
    init_states = load_initial_states(jsonl_paths, featurizer, max_states=10)

    if not init_states:
        logger.warning("実データなし: ランダム初期状態を使用")
        init_states = [make_random_initial_state(featurizer)]

    logger.info(f"\n--- 自己対戦テスト (1 エピソード, num_sims=30) ---")
    t0 = time.time()
    samples = worker.run_episode(init_states[0], max_steps=20)
    elapsed = time.time() - t0

    logger.info(f"ステップ数: {len(samples)}")
    logger.info(f"所要時間:   {elapsed:.1f}s ({elapsed/max(len(samples),1):.2f}s/step)")
    logger.info(f"outcome:    {samples[-1]['outcome'] if samples else 'N/A'}")

    # 行動分布を確認
    from action_classifier import CATEGORY_LABELS
    from collections import Counter
    chosen = [int(s["mcts_probs"].argmax()) for s in samples]
    cnt = Counter(chosen)
    logger.info("選択カテゴリ分布:")
    for cat, n in sorted(cnt.items()):
        logger.info(f"  [{cat:2d}] {CATEGORY_LABELS.get(cat, str(cat)):<16} : {n}")

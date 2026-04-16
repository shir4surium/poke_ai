"""
Phase 5: 自己対戦 RL トレーナー
================================

AlphaZero 方式の強化学習ループ。

1イテレーションの流れ:
  1. SelfPlayWorker で N エピソード生成
     → (state_vec, mcts_probs, outcome) サンプル群
  2. ReplayBuffer に追加 (古いサンプルを上限まで保持)
  3. ReplayBuffer からミニバッチを抽出して PolicyValueNetwork を更新
     損失 = CE(π_mcts, π_pred) + λ * MSE(z, v_pred)
  4. 更新後のモデルを保存 → 次のイテレーションへ

模倣学習との違い:
  - ラベルが1-hot でなく MCTS 確率分布 π_mcts → KL ダイバージェンス最小化
  - outcome z は自己対戦の実際の勝敗 → より真の強さを反映
  - ネットワークを自分自身と対戦させることで模倣学習超えを目指す

実行:
  # 10 イテレーション, 各 100 エピソード
  python ai/rl_trainer.py --iterations 10 --episodes_per_iter 100

  # 既存チェックポイントから継続
  python ai/rl_trainer.py --checkpoint ai/models/policy_value_best.pt --iterations 5
"""

from __future__ import annotations
import sys
import logging
import argparse
import time
import random
from collections import deque
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "db"))
sys.path.insert(0, str(ROOT / "ai"))

from featurizer import BattleFeaturizer, MAX_ACTIONS
from network import PolicyValueNetwork, save_checkpoint, load_checkpoint
from world_model import TransitionModel
from self_play import SelfPlayWorker, load_initial_states, make_random_initial_state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

MODELS_DIR = ROOT / "ai" / "models"
PARSED_DIR = ROOT / "data" / "parsed"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

LAMBDA_VALUE = 0.5    # value 損失の重み (模倣学習と同じ)
BUFFER_SIZE  = 50_000 # リプレイバッファ最大サンプル数


# ===== ReplayBuffer =====

class ReplayBuffer:
    """
    自己対戦サンプルを蓄積する循環バッファ。

    格納形式: {"state_vec", "mcts_probs", "outcome"}
    最大 capacity 件を超えた場合、古いサンプルを先頭から削除する。
    """

    def __init__(self, capacity: int = BUFFER_SIZE):
        self.buffer: deque[dict] = deque(maxlen=capacity)

    def extend(self, samples: list[dict]) -> None:
        self.buffer.extend(samples)

    def sample(self, n: int) -> list[dict]:
        n = min(n, len(self.buffer))
        return random.sample(list(self.buffer), n)

    def __len__(self) -> int:
        return len(self.buffer)


# ===== SelfPlayDataset =====

class SelfPlayDataset(Dataset):
    """ReplayBuffer のスナップショットから DataLoader 用データセットを作る"""

    def __init__(self, samples: list[dict]):
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        s = self.samples[idx]
        return (
            torch.from_numpy(s["state_vec"]).float(),
            torch.from_numpy(s["mcts_probs"]).float(),
            torch.tensor(s["outcome"], dtype=torch.float32),
        )


# ===== RLTrainer =====

class RLTrainer:
    """
    自己対戦データで PolicyValueNetwork を更新する。

    損失関数 (AlphaZero):
      L = -Σ π_mcts * log(π_net)    (policy: cross-entropy with soft labels)
        + λ * (z - v_net)^2          (value:  MSE)
    """

    def __init__(
        self,
        net:         PolicyValueNetwork,
        device:      str   = "cpu",
        lr:          float = 1e-4,     # RL は模倣学習より低め
        weight_decay: float = 1e-4,
    ):
        self.net    = net.to(device)
        self.device = device
        self.optimizer = torch.optim.AdamW(
            net.parameters(), lr=lr, weight_decay=weight_decay
        )

    def _step(self, batch, train: bool) -> dict[str, float]:
        state_t, mcts_probs_t, outcome_t = [t.to(self.device) for t in batch]
        outcome_t = outcome_t.unsqueeze(1)

        with torch.set_grad_enabled(train):
            log_policy, value = self.net(state_t)

            # AlphaZero policy loss: -sum(π_mcts * log π_net)
            loss_policy = -(mcts_probs_t * log_policy).sum(dim=-1).mean()
            loss_value  = F.mse_loss(value, outcome_t)
            loss        = loss_policy + LAMBDA_VALUE * loss_value

        if train:
            self.optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.net.parameters(), 1.0)
            self.optimizer.step()

        return {
            "loss": loss.item(),
            "loss_policy": loss_policy.item(),
            "loss_value": loss_value.item(),
        }

    def train_on_buffer(
        self,
        buffer:     ReplayBuffer,
        epochs:     int = 5,
        batch_size: int = 128,
        sample_size: int = 10_000,
    ) -> dict[str, float]:
        """
        バッファからサンプリングしてネットワークを更新する。

        Args:
            buffer:      ReplayBuffer
            epochs:      更新エポック数
            batch_size:  ミニバッチサイズ
            sample_size: バッファから取り出すサンプル数

        Returns:
            最終エポックの平均損失
        """
        samples = buffer.sample(sample_size)
        dataset = SelfPlayDataset(samples)
        loader  = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0)

        last_metrics: dict[str, float] = {}
        self.net.train()
        for epoch in range(1, epochs + 1):
            totals: dict[str, float] = {}
            for batch in loader:
                for k, v in self._step(batch, True).items():
                    totals[k] = totals.get(k, 0.0) + v
            n = len(loader)
            last_metrics = {k: v / n for k, v in totals.items()}
            logger.info(
                f"  RL epoch {epoch}/{epochs} | "
                f"loss={last_metrics['loss']:.4f} "
                f"(policy={last_metrics['loss_policy']:.4f}, "
                f"value={last_metrics['loss_value']:.4f})"
            )
        self.net.eval()
        return last_metrics


# ===== メインループ =====

def run_rl_loop(
    net:          PolicyValueNetwork,
    world_model:  TransitionModel,
    iterations:   int   = 10,
    episodes_per_iter: int = 100,
    num_sims:     int   = 50,
    epochs_per_iter: int = 5,
    batch_size:   int   = 128,
    device:       str   = "cpu",
    save_every:   int   = 1,
) -> None:
    """
    AlphaZero スタイルの RL メインループ。

    Args:
        net:              PolicyValueNetwork (模倣学習済みから継続)
        world_model:      TransitionModel (固定)
        iterations:       RL イテレーション数
        episodes_per_iter: 1イテレーションあたり自己対戦エピソード数
        num_sims:         MCTS シミュレーション回数 (速度とトレードオフ)
        epochs_per_iter:  1イテレーションあたり学習エポック数
        batch_size:       ミニバッチサイズ
        device:           推論・学習デバイス
        save_every:       何イテレーションごとにモデルを保存するか
    """
    world_model.eval()

    worker    = SelfPlayWorker(net, world_model, num_sims=num_sims, device=device)
    trainer   = RLTrainer(net, device=device)
    buffer    = ReplayBuffer()
    featurizer = BattleFeaturizer()

    # 初期状態を実データから取得
    jsonl_paths = list(PARSED_DIR.glob("*.jsonl"))
    init_states = load_initial_states(jsonl_paths, featurizer, max_states=500)
    if not init_states:
        logger.warning("実データなし: ランダム初期状態を使用")
        init_states = [make_random_initial_state(featurizer)] * 10

    logger.info(
        f"RL ループ開始: {iterations} iter × {episodes_per_iter} ep "
        f"| MCTS sims={num_sims} | 初期状態={len(init_states)} 件"
    )

    best_loss = float("inf")

    for it in range(1, iterations + 1):
        iter_start = time.time()
        logger.info(f"\n{'='*60}")
        logger.info(f"イテレーション {it}/{iterations}")

        # ── 自己対戦フェーズ ──────────────────────────────────
        net.eval()
        total_samples = 0
        for ep in range(episodes_per_iter):
            init_sv = random.choice(init_states)
            samples = worker.run_episode(init_sv)
            buffer.extend(samples)
            total_samples += len(samples)

        logger.info(
            f"自己対戦完了: {episodes_per_iter} ep, "
            f"+{total_samples} サンプル (バッファ計={len(buffer)})"
        )

        # サンプルが少ない場合はスキップ
        if len(buffer) < batch_size:
            logger.warning(f"バッファ不足 ({len(buffer)} < {batch_size}): スキップ")
            continue

        # ── 学習フェーズ ──────────────────────────────────────
        metrics = trainer.train_on_buffer(
            buffer,
            epochs=epochs_per_iter,
            batch_size=batch_size,
            sample_size=min(len(buffer), 10_000),
        )

        elapsed = time.time() - iter_start
        logger.info(
            f"イテレーション完了: {elapsed:.0f}s | "
            f"loss={metrics.get('loss', 0):.4f}"
        )

        # ── モデル保存 ────────────────────────────────────────
        if it % save_every == 0:
            path = MODELS_DIR / f"rl_iter_{it:04d}.pt"
            save_checkpoint(net, trainer.optimizer, it, metrics.get("loss", 0), path)
            logger.info(f"モデル保存: {path}")

        # best モデル更新
        if metrics.get("loss", float("inf")) < best_loss:
            best_loss = metrics["loss"]
            path = MODELS_DIR / "rl_best.pt"
            save_checkpoint(net, trainer.optimizer, it, best_loss, path)
            logger.info(f"  → best RL モデル更新: {path} (loss={best_loss:.4f})")

    # 最終モデル保存
    path = MODELS_DIR / "rl_last.pt"
    save_checkpoint(net, trainer.optimizer, iterations, metrics.get("loss", 0), path)
    logger.info(f"\nRL 完了。最終モデル: {path}")


# ===== エントリポイント =====

def main():
    parser = argparse.ArgumentParser(description="Champions AI 自己対戦 RL")
    parser.add_argument("--iterations",        type=int,   default=10)
    parser.add_argument("--episodes_per_iter", type=int,   default=50)
    parser.add_argument("--num_sims",          type=int,   default=50,
                        help="MCTS シミュレーション数 (速度↔品質)")
    parser.add_argument("--epochs_per_iter",   type=int,   default=5)
    parser.add_argument("--batch_size",        type=int,   default=128)
    parser.add_argument("--checkpoint",        type=str,   default=None,
                        help="開始チェックポイント (省略時: policy_value_best.pt)")
    parser.add_argument("--device",            type=str,   default="cpu")
    parser.add_argument("--save_every",        type=int,   default=1)
    args = parser.parse_args()

    net   = PolicyValueNetwork()
    world = TransitionModel()

    # PolicyValueNetwork チェックポイント読み込み
    ckpt = args.checkpoint or str(MODELS_DIR / "policy_value_best.pt")
    if Path(ckpt).exists():
        epoch, loss = load_checkpoint(net, None, ckpt, args.device)
        logger.info(f"PolicyValueNet 読み込み: {ckpt} (epoch={epoch}, loss={loss:.4f})")
    else:
        logger.info("PolicyValueNet: 未学習モデルで開始")

    # WorldModel チェックポイント読み込み (state_dict 直接保存形式)
    world_ckpt = MODELS_DIR / "world_model_best.pt"
    if world_ckpt.exists():
        world.load_state_dict(
            torch.load(str(world_ckpt), map_location=args.device, weights_only=True)
        )
        logger.info(f"WorldModel 読み込み: {world_ckpt}")
    else:
        logger.warning("WorldModel チェックポイント未発見: ランダム重みで動作")

    world.eval()
    net.eval()

    run_rl_loop(
        net          = net,
        world_model  = world,
        iterations   = args.iterations,
        episodes_per_iter = args.episodes_per_iter,
        num_sims     = args.num_sims,
        epochs_per_iter  = args.epochs_per_iter,
        batch_size   = args.batch_size,
        device       = args.device,
        save_every   = args.save_every,
    )


if __name__ == "__main__":
    main()

"""
Phase 3-C: 世界モデル (TransitionModel)

(状態, 行動) → 次の状態 を予測するモデル。
Champions には公式シミュレーターが存在しないため、
Showdown リプレイデータから遷移を学習する。

入力:
  state  : (batch, STATE_DIM=372)  現在の状態ベクトル
  action : (batch,)               行動インデックス (0 ~ MAX_ACTIONS-1)

出力:
  next_state : (batch, STATE_DIM)  次の状態予測
  done_logit : (batch, 1)         対戦終了確率のロジット (BCE 損失用)
  reward     : (batch, 1)         即時報酬予測 (勝=+1, 負=-1, 継続=0)
"""

from __future__ import annotations
import sys
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).parent.parent / "simulator"))
from featurizer import BattleFeaturizer

STATE_DIM   = BattleFeaturizer.TOTAL_DIM  # 372
MAX_ACTIONS = 12  # ActionCategory の12カテゴリ
HIDDEN_DIM  = 512
NUM_BLOCKS  = 3


# ===== 残差ブロック (world_model 内部用) =====

class _ResBlock(nn.Module):
    def __init__(self, dim: int, dropout: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, dim), nn.LayerNorm(dim), nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(dim, dim), nn.LayerNorm(dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.relu(x + self.net(x))


# ===== TransitionModel =====

class TransitionModel(nn.Module):
    """
    世界モデル: (s, a) → s', done, r

    アーキテクチャ:
      ・状態ベクトル (372) を Linear → 512 に射影
      ・行動を Embedding (10 → 32) で表現
      ・結合 (512 + 32 = 544) → Linear → 512
      ・残差ブロック × NUM_BLOCKS
      ・次状態ヘッド: 512 → 372
      ・終了フラグヘッド: 512 → 1 (BCE)
      ・即時報酬ヘッド: 512 → 1 (Tanh)

    損失:
      L = λ1 * MSE(s') + λ2 * BCE(done) + λ3 * MSE(r)
    """

    LAMBDA_STATE  = 1.0
    LAMBDA_DONE   = 0.5
    LAMBDA_REWARD = 0.3

    def __init__(
        self,
        state_dim:   int = STATE_DIM,
        num_actions: int = MAX_ACTIONS,
        hidden_dim:  int = HIDDEN_DIM,
        action_emb:  int = 32,
        num_blocks:  int = NUM_BLOCKS,
        dropout:     float = 0.1,
    ):
        super().__init__()

        # 状態射影
        self.state_proj = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
        )

        # 行動 Embedding
        self.action_emb = nn.Embedding(num_actions, action_emb)

        # 結合→共有表現
        self.fuse = nn.Sequential(
            nn.Linear(hidden_dim + action_emb, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
        )

        # 残差ブロック
        self.blocks = nn.ModuleList([
            _ResBlock(hidden_dim, dropout) for _ in range(num_blocks)
        ])

        # 各ヘッド
        self.next_state_head = nn.Linear(hidden_dim, state_dim)
        self.done_head        = nn.Linear(hidden_dim, 1)
        self.reward_head      = nn.Sequential(
            nn.Linear(hidden_dim, 1), nn.Tanh()
        )

    def forward(
        self,
        state:  torch.Tensor,   # (batch, STATE_DIM)
        action: torch.Tensor,   # (batch,) long
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Returns:
            next_state : (batch, STATE_DIM)
            done_logit : (batch, 1)
            reward     : (batch, 1)
        """
        hs = self.state_proj(state)                  # (B, H)
        ha = self.action_emb(action)                 # (B, E)
        h  = self.fuse(torch.cat([hs, ha], dim=-1))  # (B, H)

        for block in self.blocks:
            h = block(h)

        next_state = self.next_state_head(h)         # (B, STATE_DIM)
        done_logit = self.done_head(h)               # (B, 1)
        reward     = self.reward_head(h)             # (B, 1)
        return next_state, done_logit, reward

    def loss(
        self,
        state:       torch.Tensor,  # (B, STATE_DIM)
        action:      torch.Tensor,  # (B,)
        next_state:  torch.Tensor,  # (B, STATE_DIM)
        done:        torch.Tensor,  # (B, 1) float 0/1
        reward:      torch.Tensor,  # (B, 1)
    ) -> tuple[torch.Tensor, dict[str, float]]:
        """
        合計損失と内訳辞書を返す。
        """
        pred_ns, pred_done_logit, pred_r = self(state, action)

        loss_state  = F.mse_loss(pred_ns, next_state)
        loss_done   = F.binary_cross_entropy_with_logits(pred_done_logit, done)
        loss_reward = F.mse_loss(pred_r, reward)

        total = (
            self.LAMBDA_STATE  * loss_state
          + self.LAMBDA_DONE   * loss_done
          + self.LAMBDA_REWARD * loss_reward
        )
        breakdown = {
            "state":  loss_state.item(),
            "done":   loss_done.item(),
            "reward": loss_reward.item(),
            "total":  total.item(),
        }
        return total, breakdown

    def rollout(
        self,
        state:   torch.Tensor,   # (1, STATE_DIM)
        actions: list[int],
        device:  str = "cpu",
    ) -> list[dict]:
        """
        仮想ロールアウト: 行動列を受け取り、予測状態列を返す。

        Returns:
            list of {"state": np.ndarray, "done": bool, "reward": float}
        """
        import numpy as np
        self.eval()
        results = []
        s = state.to(device)
        with torch.no_grad():
            for a in actions:
                a_t = torch.tensor([a], dtype=torch.long, device=device)
                ns, done_logit, r = self(s, a_t)
                done_prob = torch.sigmoid(done_logit).item()
                results.append({
                    "state":  ns.squeeze(0).cpu().numpy(),
                    "done":   done_prob > 0.5,
                    "reward": r.squeeze().item(),
                })
                if done_prob > 0.5:
                    break
                s = ns
        return results

    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# ===== 動作確認 =====

if __name__ == "__main__":
    import numpy as np

    model = TransitionModel()
    print(f"TransitionModel パラメータ数: {model.num_parameters():,}")

    B = 4
    states  = torch.randn(B, STATE_DIM)
    actions = torch.randint(0, MAX_ACTIONS, (B,))
    ns, dl, r = model(states, actions)
    print(f"next_state: {ns.shape}, done_logit: {dl.shape}, reward: {r.shape}")

    # 損失計算
    target_ns     = torch.randn(B, STATE_DIM)
    target_done   = torch.zeros(B, 1)
    target_reward = torch.zeros(B, 1)
    loss, bd = model.loss(states, actions, target_ns, target_done, target_reward)
    print(f"loss={loss.item():.4f}  {bd}")

    # ロールアウト
    s0 = torch.randn(1, STATE_DIM)
    traj = model.rollout(s0, [0, 3, 8, 1])
    print(f"ロールアウト長: {len(traj)}, 最終報酬: {traj[-1]['reward']:.4f}")
    print("OK")

"""
Phase 3-C: PolicyValueNetwork

AlphaZero スタイルの方策・価値ネットワーク。
MCTS の評価関数として使用する。

入力: BattleFeaturizer が生成した 372 次元ベクトル
出力:
  - policy: 各行動の対数確率 (MAX_ACTIONS = 10 次元)
  - value:  現在局面の勝利期待値 (-1.0 ~ +1.0)
"""

from __future__ import annotations
import sys
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).parent.parent / "simulator"))
from featurizer import POKEMON_FULL_DIM, FIELD_FEAT_DIM, BattleFeaturizer

# 定数
STATE_DIM   = BattleFeaturizer.TOTAL_DIM  # 372
MAX_ACTIONS = 12                           # ActionCategory の12カテゴリ
HIDDEN_DIM  = 512
NUM_BLOCKS  = 4


# ===== 残差ブロック =====

class ResidualBlock(nn.Module):
    """全結合残差ブロック (LayerNorm + ReLU)"""

    def __init__(self, dim: int, dropout: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, dim),
            nn.LayerNorm(dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(dim, dim),
            nn.LayerNorm(dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.relu(x + self.net(x))


# ===== 共有バックボーン =====

class SharedBackbone(nn.Module):
    """
    入力層 → 残差ブロック × NUM_BLOCKS

    方策ヘッドと価値ヘッドが共通で使う特徴抽出器。
    """

    def __init__(
        self,
        input_dim:  int = STATE_DIM,
        hidden_dim: int = HIDDEN_DIM,
        num_blocks: int = NUM_BLOCKS,
        dropout:    float = 0.1,
    ):
        super().__init__()
        self.input_proj = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
        )
        self.blocks = nn.ModuleList([
            ResidualBlock(hidden_dim, dropout) for _ in range(num_blocks)
        ])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.input_proj(x)
        for block in self.blocks:
            h = block(h)
        return h


# ===== PolicyValueNetwork =====

class PolicyValueNetwork(nn.Module):
    """
    方策・価値ネットワーク（双頭）

    使い方:
        net = PolicyValueNetwork()
        state_vec = featurizer.encode(battle_state)          # shape: (372,)
        x = torch.from_numpy(state_vec).unsqueeze(0)         # (1, 372)
        log_policy, value = net(x)
        # log_policy: (1, 10)  — log softmax
        # value:      (1, 1)   — tanh (-1 ~ +1)

    学習時は CrossEntropy(policy) + MSE(value) の合計損失を使う。
    """

    def __init__(
        self,
        input_dim:   int = STATE_DIM,
        hidden_dim:  int = HIDDEN_DIM,
        num_blocks:  int = NUM_BLOCKS,
        num_actions: int = MAX_ACTIONS,
        dropout:     float = 0.1,
    ):
        super().__init__()
        self.backbone = SharedBackbone(input_dim, hidden_dim, num_blocks, dropout)

        # 方策ヘッド
        self.policy_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, num_actions),
        )

        # 価値ヘッド
        self.value_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Tanh(),
        )

    def forward(
        self, x: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: (batch, STATE_DIM) の状態ベクトル

        Returns:
            log_policy: (batch, num_actions) — 対数確率
            value:      (batch, 1)           — 勝利期待値 (-1~+1)
        """
        h = self.backbone(x)
        log_policy = F.log_softmax(self.policy_head(h), dim=-1)
        value = self.value_head(h)
        return log_policy, value

    def predict(
        self, state_vec: "np.ndarray", device: str = "cpu"
    ) -> tuple["np.ndarray", float]:
        """
        numpy ベクトルを受け取り numpy で返す（推論専用）

        Returns:
            policy_probs: (num_actions,) — 確率分布
            value:        float          — 勝利期待値
        """
        import numpy as np
        self.eval()
        with torch.no_grad():
            x = torch.from_numpy(state_vec).float().unsqueeze(0).to(device)
            log_p, v = self(x)
            policy = log_p.exp().squeeze(0).cpu().numpy()
            value  = v.squeeze().item()
        return policy, value

    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# ===== アクションマスキング =====

def masked_log_softmax(
    logits: torch.Tensor, mask: torch.Tensor
) -> torch.Tensor:
    """
    無効な行動を -inf でマスクしてから log_softmax を計算する。

    Args:
        logits: (batch, num_actions)
        mask:   (batch, num_actions)  — 有効なら 1、無効なら 0

    Returns:
        masked log_softmax: (batch, num_actions)
    """
    masked = logits.masked_fill(mask == 0, float("-inf"))
    return F.log_softmax(masked, dim=-1)


# ===== チェックポイント =====

def save_checkpoint(
    net: PolicyValueNetwork,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    loss: float,
    path: str | Path,
) -> None:
    """モデルとオプティマイザの状態を保存"""
    torch.save({
        "epoch":      epoch,
        "loss":       loss,
        "state_dict": net.state_dict(),
        "optimizer":  optimizer.state_dict(),
    }, path)


def load_checkpoint(
    net: PolicyValueNetwork,
    optimizer: torch.optim.Optimizer | None,
    path: str | Path,
    device: str = "cpu",
) -> tuple[int, float]:
    """チェックポイントを読み込み、(epoch, loss) を返す"""
    ckpt = torch.load(path, map_location=device)
    net.load_state_dict(ckpt["state_dict"])
    if optimizer is not None:
        optimizer.load_state_dict(ckpt["optimizer"])
    return ckpt["epoch"], ckpt["loss"]


# ===== 動作確認 =====

if __name__ == "__main__":
    import numpy as np

    net = PolicyValueNetwork()
    print(f"パラメータ数: {net.num_parameters():,}")
    print(f"入力次元: {STATE_DIM}, 行動数: {MAX_ACTIONS}")

    dummy = np.zeros(STATE_DIM, dtype=np.float32)
    dummy[0] = 0.8   # 自分の場ポケHP
    dummy[59] = 0.6  # 相手の場ポケHP

    policy, value = net.predict(dummy)
    print(f"方策 (確率合計={policy.sum():.4f}): {policy.round(4)}")
    print(f"価値: {value:.4f}")

    # バッチ入力テスト
    x = torch.randn(8, STATE_DIM)
    log_p, v = net(x)
    print(f"\nバッチ処理: log_policy={log_p.shape}, value={v.shape}")
    assert log_p.shape == (8, MAX_ACTIONS)
    assert v.shape == (8, 1)
    print("OK")

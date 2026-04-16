"""
Phase 4-A: モンテカルロ木探索 (MCTS)

AlphaZero スタイルの PUCT ベース MCTS。
PolicyValueNetwork を評価関数、TransitionModel を遷移モデルとして使用する。

探索フロー:
  1. Select   : UCB スコアが最大の子ノードを再帰的に選択
  2. Expand   : 未展開ノードを PolicyNetwork の事前確率で展開
  3. Evaluate : ValueNetwork で局面の勝利期待値を推定
  4. Backup   : 経路上の全ノードに価値を逆伝播

出力:
  search(state_vec, valid_mask) → action_probs (12,)
  各要素は各 ActionCategory の訪問回数に比例した確率
"""

from __future__ import annotations
import sys
import math
import numpy as np
import torch
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "ai"))

from featurizer import MAX_ACTIONS
from network import PolicyValueNetwork, masked_log_softmax
from world_model import TransitionModel

# MCTS ハイパーパラメータ
C_PUCT       = 1.5    # 探索定数（高いほど未探索を優先）
DIRICHLET_α  = 0.3    # ルートノードへのノイズ強度
DIRICHLET_ε  = 0.25   # ノイズ混合率（0 = ノイズなし）
NUM_SIMS     = 200    # 1手あたりのシミュレーション数（推論時）
ROLLOUT_DEPTH = 3     # 世界モデルによるロールアウト深さ
TEMPERATURE  = 1.0    # 行動選択温度（低いほど最善手重視）


# ===== MCTSNode =====

class MCTSNode:
    """
    MCTS の1ノード = 1つの局面。

    Attributes:
        state_vec : np.ndarray (STATE_DIM,) — この局面の状態ベクトル
        prior     : float — 親から選ばれた事前確率 P(s, a)
        parent    : MCTSNode | None
        children  : dict[int, MCTSNode]  action_cat → 子ノード
        N         : 訪問回数
        W         : 累積価値
        Q         : 平均価値 W/N
    """

    __slots__ = ("state_vec", "prior", "parent", "children", "N", "W", "is_terminal")

    def __init__(
        self,
        state_vec: np.ndarray,
        prior: float = 0.0,
        parent: Optional["MCTSNode"] = None,
        is_terminal: bool = False,
    ):
        self.state_vec   = state_vec
        self.prior       = prior
        self.parent      = parent
        self.children:   dict[int, "MCTSNode"] = {}
        self.N:          int   = 0
        self.W:          float = 0.0
        self.is_terminal = is_terminal

    @property
    def Q(self) -> float:
        return self.W / self.N if self.N > 0 else 0.0

    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def ucb_score(self, total_n: int, c_puct: float = C_PUCT) -> float:
        """PUCT スコア: Q + c_puct * P * sqrt(N_parent) / (1 + N_child)"""
        u = c_puct * self.prior * math.sqrt(total_n) / (1 + self.N)
        return self.Q + u

    def best_child(self, c_puct: float = C_PUCT) -> tuple[int, "MCTSNode"]:
        """PUCT スコアが最大の子ノードを返す"""
        total_n = sum(c.N for c in self.children.values())
        best_action = max(
            self.children,
            key=lambda a: self.children[a].ucb_score(total_n, c_puct),
        )
        return best_action, self.children[best_action]

    def visit_counts(self) -> np.ndarray:
        """各 ActionCategory の訪問回数ベクトル (MAX_ACTIONS,)"""
        counts = np.zeros(MAX_ACTIONS, dtype=np.float32)
        for a, child in self.children.items():
            if 0 <= a < MAX_ACTIONS:
                counts[a] = child.N
        return counts


# ===== MCTS =====

class MCTS:
    """
    PolicyValueNetwork + TransitionModel を用いた MCTS。

    使い方:
        mcts = MCTS(policy_value_net, transition_model)
        action_probs = mcts.search(state_vec, valid_mask)
    """

    def __init__(
        self,
        net:         PolicyValueNetwork,
        world_model: TransitionModel,
        num_sims:    int   = NUM_SIMS,
        c_puct:      float = C_PUCT,
        device:      str   = "cpu",
        add_noise:   bool  = True,
    ):
        self.net         = net.to(device)
        self.world_model = world_model.to(device)
        self.num_sims    = num_sims
        self.c_puct      = c_puct
        self.device      = device
        self.add_noise   = add_noise

        self.net.eval()
        self.world_model.eval()

    # ── ネットワーク推論 ──────────────────────────────────────────

    @torch.no_grad()
    def _evaluate(
        self,
        state_vec: np.ndarray,
        valid_mask: np.ndarray | None = None,
    ) -> tuple[np.ndarray, float]:
        """
        PolicyValueNetwork で (policy_probs, value) を返す。
        valid_mask が与えられた場合は無効行動をマスク。
        """
        x = torch.from_numpy(state_vec).float().unsqueeze(0).to(self.device)

        if valid_mask is not None:
            mask = torch.from_numpy(valid_mask).float().unsqueeze(0).to(self.device)
            logits = self.net.backbone(x)
            logits_raw = self.net.policy_head(logits)
            log_p = masked_log_softmax(logits_raw, mask)
            value = self.net.value_head(logits).squeeze().item()
        else:
            log_p, v = self.net(x)
            value = v.squeeze().item()

        policy = log_p.exp().squeeze(0).cpu().numpy()
        return policy, value

    @torch.no_grad()
    def _transition(
        self, state_vec: np.ndarray, action: int
    ) -> tuple[np.ndarray, bool, float]:
        """
        TransitionModel で (next_state, done, reward) を返す。
        """
        s = torch.from_numpy(state_vec).float().unsqueeze(0).to(self.device)
        a = torch.tensor([action], dtype=torch.long, device=self.device)
        ns, done_logit, r = self.world_model(s, a)
        next_vec  = ns.squeeze(0).cpu().numpy()
        done_prob = torch.sigmoid(done_logit).item()
        reward    = r.squeeze().item()
        return next_vec, done_prob > 0.5, reward

    # ── MCTS コア ────────────────────────────────────────────────

    def _select(self, node: MCTSNode) -> MCTSNode:
        """葉ノードに到達するまで best_child を辿る"""
        while not node.is_leaf() and not node.is_terminal:
            _, node = node.best_child(self.c_puct)
        return node

    def _expand(
        self,
        node: MCTSNode,
        valid_mask: np.ndarray | None = None,
    ) -> float:
        """
        葉ノードを展開し、ValueNetwork による価値推定値を返す。
        """
        if node.is_terminal:
            return node.W  # 終端ノードは累積価値をそのまま使う

        policy, value = self._evaluate(node.state_vec, valid_mask)

        # ルートノードに Dirichlet ノイズを加える
        if node.parent is None and self.add_noise:
            noise = np.random.dirichlet([DIRICHLET_α] * MAX_ACTIONS)
            policy = (1 - DIRICHLET_ε) * policy + DIRICHLET_ε * noise

        for action in range(MAX_ACTIONS):
            if valid_mask is not None and valid_mask[action] == 0:
                continue
            prior = float(policy[action])

            # TransitionModel で次状態を予測
            next_vec, done, reward = self._transition(node.state_vec, action)

            child = MCTSNode(
                state_vec=next_vec,
                prior=prior,
                parent=node,
                is_terminal=done,
            )
            if done:
                child.W = reward  # 終端報酬を初期値に設定

            node.children[action] = child

        return value

    def _backup(self, node: MCTSNode, value: float) -> None:
        """経路上の全ノードに価値を逆伝播する"""
        while node is not None:
            node.N += 1
            node.W += value
            value = -value   # ゼロサムゲーム: 相手視点は符号反転
            node = node.parent

    def search(
        self,
        state_vec:  np.ndarray,
        valid_mask: np.ndarray | None = None,
        temperature: float = TEMPERATURE,
    ) -> np.ndarray:
        """
        MCTS を num_sims 回実行し、行動確率分布を返す。

        Args:
            state_vec:  現在の状態ベクトル (STATE_DIM,)
            valid_mask: 有効な行動のマスク (MAX_ACTIONS,) — 1=有効, 0=無効
            temperature: 選択温度 (0 で argmax)

        Returns:
            action_probs: (MAX_ACTIONS,) 各カテゴリの選択確率
        """
        root = MCTSNode(state_vec=state_vec)

        for _ in range(self.num_sims):
            node = self._select(root)
            value = self._expand(node, valid_mask)
            self._backup(node, value)

        counts = root.visit_counts()

        if valid_mask is not None:
            counts *= valid_mask.astype(np.float32)

        if temperature == 0:
            # 最善手のみ選択
            probs = np.zeros_like(counts)
            if counts.max() > 0:
                probs[counts.argmax()] = 1.0
        else:
            powered = counts ** (1.0 / temperature)
            total = powered.sum()
            probs = powered / total if total > 0 else np.ones(MAX_ACTIONS) / MAX_ACTIONS

        return probs


# ===== 動作確認 =====

if __name__ == "__main__":
    import numpy as np
    from featurizer import BattleFeaturizer

    STATE_DIM = BattleFeaturizer.TOTAL_DIM

    net   = PolicyValueNetwork()
    world = TransitionModel()
    mcts  = MCTS(net, world, num_sims=50, add_noise=False)

    dummy_state = np.zeros(STATE_DIM, dtype=np.float32)
    dummy_state[0] = 0.8   # 自分HP
    dummy_state[59] = 0.5  # 相手HP

    # 全行動有効
    valid_mask = np.ones(MAX_ACTIONS, dtype=np.float32)

    print("MCTS 探索中 (50 sims)...")
    probs = mcts.search(dummy_state, valid_mask, temperature=1.0)

    from action_classifier import CATEGORY_LABELS, ActionCategory
    print(f"\n行動確率 (合計={probs.sum():.4f}):")
    for i, p in enumerate(probs):
        label = CATEGORY_LABELS.get(i, str(i))
        bar = "#" * int(p * 40)
        print(f"  [{i:2d}] {label:<16} {p:.4f} {bar}")

    best = probs.argmax()
    print(f"\n推奨カテゴリ: [{best}] {CATEGORY_LABELS[best]}")

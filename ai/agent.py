"""
Phase 4-B: Champions AI エージェント

BattleState を受け取り、MCTS + PolicyValueNetwork で
上位3行動候補を優先度順に返す。

入力:
  - BattleState (現在の対戦状態)
  - 利用可能な Action リスト (BattleState.get_available_actions)

出力:
  - list[Recommendation]  上位3件
    Recommendation.action     : Action オブジェクト
    Recommendation.score      : MCTS 選択確率 (0.0〜1.0)
    Recommendation.category   : ActionCategory
    Recommendation.reason     : 選択理由テキスト

使い方:
    agent = ChampionsAgent.from_checkpoint("ai/models/policy_value_best.pt")
    recs = agent.recommend(battle_state)
    for r in recs:
        print(r)
"""

from __future__ import annotations
import sys
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import torch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "db"))
sys.path.insert(0, str(ROOT / "ai"))

from game_state import BattleState, Action, ActionType
from featurizer import BattleFeaturizer, MAX_ACTIONS
from network import PolicyValueNetwork, load_checkpoint
from world_model import TransitionModel
from mcts import MCTS, NUM_SIMS
from action_classifier import (
    ActionClassifier, ActionCategory, CATEGORY_LABELS,
    NUM_ACTION_CATEGORIES,
)

logger = logging.getLogger(__name__)

MODELS_DIR = ROOT / "ai" / "models"


# ===== 推薦結果 =====

@dataclass
class Recommendation:
    action:   Action
    score:    float          # MCTS 選択確率
    category: int            # ActionCategory 値
    reason:   str            # 選択理由

    def __str__(self) -> str:
        cat_label = CATEGORY_LABELS.get(self.category, "不明")
        return (
            f"[{self.category:2d}] {cat_label:<16} "
            f"score={self.score:.3f} | {self.action} | {self.reason}"
        )


# ===== ChampionsAgent =====

class ChampionsAgent:
    """
    MCTS + PolicyValueNetwork による行動推薦エージェント。

    アーキテクチャ:
      1. BattleFeaturizer で状態を 372 次元に変換
      2. 各行動を ActionClassifier でカテゴリ分類
      3. MCTS で各カテゴリの選択確率を計算
      4. カテゴリ確率 × 行動の有効性でスコアリング
      5. 上位 top_k 件を返す
    """

    def __init__(
        self,
        net:         PolicyValueNetwork,
        world_model: TransitionModel,
        num_sims:    int  = NUM_SIMS,
        device:      str  = "cpu",
        add_noise:   bool = False,   # 推論時はノイズなし
    ):
        self.featurizer  = BattleFeaturizer()
        self.classifier  = ActionClassifier()
        self.mcts        = MCTS(net, world_model, num_sims=num_sims,
                                device=device, add_noise=add_noise)
        self.net         = net
        self.device      = device

    # ── 行動 → ActionCategory 変換 ─────────────────────────────

    def _action_to_category(self, action: Action, state: BattleState) -> int:
        """
        Action オブジェクトを ActionCategory に変換する。

        技行動: ActionClassifier.classify_move を使用
        交代行動: ActionClassifier.classify_switch を使用
        """
        p1 = state.p1
        p2 = state.p2
        active_p1 = p1.active
        active_p2 = p2.active

        user_name = active_p1.name_en if active_p1 else ""
        opp_name  = active_p2.name_en if active_p2 else ""

        if action.action_type == ActionType.MEGA:
            return int(ActionCategory.MEGA_MOVE)

        elif action.action_type == ActionType.MOVE:
            move_name = action.move_name_jp or ""
            # Showdown英語名があれば優先（ActionClassifier はEN名を使う）
            # ここでは日本語名のまま渡し、手動マッピングにフォールバック
            try:
                return self.classifier.classify_move(
                    move_name, user_name, opp_name, is_mega=False
                )
            except Exception:
                return int(ActionCategory.PHYSICAL_NEUTRAL)

        elif action.action_type == ActionType.SWITCH:
            incoming_name = action.switch_to_jp or ""
            # name_en を探す
            incoming_en = self._jp_to_en(incoming_name, state)
            try:
                return self.classifier.classify_switch(
                    user_name, incoming_en, opp_name
                )
            except Exception:
                return int(ActionCategory.SWITCH_SAFE)

        return int(ActionCategory.PHYSICAL_NEUTRAL)

    def _jp_to_en(self, name_jp: str, state: BattleState) -> str:
        """日本語名を英語名に変換（selected リストから探す）"""
        for poke in state.p1.selected:
            if poke.name_jp == name_jp:
                return poke.name_en
        return name_jp  # 見つからない場合はそのまま

    # ── 有効行動マスク生成 ─────────────────────────────────────

    def _build_valid_mask(
        self,
        available_actions: list[Action],
        state: BattleState,
    ) -> np.ndarray:
        """利用可能な行動が属するカテゴリを 1 にした valid_mask を返す"""
        mask = np.zeros(MAX_ACTIONS, dtype=np.float32)
        for action in available_actions:
            cat = self._action_to_category(action, state)
            mask[cat] = 1.0
        if mask.sum() == 0:
            mask[:] = 1.0   # 全無効は全有効にフォールバック
        return mask

    # ── 推薦メイン ────────────────────────────────────────────

    def recommend(
        self,
        state:     BattleState,
        top_k:     int   = 3,
        temperature: float = 0.5,
    ) -> list[Recommendation]:
        """
        現在の BattleState に対して上位 top_k 件の行動を推薦する。

        Args:
            state:       現在の対戦状態
            top_k:       返す推薦件数（デフォルト3）
            temperature: MCTS 選択温度（0 = 最善手のみ、1 = 訪問率比例）

        Returns:
            list[Recommendation]  スコア降順
        """
        available_actions = state.get_available_actions("p1")
        if not available_actions:
            logger.warning("利用可能な行動がありません")
            return []

        # 1. 状態ベクトル化
        try:
            state_vec = self.featurizer.encode(state)
        except Exception as e:
            logger.error(f"特徴量エンコード失敗: {e}")
            return []

        # 2. 有効マスク
        valid_mask = self._build_valid_mask(available_actions, state)

        # 3. MCTS 探索
        action_probs = self.mcts.search(state_vec, valid_mask, temperature)

        # 4. 各行動をカテゴリスコアでスコアリング
        #    複数の行動が同じカテゴリに属する場合は均等分割
        cat_action_map: dict[int, list[Action]] = {}
        for action in available_actions:
            cat = self._action_to_category(action, state)
            cat_action_map.setdefault(cat, []).append(action)

        scored: list[Recommendation] = []
        for cat, actions_in_cat in cat_action_map.items():
            cat_score = float(action_probs[cat])
            per_action_score = cat_score / len(actions_in_cat)
            for action in actions_in_cat:
                reason = self._make_reason(action, cat, state)
                scored.append(Recommendation(
                    action=action,
                    score=per_action_score,
                    category=cat,
                    reason=reason,
                ))

        scored.sort(key=lambda r: -r.score)
        return scored[:top_k]

    def _make_reason(
        self, action: Action, category: int, state: BattleState
    ) -> str:
        """行動の選択理由テキストを生成する"""
        active_p1 = state.p1.active
        active_p2 = state.p2.active
        p1_hp = f"HP{active_p1.hp_ratio:.0%}" if active_p1 else "?"
        p2_hp = f"HP{active_p2.hp_ratio:.0%}" if active_p2 else "?"
        cat_label = CATEGORY_LABELS.get(category, "不明")

        if action.action_type == ActionType.SWITCH:
            return (
                f"{cat_label}: 現在{p1_hp}→{action.switch_to_jp}へ交代"
                f"（相手{active_p2.name_jp if active_p2 else '?'} {p2_hp}）"
            )
        else:
            move_label = "メガシンカ+" if action.action_type == ActionType.MEGA else ""
            return (
                f"{cat_label}: {move_label}{action.move_name_jp}"
                f"（自{p1_hp} 相手{p2_hp}）"
            )

    # ── ファクトリ ────────────────────────────────────────────

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint_path: str | Path,
        num_sims: int = NUM_SIMS,
        device:   str = "cpu",
    ) -> "ChampionsAgent":
        """チェックポイントからエージェントを生成する"""
        import torch as _torch
        net   = PolicyValueNetwork()
        world = TransitionModel()
        load_checkpoint(net, None, checkpoint_path, device=device)
        # WorldModel は state_dict 直接保存形式
        world_ckpt = MODELS_DIR / "world_model_best.pt"
        if world_ckpt.exists():
            world.load_state_dict(
                _torch.load(str(world_ckpt), map_location=device, weights_only=True)
            )
            logger.info(f"WorldModel 読み込み: {world_ckpt}")
        net.eval()
        world.eval()
        logger.info(f"PolicyValueNet 読み込み: {checkpoint_path}")
        return cls(net, world, num_sims=num_sims, device=device)

    @classmethod
    def new(
        cls,
        num_sims: int = NUM_SIMS,
        device:   str = "cpu",
    ) -> "ChampionsAgent":
        """未学習モデルで初期化する（テスト用）"""
        net   = PolicyValueNetwork()
        world = TransitionModel()
        return cls(net, world, num_sims=num_sims, device=device)

    # ── 価値推定 ─────────────────────────────────────────────

    def evaluate(self, state: BattleState) -> float:
        """
        現在局面の勝利期待値を返す (-1.0〜+1.0)。
        p1 視点: +1.0 が有利, -1.0 が不利
        """
        try:
            state_vec = self.featurizer.encode(state)
        except Exception:
            return 0.0
        _, value = self.net.predict(state_vec, self.device)
        return value


# ===== 動作確認 =====

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from game_state import (
        BattleState, PlayerState, PokemonStatus, FieldState,
    )

    # テスト用 BattleState を構築
    def make_test_poke(name_jp, name_en, hp_ratio, moves):
        p = PokemonStatus(
            name_jp=name_jp, name_en=name_en,
            current_hp=int(hp_ratio * 300), max_hp=300,
        )
        p.move_names = moves
        return p

    poke_garchomp = make_test_poke(
        "ガブリアス", "garchomp", 0.9,
        ["じしん", "げきりん", "かみくだく", "つるぎのまい"]
    )
    poke_togekiss = make_test_poke(
        "トゲキッス", "togekiss", 0.8,
        ["エアスラッシュ", "マジカルシャイン", "はどうだん", "ほろびのうた"]
    )
    poke_opponent = make_test_poke(
        "ドヒドイデ", "toxapex", 0.7,
        ["ヘドロウェーブ", "どくどく", "リカバリー", "ほえる"]
    )

    p1 = PlayerState(player_id="p1", player_name="自分")
    p1.selected = [poke_garchomp, poke_togekiss]
    p1.active_index = 0

    p2 = PlayerState(player_id="p2", player_name="相手")
    p2.selected = [poke_opponent]
    p2.active_index = 0

    state = BattleState(turn=5, p1=p1, p2=p2)

    print("=== ChampionsAgent テスト ===")
    print(f"状態: {state.summary()}")
    print(f"利用可能な行動: {[str(a) for a in state.get_available_actions('p1')]}")
    print()

    # 学習済みモデルがあれば読み込む、なければ未学習モデルを使用
    ckpt = MODELS_DIR / "policy_value_best.pt"
    if ckpt.exists():
        agent = ChampionsAgent.from_checkpoint(ckpt, num_sims=50)
    else:
        print("(未学習モデルを使用)")
        agent = ChampionsAgent.new(num_sims=50)

    print(f"局面評価値: {agent.evaluate(state):.4f}")
    print()

    recs = agent.recommend(state, top_k=3)
    print("=== 推薦行動（上位3件）===")
    for i, r in enumerate(recs, 1):
        print(f"  {i}. score={r.score:.4f} | {r.reason}")

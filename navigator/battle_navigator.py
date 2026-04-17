"""
navigator/battle_navigator.py
==============================
Champions AI 対戦ナビゲーター メインクラス。

状態管理フロー:
  1. setup_my_party()    — 自パーティ登録
  2. setup_opponent()    — 相手パーティ登録 → 選出推薦返却
  3. start_battle()      — 選出確定・BattleState 初期化
  4. process_turn() × N — 毎ターン入力 → 推薦・相手情報更新

MCTS による行動推薦:
  - ChampionsAgent.recommend() で上位3件の ActionCategory 確率を取得
  - 各 ActionCategory に対応する具体的な行動（技名/交代先）をマッピング
  - MCTS スコアを合計100%に正規化して confidence として返す
"""

from __future__ import annotations
import sys
import logging
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "db"))
sys.path.insert(0, str(ROOT / "ai"))

from simulator.game_state import (  # type: ignore
    BattleState, PlayerState, PokemonStatus, FieldState,
    Action, ActionType, StatusCondition, Weather, Terrain,
)
from navigator.schemas import (
    MyPokemonInput, TurnInput, TurnOutput,
    ActionRecommendation, OpponentEstimateOut, SelectionResultOut,
)
from navigator.lead_selector import select_team, SelectionResult
from navigator.opponent_estimator import OpponentEstimator
from navigator.stats import get_actual_stats, load_base_stats

logger = logging.getLogger(__name__)

# ActionCategory ラベル（action_classifier.py の CATEGORY_LABELS と同期）
CATEGORY_LABELS: dict[int, str] = {
    0: "物理STAB",
    1: "物理有効",
    2: "物理等倍",
    3: "特殊STAB",
    4: "特殊有効",
    5: "特殊等倍",
    6: "変化（強化）",
    7: "変化（弱体）",
    8: "先制技",
    9: "メガシンカ",
    10: "タイプ有利交代",
    11: "安全交代",
}


class BattleNavigator:
    """
    Champions AI 対戦ナビゲーター。

    ChampionsAgent を内包し、バトル全体の状態管理と
    毎ターンの推薦生成を担当する。
    """

    def __init__(self, agent=None):
        """
        Args:
            agent: ChampionsAgent インスタンス（None の場合は推薦をスキップ）
        """
        self.agent = agent

        # パーティ情報
        self._my_party:         list[PokemonStatus] = []
        self._opp_party_names:  list[str]           = []

        # バトル状態
        self._state:            Optional[BattleState] = None
        self._battle_started:   bool = False
        self._opp_revealed:     list[str] = []   # 判明した相手ポケモン

        # 相手推測器（ポケモン名 → OpponentEstimator）
        self._estimators:       dict[str, OpponentEstimator] = {}

        # 自分の実数値キャッシュ
        self._my_stats_cache:   dict[str, dict[str, int]] = {}

    # ── セットアップ ───────────────────────────────────────────────

    def setup_my_party(self, inputs: list[MyPokemonInput]) -> None:
        """
        自分のパーティ情報を登録する。

        Args:
            inputs: MyPokemonInput のリスト（最大6体）
        """
        self._my_party = []
        self._my_stats_cache = {}

        for inp in inputs:
            poke = PokemonStatus(
                name_jp   = inp.name_jp,
                name_en   = inp.name_en,
                current_hp = 0,   # バトル開始時に実数値から算出
                max_hp     = 0,
            )
            poke.item_jp    = inp.item
            poke.item_en    = inp.item
            poke.ability_jp = inp.ability
            poke.nature     = inp.nature
            poke.gender     = inp.gender
            poke.evs        = {
                "H": inp.evs.H, "A": inp.evs.A, "B": inp.evs.B,
                "C": inp.evs.C, "D": inp.evs.D, "S": inp.evs.S,
            }
            poke.move_names = inp.moves[:4]
            poke.has_used_mega = False

            # HP実数値を計算
            base = load_base_stats(inp.name_jp)
            if base:
                stats = get_actual_stats(poke, base)
                poke.current_hp = stats["H"]
                poke.max_hp     = stats["H"]
                self._my_stats_cache[inp.name_jp] = stats
            else:
                poke.current_hp = 100
                poke.max_hp     = 100

            self._my_party.append(poke)

        logger.info(f"自パーティ登録: {[p.name_jp for p in self._my_party]}")

    def setup_opponent(self, names: list[str]) -> SelectionResultOut:
        """
        相手のパーティ情報を登録し、選出推薦を返す。

        Args:
            names: 相手6体の日本語名

        Returns:
            SelectionResultOut（選出3体・リード・スコア・理由）
        """
        self._opp_party_names = names
        self._estimators = {}

        if not self._my_party:
            logger.warning("先に setup_my_party を呼んでください")
            return SelectionResultOut(selected=[], lead="", scores={}, reasons={})

        result: SelectionResult = select_team(
            my_party       = self._my_party,
            opponent_names = names,
            lead_opponent  = names[0] if names else None,
        )
        return SelectionResultOut(
            selected = result.selected,
            lead     = result.lead,
            scores   = result.scores,
            reasons  = result.reasons,
        )

    def start_battle(
        self,
        selected:  list[str],
        lead_my:   str,
        lead_opp:  str,
    ) -> None:
        """
        選出確定・BattleState を初期化する。

        Args:
            selected:  選出3体の日本語名
            lead_my:   自分のリード
            lead_opp:  相手のリード（相手のポケモン名）
        """
        # 選出したポケモンの PokemonStatus を取得
        name_to_poke = {p.name_jp: p for p in self._my_party}
        selected_pokes = [name_to_poke[n] for n in selected if n in name_to_poke]

        # lead_my を先頭に並び替え
        ordered = sorted(
            selected_pokes,
            key=lambda p: 0 if p.name_jp == lead_my else 1,
        )

        # p1 (自分) の PlayerState
        p1 = PlayerState(player_id="p1", player_name="自分")
        p1.selected = ordered
        p1.active_index = 0

        # p2 (相手) の PlayerState — リードのポケモンだけ追加
        lead_opp_poke = PokemonStatus(
            name_jp   = lead_opp,
            name_en   = lead_opp,
            current_hp = 100,
            max_hp     = 100,
        )
        p2 = PlayerState(player_id="p2", player_name="相手")
        p2.selected = [lead_opp_poke]
        p2.active_index = 0

        self._state       = BattleState(turn=1, p1=p1, p2=p2)
        self._battle_started = True
        self._opp_revealed = [lead_opp]

        # 推測器を初期化
        self._estimators[lead_opp] = OpponentEstimator(lead_opp)

        logger.info(
            f"バトル開始: 自分={lead_my} vs 相手={lead_opp} "
            f"(選出={selected})"
        )

    # ── ターン処理 ────────────────────────────────────────────────

    def process_turn(self, turn_input: TurnInput) -> TurnOutput:
        """
        ターン入力を処理し、次の行動推薦を返す。

        Args:
            turn_input: TurnInput（ターンの観測情報）

        Returns:
            TurnOutput（上位3件の推薦 + 相手情報推測）
        """
        if not self._battle_started or self._state is None:
            return TurnOutput(
                recommendations=[],
                opponent_estimate=OpponentEstimateOut(),
                battle_state_summary="バトルが開始されていません。start_battle を呼んでください。",
            )

        # 1. BattleState を更新
        self._apply_turn_input(turn_input)

        # 2. 現在の相手ポケモンの推測器を取得/更新
        opp_active = self._state.p2.active
        opp_name   = opp_active.name_jp if opp_active else "不明"
        estimator  = self._estimators.get(opp_name)

        if estimator and turn_input.opponent_action:
            opp_act = turn_input.opponent_action
            # 技使用を記録
            if opp_act.move:
                estimator.observe_move_used(opp_act.move)
            # 相手の行動からダメージを受けた場合の自分HP情報を記録
            # （相手の耐久推測ではなく速度推測に利用）

        # アイテム確定
        if turn_input.opponent_item_activated and estimator:
            estimator.observe_item_activation(turn_input.opponent_item_activated)

        # 3. 行動推薦（MCTS agent）
        recommendations = self._get_recommendations()

        # 4. 相手推測情報
        opp_est = self._build_opponent_estimate(opp_name)

        # 5. サマリーテキスト
        summary = self._build_summary(turn_input.turn)

        return TurnOutput(
            recommendations      = recommendations,
            opponent_estimate    = opp_est,
            battle_state_summary = summary,
        )

    # ── 内部: BattleState 更新 ───────────────────────────────────

    def _apply_turn_input(self, inp: TurnInput) -> None:
        """TurnInput の観測情報を BattleState に反映する"""
        state = self._state
        p1    = state.p1
        p2    = state.p2

        # ターン番号を更新
        state.turn = inp.turn

        # 自分の交代
        if inp.my_switch:
            for i, poke in enumerate(p1.selected):
                if poke.name_jp == inp.my_switch:
                    p1.active_index = i
                    break

        # 相手の交代（初めて見るポケモンなら追加）
        if inp.opponent_switch:
            opp_name = inp.opponent_switch
            if opp_name not in self._opp_revealed:
                self._opp_revealed.append(opp_name)
                new_poke = PokemonStatus(
                    name_jp    = opp_name,
                    name_en    = opp_name,
                    current_hp = 100,
                    max_hp     = 100,
                )
                p2.selected.append(new_poke)
                self._estimators[opp_name] = OpponentEstimator(opp_name)
            # 交代先をアクティブに
            for i, poke in enumerate(p2.selected):
                if poke.name_jp == opp_name:
                    p2.active_index = i
                    break

        # 相手の残HP更新
        if inp.opponent_hp_pct is not None and p2.active:
            p2.active.current_hp = inp.opponent_hp_pct
            p2.active.max_hp     = 100  # %ベースで管理

        # 自分の残HP更新
        if inp.my_hp_after is not None and p1.active:
            p1.active.current_hp = inp.my_hp_after

        # 状態異常の更新
        if inp.my_status and p1.active:
            p1.active.status = StatusCondition.from_showdown(inp.my_status) \
                if inp.my_status != "none" else StatusCondition.NONE

        if inp.opponent_status and p2.active:
            p2.active.status = StatusCondition.from_showdown(inp.opponent_status) \
                if inp.opponent_status != "none" else StatusCondition.NONE

        # 持ち物消費
        if inp.my_item_consumed and p1.active:
            p1.active.item_jp = None
            p1.active.item_en = None

        # メガシンカ
        if inp.my_mega and p1.active:
            p1.active.has_used_mega = True
            p1.mega_used = True
        if inp.opp_mega and p2.active:
            p2.active.has_used_mega = True
            p2.mega_used = True

    # ── 内部: 推薦生成 ────────────────────────────────────────────

    def _get_recommendations(self) -> list[ActionRecommendation]:
        """MCTS agent から推薦を取得して ActionRecommendation に変換する"""
        if self.agent is None or self._state is None:
            return self._fallback_recommendations()

        try:
            recs = self.agent.recommend(self._state, top_k=3, temperature=0.5)
        except Exception as e:
            logger.error(f"MCTS 推薦エラー: {e}")
            return self._fallback_recommendations()

        if not recs:
            return self._fallback_recommendations()

        # スコアを正規化して confidence% に変換
        total = sum(r.score for r in recs) or 1.0
        results: list[ActionRecommendation] = []
        for rec in recs:
            confidence = round(rec.score / total * 100, 1)
            cat_label  = CATEGORY_LABELS.get(rec.category, "不明")
            results.append(ActionRecommendation(
                action     = self._action_label(rec.action),
                confidence = confidence,
                category   = cat_label,
                reason     = rec.reason,
            ))
        return results

    def _action_label(self, action: Action) -> str:
        """Action を表示用テキストに変換"""
        if action.action_type == ActionType.SWITCH:
            return f"交代: {action.switch_to_jp or '?'}"
        elif action.action_type == ActionType.MEGA:
            return f"メガシンカ+{action.move_name_jp or '?'}"
        else:
            return action.move_name_jp or "?"

    def _fallback_recommendations(self) -> list[ActionRecommendation]:
        """agent が使えない場合の簡易推薦（タイプ相性ベース）"""
        if self._state is None:
            return []

        available = self._state.get_available_actions("p1")
        if not available:
            return []

        # 利用可能な行動を均等分割
        n = min(len(available), 3)
        per = round(100.0 / n, 1)
        results = []
        for i, action in enumerate(available[:n]):
            results.append(ActionRecommendation(
                action     = self._action_label(action),
                confidence = per,
                category   = "-",
                reason     = "（モデル未読み込み - タイプ相性参照推奨）",
            ))
        return results

    # ── 内部: 相手推測整形 ────────────────────────────────────────

    def _build_opponent_estimate(self, opp_name: str) -> OpponentEstimateOut:
        """相手ポケモンの推測情報を OpponentEstimateOut に変換"""
        estimator = self._estimators.get(opp_name)
        if estimator is None:
            return OpponentEstimateOut()
        est = estimator.get_estimate()
        return OpponentEstimateOut(
            item            = est.item,
            item_confidence = round(est.item_confidence, 2),
            speed_tier      = est.speed_tier,
            bulk_tendency   = est.bulk_tendency,
            is_choice_item  = est.is_choice_item,
            choice_move     = est.choice_move,
        )

    # ── 内部: サマリーテキスト ────────────────────────────────────

    def _build_summary(self, turn: int) -> str:
        """現在の状態をテキストで要約する"""
        if self._state is None:
            return "状態不明"

        p1 = self._state.p1
        p2 = self._state.p2

        my_active  = p1.active
        opp_active = p2.active

        my_name  = my_active.name_jp  if my_active  else "?"
        opp_name = opp_active.name_jp if opp_active else "?"

        if my_active:
            my_hp_str = f"{my_active.current_hp}/{my_active.max_hp}"
        else:
            my_hp_str = "?"

        if opp_active:
            opp_hp_str = f"{opp_active.current_hp}%"
        else:
            opp_hp_str = "?"

        alive_my  = sum(1 for p in p1.selected if not p.is_fainted)
        alive_opp = len(self._opp_revealed)

        return (
            f"ターン{turn} | "
            f"自:{my_name}({my_hp_str}) vs 相手:{opp_name}(残{opp_hp_str}) | "
            f"残ポケ 自{alive_my}体 / 相手判明{alive_opp}体"
        )

    # ── 状態取得 ────────────────────────────────────────────────

    def get_state_info(self) -> dict:
        """現在の状態情報を辞書で返す"""
        if self._state is None:
            return {"battle_started": False}

        p1 = self._state.p1
        p2 = self._state.p2
        my_active  = p1.active
        opp_active = p2.active

        return {
            "turn":         self._state.turn,
            "my_active":    my_active.name_jp  if my_active  else None,
            "opp_active":   opp_active.name_jp if opp_active else None,
            "my_hp":        f"{my_active.current_hp}/{my_active.max_hp}" if my_active else None,
            "opp_hp_pct":   opp_active.current_hp if opp_active else None,
            "my_selected":  [p.name_jp for p in p1.selected],
            "opp_revealed": self._opp_revealed,
            "battle_started": self._battle_started,
        }

    def reset(self) -> None:
        """ナビゲーターをリセット（次のバトルに備える）"""
        self._my_party        = []
        self._opp_party_names = []
        self._state           = None
        self._battle_started  = False
        self._opp_revealed    = []
        self._estimators      = {}
        self._my_stats_cache  = {}
        logger.info("ナビゲーターをリセットしました")

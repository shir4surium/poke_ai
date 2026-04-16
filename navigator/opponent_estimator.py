"""
navigator/opponent_estimator.py
================================
対戦中の観測情報から相手ポケモンの持ち物・耐久・素早さを推測する。

ターンをまたいで情報を蓄積し、推測精度を高めていく。
1ポケモン1インスタンスで使用する。

観測できる情報:
  - 与えたダメージ% → 防御/特防実数値の範囲を絞り込む
  - 行動順         → 素早さ実数値の範囲を絞り込む
  - 使用した技      → こだわり系アイテム推測
  - HP 回復       → きのみ/たべのこし/黒いヘドロ等の推測
  - アイテム発動   → 確定
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ===== 結果データクラス =====

@dataclass
class OpponentEstimate:
    """相手ポケモンの推測情報"""
    # 持ち物
    item:             Optional[str] = None   # 確定持ち物（または最有力候補）
    item_confidence:  float         = 0.0    # 持ち物の確信度 0.0〜1.0

    # 防御実数値の推定範囲
    phys_def_range:   tuple[int, int] = (1, 999)   # 物理防御
    spec_def_range:   tuple[int, int] = (1, 999)   # 特殊防御

    # 素早さの推定範囲
    spd_range:        tuple[int, int] = (1, 999)

    # テキスト説明
    bulk_tendency:    Optional[str] = None   # "HB特化傾向" などの説明
    speed_tier:       Optional[str] = None   # "最速ガブリアスより速い" など

    # こだわり判定
    is_choice_item:   bool = False
    choice_move:      Optional[str] = None   # 縛られている技名（推測）


# ===== 推測器 =====

# こだわり系アイテムの候補リスト
_CHOICE_ITEMS = ["こだわりスカーフ", "こだわりハチマキ", "こだわりメガネ"]

# HP回復から推測できるアイテム
_RECOVERY_ITEM_HINTS: dict[str, str] = {
    "1/4": "たべのこし",
    "1/16": "たべのこし/くろいヘドロ（推測）",
    "half": "きのみ系",
}

# チャンピオンズで頻出する持ち物リスト（優先度順）
_COMMON_ITEMS = [
    "こだわりスカーフ", "こだわりハチマキ", "こだわりメガネ",
    "いのちのたま", "たべのこし", "とつげきチョッキ",
    "ラムのみ", "オボンのみ", "ウイのみ",
    "ひかりのこな", "きあいのタスキ",
]


class OpponentEstimator:
    """
    1ポケモンの観測情報を蓄積して推測を更新する。

    毎ターン observe_* メソッドを呼んで情報を入力し、
    get_estimate() で現在の推測結果を取得する。
    """

    def __init__(self, pokemon_name: str):
        self.name = pokemon_name

        # 推測状態
        self._item:            Optional[str] = None
        self._item_confirmed:  bool          = False
        self._item_confidence: float         = 0.0

        self._phys_def_range:  tuple[int, int] = (1, 999)
        self._spec_def_range:  tuple[int, int] = (1, 999)
        self._spd_range:       tuple[int, int] = (1, 999)

        # こだわり判定
        self._move_history:     list[str] = []
        self._choice_suspected: bool = False

        # テキスト説明
        self._speed_notes:  list[str] = []
        self._bulk_notes:   list[str] = []

    # ── 観測メソッド ─────────────────────────────────────────────

    def observe_damage_dealt(
        self,
        atk_stat:    int,
        power:       int,
        type_eff:    float,
        stab:        float,
        damage_pct:  float,         # 0.0〜1.0
        defender_max_hp: int,
        is_physical: bool = True,
    ) -> None:
        """
        相手に与えたダメージ観測から、防御/特防実数値の範囲を更新する。

        Args:
            atk_stat:         自分の攻撃（物理→A、特殊→C）実数値
            power:            技の基礎威力
            type_eff:         タイプ相性倍率
            stab:             STAB倍率 (1.0 or 1.5)
            damage_pct:       観測HP変化% (e.g. 0.30)
            defender_max_hp:  相手の最大HP推定値
            is_physical:      物理技かどうか
        """
        from navigator.damage_calc import estimate_def_stat_range

        new_range = estimate_def_stat_range(
            atk_stat, power, type_eff, stab, damage_pct, defender_max_hp
        )

        if is_physical:
            # 既存範囲と新範囲の共通部分で絞り込む
            self._phys_def_range = (
                max(self._phys_def_range[0], new_range[0]),
                min(self._phys_def_range[1], new_range[1]),
            )
            # 逆転を防ぐ
            if self._phys_def_range[0] > self._phys_def_range[1]:
                self._phys_def_range = new_range
            self._update_bulk_note("phys")
        else:
            self._spec_def_range = (
                max(self._spec_def_range[0], new_range[0]),
                min(self._spec_def_range[1], new_range[1]),
            )
            if self._spec_def_range[0] > self._spec_def_range[1]:
                self._spec_def_range = new_range
            self._update_bulk_note("spec")

    def observe_turn_order(
        self,
        my_speed:     int,
        moved_first:  bool,
        my_priority:  int = 0,
        opp_priority: int = 0,
        trick_room:   bool = False,
    ) -> None:
        """行動順の観察から素早さ範囲を絞り込む"""
        from navigator.damage_calc import compare_speed

        result = compare_speed(my_speed, moved_first, my_priority, opp_priority, trick_room)
        new_min = result["opp_speed_min"]
        new_max = result["opp_speed_max"]

        self._spd_range = (
            max(self._spd_range[0], new_min),
            min(self._spd_range[1], new_max),
        )
        if self._spd_range[0] > self._spd_range[1]:
            self._spd_range = (new_min, new_max)

        self._speed_notes.append(result.get("note", ""))
        self._update_speed_tier_note()

    def observe_move_used(self, move_name: str) -> None:
        """
        相手が使用した技を記録する。
        2ターン以上異なる技 → こだわり解除（または非こだわり）
        同じ技を2回以上 → こだわりの可能性上昇
        """
        if not self._item_confirmed:
            self._move_history.append(move_name)

            # 同じ技を2回連続で使用
            if len(self._move_history) >= 2 and len(set(self._move_history[-2:])) == 1:
                self._choice_suspected = True
                if not self._item:
                    self._item = "こだわり系（推測）"
                    self._item_confidence = 0.6

            # 異なる技を使用 → こだわりでない可能性
            if len(self._move_history) >= 2 and len(set(self._move_history[-2:])) > 1:
                self._choice_suspected = False
                if self._item == "こだわり系（推測）":
                    self._item = None
                    self._item_confidence = 0.0

    def observe_item_activation(self, item_name: str) -> None:
        """アイテムの発動を観測（確定情報）"""
        self._item           = item_name
        self._item_confirmed = True
        self._item_confidence = 1.0

    def observe_hp_recovery(self, recovered_pct: float) -> None:
        """
        ターン終了時の HP 回復量から持ち物を推測する。

        Args:
            recovered_pct: 回復した HP 割合 (0.0〜1.0)
        """
        if self._item_confirmed:
            return

        if 0.06 <= recovered_pct <= 0.07:
            # たべのこし: 1/16 = 6.25%
            self._item = "たべのこし（推測）"
            self._item_confidence = 0.75
        elif 0.24 <= recovered_pct <= 0.26:
            # オボンのみ等 1/4 回復
            self._item = "きのみ（オボン等）（推測）"
            self._item_confidence = 0.6

    # ── 内部更新 ─────────────────────────────────────────────────

    def _update_bulk_note(self, stat_type: str) -> None:
        """耐久傾向テキストを更新"""
        pd = self._phys_def_range
        sd = self._spec_def_range
        notes = []
        if pd[1] < 999:
            notes.append(f"物理防御推定{pd[0]}〜{pd[1]}")
        if sd[1] < 999:
            notes.append(f"特殊防御推定{sd[0]}〜{sd[1]}")
        self._bulk_notes = notes

    def _update_speed_tier_note(self) -> None:
        """素早さ段階テキストを更新"""
        mn, mx = self._spd_range
        if mx < 999:
            note = f"素早さ実数値 {mn}〜{mx}"
        elif mn > 1:
            note = f"素早さ実数値 {mn} 以上"
        else:
            note = None
        if note:
            self._speed_notes = [note]

    # ── 推測結果 ─────────────────────────────────────────────────

    def get_estimate(self) -> OpponentEstimate:
        """現在の推測情報をまとめて返す"""
        bulk_tendency = "、".join(self._bulk_notes) if self._bulk_notes else None
        speed_tier    = self._speed_notes[-1] if self._speed_notes else None

        return OpponentEstimate(
            item              = self._item,
            item_confidence   = self._item_confidence,
            phys_def_range    = self._phys_def_range,
            spec_def_range    = self._spec_def_range,
            spd_range         = self._spd_range,
            bulk_tendency     = bulk_tendency,
            speed_tier        = speed_tier,
            is_choice_item    = self._choice_suspected,
            choice_move       = self._move_history[-1] if self._choice_suspected and self._move_history else None,
        )


# ===== 動作確認 =====

if __name__ == "__main__":
    estimator = OpponentEstimator("カイリュー")

    # ターン1: 自分が先行（S169 > 相手）
    estimator.observe_turn_order(my_speed=169, moved_first=True)

    # ターン1: じしん (A182) でカイリューに30%ダメージ
    estimator.observe_damage_dealt(
        atk_stat=182, power=100, type_eff=1.0, stab=1.5,
        damage_pct=0.30, defender_max_hp=167, is_physical=True
    )

    # ターン2: 同じ技「ダブルウイング」を使用 → こだわり疑い
    estimator.observe_move_used("ダブルウイング")
    estimator.observe_move_used("ダブルウイング")

    est = estimator.get_estimate()
    print("=== 推測結果 ===")
    print(f"持ち物:   {est.item} (確信度 {est.item_confidence:.0%})")
    print(f"物理防御: {est.phys_def_range[0]}〜{est.phys_def_range[1]}")
    print(f"素早さ:   {est.spd_range[0]}〜{est.spd_range[1]}")
    print(f"耐久傾向: {est.bulk_tendency}")
    print(f"速度段階: {est.speed_tier}")
    print(f"こだわり: {est.is_choice_item} (縛り技: {est.choice_move})")

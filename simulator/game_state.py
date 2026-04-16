"""
Phase 3-A: ゲーム状態定義

チャンピオンズの1対戦における状態を表現するデータ構造。

入力仕様（ユーザー要件より）:
  - 相手パーティ（各ポケモンのステータス・技・持ち物）
  - こちらのパーティ・選出ポケモン・ステータス・技・持ち物
  - ターン毎の行動とその結果

出力仕様:
  - 取り得る選択（技/交代）を優先度順に上位3候補
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ===== 定数 =====

MAX_PARTY     = 6   # パーティ最大数
SELECT_SIZE   = 3   # 選出数
MAX_MOVES     = 4   # 技の最大数
MAX_TURNS     = 200 # ターン上限（制限時間20分の近似）


class StatusCondition(str, Enum):
    """状態異常"""
    NONE  = "なし"
    BRN   = "やけど"
    PAR   = "まひ"
    SLP   = "ねむり"
    PSN   = "どく"
    TOX   = "もうどく"
    FRZ   = "こおり"

    @classmethod
    def from_showdown(cls, code: str) -> "StatusCondition":
        """Showdownログのコードから変換"""
        _MAP = {
            "brn": cls.BRN, "par": cls.PAR, "slp": cls.SLP,
            "psn": cls.PSN, "tox": cls.TOX, "frz": cls.FRZ,
        }
        return _MAP.get(code, cls.NONE)


class MoveCategory(str, Enum):
    """技カテゴリ"""
    PHYSICAL = "物理"
    SPECIAL  = "特殊"
    STATUS   = "変化"


class ActionType(str, Enum):
    """行動種別"""
    MOVE   = "技"
    SWITCH = "交代"
    MEGA   = "メガシンカ+技"


# ===== 技データ =====

@dataclass
class MoveData:
    """技の基本データ（DBから引いた静的情報）"""
    name_jp:    str
    name_en:    str
    type_jp:    str
    category:   MoveCategory
    power:      Optional[int]     # 変化技はNone
    accuracy:   Optional[int]     # 必中はNone
    pp:         int
    priority:   int = 0
    effect:     Optional[str] = None
    effect_chance: Optional[int] = None


# ===== ポケモン状態 =====

@dataclass
class PokemonStatus:
    """
    対戦中の1体のポケモンの状態。

    種族値・タイプ・特性はDBから引いた静的情報（StaticPokemon）に持たせ、
    こちらには対戦中に変化するダイナミックな情報のみ持つ。
    """
    # --- 識別情報 ---
    name_jp:     str
    name_en:     str
    is_mega:     bool = False

    # --- HP ---
    current_hp:  int  = 0
    max_hp:      int  = 0

    @property
    def hp_ratio(self) -> float:
        return self.current_hp / self.max_hp if self.max_hp > 0 else 0.0

    @property
    def is_fainted(self) -> bool:
        return self.current_hp <= 0

    # --- 状態異常 ---
    status: StatusCondition = StatusCondition.NONE

    # --- 能力ランク (-6 〜 +6) ---
    rank_atk:  int = 0
    rank_def:  int = 0
    rank_spa:  int = 0
    rank_spd:  int = 0
    rank_spe:  int = 0
    rank_acc:  int = 0
    rank_eva:  int = 0

    # --- 技PP残量 ---
    move_names: list[str] = field(default_factory=list)  # 技名リスト（最大4）
    move_pp:    list[int] = field(default_factory=list)  # 各技の残PP

    # --- 持ち物 ---
    item_jp: Optional[str] = None
    item_en: Optional[str] = None

    # --- 特性 ---
    ability_jp: Optional[str] = None

    # --- フラグ ---
    has_used_mega: bool = False   # このポケモンでメガシンカを使用済みか

    # --- ナビゲーター用: 育成情報 ---
    evs: dict = field(default_factory=lambda: {"H":0,"A":0,"B":0,"C":0,"D":0,"S":0})
    nature: str = "まじめ"   # 性格名（ニュートラルデフォルト）
    gender: str = "-"         # "♂" / "♀" / "-"

    def rank_multiplier(self, rank: int) -> float:
        """能力ランクから実際の倍率を計算（攻撃/防御/特攻/特防/素早さ用）"""
        if rank >= 0:
            return (2 + rank) / 2
        else:
            return 2 / (2 - rank)

    def accuracy_multiplier(self, rank: int) -> float:
        """命中・回避ランクから倍率を計算"""
        if rank >= 0:
            return (3 + rank) / 3
        else:
            return 3 / (3 - rank)


# ===== プレイヤー状態 =====

@dataclass
class PlayerState:
    """
    1プレイヤーの対戦中状態。
    p1（自分）・p2（相手）の両方を同じクラスで表現する。
    """
    player_id: str      # "p1" or "p2"
    player_name: str    # プレイヤー名

    # --- パーティ（選出前の全体）---
    party: list[PokemonStatus] = field(default_factory=list)

    # --- 選出済みポケモン (最大3体) ---
    selected: list[PokemonStatus] = field(default_factory=list)

    # --- 場に出ているポケモン ---
    active_index: int = 0  # selected 内のインデックス

    @property
    def active(self) -> Optional[PokemonStatus]:
        if 0 <= self.active_index < len(self.selected):
            return self.selected[self.active_index]
        return None

    # --- メガシンカ使用済みか（1対戦1回） ---
    mega_used: bool = False

    # フィールド効果（天気・地形）はBattleStateで管理


# ===== フィールド状態 =====

class Weather(str, Enum):
    """天気"""
    NONE    = "なし"
    SUNNY   = "はれ"
    RAIN    = "あめ"
    SAND    = "すなあらし"
    HAIL    = "あられ"
    HEAVY   = "おおあめ"
    HARSH   = "おおひでり"
    WIND    = "らんふうのよる"

class Terrain(str, Enum):
    """フィールド"""
    NONE     = "なし"
    ELECTRIC = "エレキフィールド"
    GRASSY   = "グラスフィールド"
    PSYCHIC  = "サイコフィールド"
    MISTY    = "ミストフィールド"


@dataclass
class FieldState:
    """フィールド全体の状態"""
    weather:          Weather = Weather.NONE
    weather_turns:    int     = 0
    terrain:          Terrain = Terrain.NONE
    terrain_turns:    int     = 0

    # 壁（サイドごと）
    reflect:     dict[str, int] = field(default_factory=dict)   # {"p1": 残ターン, "p2": ...}
    light_screen: dict[str, int] = field(default_factory=dict)
    aurora_veil:  dict[str, int] = field(default_factory=dict)

    # トリックルーム
    trick_room:       bool  = False
    trick_room_turns: int   = 0


# ===== 行動 =====

@dataclass
class Action:
    """1ターンの行動（AI出力の1候補）"""
    action_type:  ActionType
    move_name_jp: Optional[str]  = None   # 技名（MOVE/MEGA時）
    switch_to_jp: Optional[str]  = None   # 交代先ポケモン名（SWITCH時）
    priority_score: float        = 0.0    # AIが計算した優先度スコア
    reason:       str            = ""     # 選択理由（デバッグ用）

    def __str__(self) -> str:
        if self.action_type == ActionType.SWITCH:
            return f"交代→{self.switch_to_jp} (score={self.priority_score:.3f})"
        elif self.action_type == ActionType.MEGA:
            return f"メガシンカ+{self.move_name_jp} (score={self.priority_score:.3f})"
        else:
            return f"{self.move_name_jp} (score={self.priority_score:.3f})"


# ===== 対戦状態（メイン） =====

@dataclass
class BattleState:
    """
    1対戦の完全な状態。

    ターン毎にこのオブジェクトを更新していく。
    AIはこの状態を受け取り、Action候補を返す。
    """
    turn:       int = 0
    p1:         PlayerState = field(default_factory=lambda: PlayerState("p1", ""))
    p2:         PlayerState = field(default_factory=lambda: PlayerState("p2", ""))
    field_state: FieldState = field(default_factory=FieldState)
    is_terminal: bool = False  # 対戦終了フラグ
    winner:     Optional[str] = None  # "p1" or "p2"

    # ターン履歴（最新Nターン分を保持）
    action_history: list[dict] = field(default_factory=list)

    def get_available_actions(self, player_id: str) -> list[Action]:
        """
        指定プレイヤーが取れる全行動を列挙する。
        - 技（場に出ているポケモンの技リスト）
        - 交代（瀕死でない控えポケモン）
        - メガシンカ+技（未使用の場合のみ）
        """
        player = self.p1 if player_id == "p1" else self.p2
        actions = []

        active = player.active
        if active is None or active.is_fainted:
            return actions

        # 技行動
        for move_name in active.move_names:
            actions.append(Action(
                action_type=ActionType.MOVE,
                move_name_jp=move_name,
            ))
            # メガシンカ未使用の場合は同じ技でMEGAバリアントも追加
            if not player.mega_used and not active.is_mega:
                actions.append(Action(
                    action_type=ActionType.MEGA,
                    move_name_jp=move_name,
                ))

        # 交代行動（瀕死でない控えポケモン）
        for i, poke in enumerate(player.selected):
            if i != player.active_index and not poke.is_fainted:
                actions.append(Action(
                    action_type=ActionType.SWITCH,
                    switch_to_jp=poke.name_jp,
                ))

        return actions

    def apply_action_history(self, turn: int, p1_action: dict, p2_action: dict, events: list[dict]):
        """ターン履歴を追記する"""
        self.action_history.append({
            "turn":      turn,
            "p1_action": p1_action,
            "p2_action": p2_action,
            "events":    events,
        })
        # 最新50ターン分だけ保持
        if len(self.action_history) > 50:
            self.action_history = self.action_history[-50:]

    def summary(self) -> str:
        """現在状態のサマリー文字列"""
        p1a = self.p1.active
        p2a = self.p2.active
        p1_str = f"{p1a.name_jp} HP:{p1a.hp_ratio:.0%}" if p1a else "不在"
        p2_str = f"{p2a.name_jp} HP:{p2a.hp_ratio:.0%}" if p2a else "不在"
        return (
            f"Turn {self.turn} | "
            f"自: {p1_str} | "
            f"相: {p2_str} | "
            f"天気: {self.field_state.weather.value}"
        )

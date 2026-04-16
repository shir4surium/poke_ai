"""
navigator/schemas.py
====================
対戦ナビゲーター API の Pydantic 入出力スキーマ定義。

すべての API エンドポイントはこのスキーマを使って JSON を受け取り、
JSON を返す。将来の映像解析プログラムはこれらの型に合わせてデータを送る。
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ===== 入力スキーマ =====

class EvSpread(BaseModel):
    """努力値振り（合計510以内が標準だが強制はしない）"""
    H: int = 0
    A: int = 0
    B: int = 0
    C: int = 0
    D: int = 0
    S: int = 0


class MyPokemonInput(BaseModel):
    """
    自分のポケモン1体の情報（バトル開始前に入力）。

    Example:
        {
            "name_jp": "ガブリアス",
            "name_en": "garchomp",
            "item": "こだわりスカーフ",
            "ability": "さめはだ",
            "gender": "♂",
            "nature": "ようき",
            "evs": {"H": 0, "A": 252, "B": 0, "C": 0, "D": 4, "S": 252},
            "moves": ["じしん", "げきりん", "かみくだく", "つるぎのまい"],
            "can_mega": false
        }
    """
    name_jp:  str
    name_en:  str
    item:     Optional[str] = None
    ability:  Optional[str] = None
    gender:   str           = "-"       # "♂" / "♀" / "-"
    nature:   str           = "まじめ"
    evs:      EvSpread      = Field(default_factory=EvSpread)
    moves:    list[str]     = Field(default_factory=list)  # 技名（日本語）、最大4
    can_mega: bool          = False     # メガシンカ可能か


class SetupPartyRequest(BaseModel):
    """自分のパーティ登録リクエスト（最大6体）"""
    my_party: list[MyPokemonInput]


class SetupOpponentRequest(BaseModel):
    """
    相手のパーティ登録リクエスト。
    バトル開始前に相手の選出6体を入力する。

    Example:
        {"opponent_party": ["カイリュー", "ドヒドイデ", "テッカグヤ",
                            "ミミッキュ", "ウーラオス", "トゲキッス"]}
    """
    opponent_party: list[str]   # 相手6体の日本語名


class StartBattleRequest(BaseModel):
    """
    選出確定・バトル開始リクエスト。
    setup_opponent の推薦を参考にして選出を確定する。

    Example:
        {
            "selected":  ["ガブリアス", "ミミッキュ", "テッカグヤ"],
            "lead_my":   "ガブリアス",
            "lead_opp":  "カイリュー"
        }
    """
    selected:  list[str]   # 選出3体（日本語名）
    lead_my:   str         # 自分のリード
    lead_opp:  str         # 相手のリード


class AbilityActivation(BaseModel):
    """特性発動イベント（ターン開始時）"""
    player:  str    # "p1"（自分）/ "p2"（相手）
    ability: str    # 特性名
    pokemon: str    # 発動したポケモン名


class OpponentActionInput(BaseModel):
    """
    相手が行った行動（ターン結果入力）。

    move:        相手が使用した技名（日本語）
    my_hp_after: 相手の技を受けた後の自分の残HP実数値
                 （チャンピオンズでは実数値で表示されるため実数値で入力）
    """
    move:         Optional[str] = None
    my_hp_after:  Optional[int] = None   # 自分の残HP実数値


class TurnInput(BaseModel):
    """
    毎ターンの入力データ。将来の映像解析プログラムが POST する形式。

    Fields:
        turn:                    現在のターン数
        ability_activations:     特性発動リスト（複数体同時可）
        my_switch:               自分が交代したポケモン名（交代した場合）
        opponent_switch:         相手が交代したポケモン名（交代した場合）
        opponent_hp_pct:         ターン終了後の相手残HP%（整数、切り捨て）
        my_hp_after:             自分の残HP実数値（ターン終了後）
        my_status:               自分の状態異常変化（"まひ"/"やけど"/"ねむり"/"どく"/"もうどく"/"こおり"/"none"）
        opponent_status:         相手の状態異常変化
        opponent_action:         相手の行動内容
        my_item_consumed:        自分のアイテムが消費された場合のアイテム名
        opponent_item_activated: 相手のアイテムが発動した場合のアイテム名

    Example:
        {
            "turn": 1,
            "ability_activations": [
                {"player": "p2", "ability": "いかく", "pokemon": "カイリュー"}
            ],
            "opponent_hp_pct": 72,
            "my_hp_after": 212,
            "opponent_action": {
                "move": "ダブルウイング",
                "my_hp_after": 212
            }
        }
    """
    turn:                    int
    ability_activations:     list[AbilityActivation] = Field(default_factory=list)
    my_switch:               Optional[str] = None
    opponent_switch:         Optional[str] = None
    opponent_hp_pct:         Optional[int] = None     # 相手残HP%（0〜100整数）
    my_hp_after:             Optional[int] = None     # 自分の残HP実数値
    my_status:               Optional[str] = None
    opponent_status:         Optional[str] = None
    opponent_action:         Optional[OpponentActionInput] = None
    my_item_consumed:        Optional[str] = None
    opponent_item_activated: Optional[str] = None


# ===== 出力スキーマ =====

class ActionRecommendation(BaseModel):
    """
    推薦行動1件。

    action:     行動の説明（技名 or 「交代: ○○」）
    confidence: 信頼度%（小数点1桁、例: 65.2）
    category:   カテゴリラベル（"物理STAB" / "特殊有効" / "安全交代" など）
    reason:     選択理由テキスト
    """
    action:     str
    confidence: float   # 0.0〜100.0
    category:   str
    reason:     str


class OpponentEstimateOut(BaseModel):
    """
    相手ポケモンの推測情報。

    item:             推測した持ち物名（未確定なら末尾に「（推測）」）
    item_confidence:  持ち物の確信度 0.0〜1.0
    speed_tier:       素早さ段階の説明
    bulk_tendency:    耐久傾向の説明
    is_choice_item:   こだわり系アイテム疑いあり
    choice_move:      こだわり縛り技の推測（あれば）
    """
    item:             Optional[str] = None
    item_confidence:  float         = 0.0
    speed_tier:       Optional[str] = None
    bulk_tendency:    Optional[str] = None
    is_choice_item:   bool          = False
    choice_move:      Optional[str] = None


class SelectionResultOut(BaseModel):
    """選出推薦結果（/setup/opponent の返却値）"""
    selected: list[str]
    lead:     str
    scores:   dict[str, float]
    reasons:  dict[str, str]


class TurnOutput(BaseModel):
    """
    毎ターンの出力データ。

    recommendations:      上位3件の行動推薦
    opponent_estimate:    相手ポケモンの推測情報
    battle_state_summary: 現在の状況テキストサマリー
    """
    recommendations:      list[ActionRecommendation]
    opponent_estimate:    OpponentEstimateOut
    battle_state_summary: str


class StateResponse(BaseModel):
    """現在の対戦状態（/battle/state の返却値）"""
    turn:           int
    my_active:      Optional[str]
    opp_active:     Optional[str]
    my_hp:          Optional[str]   # "212/301 (70%)" 形式
    opp_hp_pct:     Optional[int]
    my_selected:    list[str]
    opp_revealed:   list[str]       # これまでに判明した相手のポケモン
    battle_started: bool

"""
Phase 3-B: 特徴量エンジニアリング

BattleState → 数値ベクトルに変換する。
AIネットワークへの入力・MCTSの状態表現として使用する。

ベクトル設計:
  自分の場のポケモン:   34次元
  相手の場のポケモン:   34次元
  自分の控え(2体分):   34×2 = 68次元
  相手の控え(2体分):   34×2 = 68次元
  フィールド状態:       16次元
  ターン情報:            2次元
  合計:               222次元
"""

from __future__ import annotations
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "db"))
from schema import get_connection
from game_state import BattleState, PokemonStatus, FieldState, Weather, Terrain, StatusCondition


# ===== タイプID マッピング =====
TYPE_IDS: dict[str, int] = {
    "ノーマル": 0, "ほのお": 1, "みず": 2, "でんき": 3,
    "くさ": 4,   "こおり": 5, "かくとう": 6, "どく": 7,
    "じめん": 8, "ひこう": 9, "エスパー": 10, "むし": 11,
    "いわ": 12,  "ゴースト": 13, "ドラゴン": 14, "あく": 15,
    "はがね": 16,"フェアリー": 17,
    # DB英語名との互換
    "Normal": 0,  "Fire": 1,  "Water": 2,  "Electric": 3,
    "Grass": 4,   "Ice": 5,   "Fighting": 6, "Poison": 7,
    "Ground": 8,  "Flying": 9, "Psychic": 10, "Bug": 11,
    "Rock": 12,   "Ghost": 13, "Dragon": 14, "Dark": 15,
    "Steel": 16,  "Fairy": 17,
}
NUM_TYPES = 18

STATUS_IDS: dict[str, int] = {
    StatusCondition.NONE: 0, StatusCondition.BRN: 1, StatusCondition.PAR: 2,
    StatusCondition.SLP: 3,  StatusCondition.PSN: 4, StatusCondition.TOX: 5,
    StatusCondition.FRZ: 6,
}

WEATHER_IDS: dict[Weather, int] = {
    Weather.NONE: 0, Weather.SUNNY: 1, Weather.RAIN: 2,
    Weather.SAND: 3, Weather.HAIL: 4,  Weather.HEAVY: 5,
    Weather.HARSH: 6, Weather.WIND: 7,
}
NUM_WEATHERS = 8

TERRAIN_IDS: dict[Terrain, int] = {
    Terrain.NONE: 0, Terrain.ELECTRIC: 1, Terrain.GRASSY: 2,
    Terrain.PSYCHIC: 3, Terrain.MISTY: 4,
}
NUM_TERRAINS = 5


# ===== タイプ相性キャッシュ =====
_TYPE_CHART: dict[tuple[str, str], float] | None = None

def _get_type_chart() -> dict[tuple[str, str], float]:
    global _TYPE_CHART
    if _TYPE_CHART is None:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT attacking_type, defending_type, multiplier FROM type_chart")
        _TYPE_CHART = {(r[0], r[1]): r[2] for r in c.fetchall()}
        conn.close()
    return _TYPE_CHART


# ===== ポケモン1体の特徴量エンコード (34次元) =====
# [0]     HP割合 (0.0~1.0)
# [1..7]  状態異常 one-hot (7)
# [8..25] タイプ1 one-hot (18)  ※ タイプ2は別チャンネルで
# [26]    タイプ2 あり/なし
# [27]    メガシンカ済みか (0/1)
# [28..34] 能力ランク7種を正規化 (-6~+6 → 0~1)
POKEMON_FEAT_DIM = 1 + 7 + 18 + 1 + 1 + 7  # = 35

def encode_pokemon(poke: PokemonStatus | None) -> np.ndarray:
    """1体のポケモン状態を数値ベクトルに変換"""
    v = np.zeros(POKEMON_FEAT_DIM, dtype=np.float32)
    if poke is None:
        return v  # 存在しない（瀕死・未選出）は全0

    # HP割合
    v[0] = poke.hp_ratio

    # 状態異常 one-hot
    sid = STATUS_IDS.get(poke.status, 0)
    v[1 + sid] = 1.0

    # タイプ1 one-hot (DBはtype1が英語で入っているため両方対応)
    # ※ PokemonStatusにはtype情報を持たせていないため、
    #    ここではフォールバックとしてNoneを扱う
    # 実際はBattleStateBuilderがDBからtypeを引いてセットする
    # (type情報はStaticPokemonDataが持つ設計)

    # メガシンカ済み
    v[26] = 1.0 if poke.is_mega else 0.0

    # 能力ランク (-6~+6 → 0~1 に正規化)
    ranks = [poke.rank_atk, poke.rank_def, poke.rank_spa,
             poke.rank_spd, poke.rank_spe, poke.rank_acc, poke.rank_eva]
    for i, r in enumerate(ranks):
        v[27 + i] = (r + 6) / 12.0

    return v


# ===== 拡張ポケモン特徴量（タイプ・種族値込み）=====
# DBから取得した静的情報も含めて特徴量化する

POKEMON_FULL_DIM = (
    1      # HP割合
  + 7      # 状態異常
  + 18     # タイプ1 one-hot
  + 18     # タイプ2 one-hot (なしは全0)
  + 1      # メガシンカ済み
  + 7      # 能力ランク
  + 6      # 種族値正規化 (HP/攻/防/特攻/特防/素早さ) / 255
  + 1      # 持ち物あり/なし
)  # = 59

def encode_pokemon_full(
    poke: PokemonStatus | None,
    type1: str | None = None,
    type2: str | None = None,
    base_stats: dict | None = None,
) -> np.ndarray:
    """
    タイプ・種族値情報も含めた完全な特徴量ベクトルを生成

    Args:
        poke:       動的状態
        type1:      タイプ1（日本語または英語）
        type2:      タイプ2（同上、なしはNone）
        base_stats: {"hp": int, "attack": int, ...}
    """
    v = np.zeros(POKEMON_FULL_DIM, dtype=np.float32)
    if poke is None:
        return v

    idx = 0

    # HP割合
    v[idx] = poke.hp_ratio
    idx += 1

    # 状態異常 one-hot
    sid = STATUS_IDS.get(poke.status, 0)
    v[idx + sid] = 1.0
    idx += 7

    # タイプ1 one-hot
    if type1 and type1 in TYPE_IDS:
        v[idx + TYPE_IDS[type1]] = 1.0
    idx += 18

    # タイプ2 one-hot
    if type2 and type2 in TYPE_IDS:
        v[idx + TYPE_IDS[type2]] = 1.0
    idx += 18

    # メガシンカ済み
    v[idx] = 1.0 if poke.is_mega else 0.0
    idx += 1

    # 能力ランク
    ranks = [poke.rank_atk, poke.rank_def, poke.rank_spa,
             poke.rank_spd, poke.rank_spe, poke.rank_acc, poke.rank_eva]
    for r in ranks:
        v[idx] = (r + 6) / 12.0
        idx += 1

    # 種族値正規化
    if base_stats:
        for key in ["hp", "attack", "defense", "sp_attack", "sp_defense", "speed"]:
            v[idx] = base_stats.get(key, 0) / 255.0
            idx += 1
    else:
        idx += 6

    # 持ち物あり/なし
    v[idx] = 1.0 if poke.item_en else 0.0
    idx += 1

    return v


# ===== フィールド特徴量 (16次元) =====
# [0..7]  天気 one-hot (8)
# [8..12] フィールド one-hot (5)
# [13]    トリックルーム (0/1)
# [14]    天気残りターン正規化
# [15]    フィールド残りターン正規化

FIELD_FEAT_DIM = 8 + 5 + 1 + 1 + 1  # = 16

def encode_field(field: FieldState) -> np.ndarray:
    v = np.zeros(FIELD_FEAT_DIM, dtype=np.float32)

    # 天気 one-hot
    wid = WEATHER_IDS.get(field.weather, 0)
    v[wid] = 1.0

    # フィールド one-hot
    tid = TERRAIN_IDS.get(field.terrain, 0)
    v[8 + tid] = 1.0

    # トリックルーム
    v[13] = 1.0 if field.trick_room else 0.0

    # 残りターン正規化 (最大8ターンで正規化)
    v[14] = min(field.weather_turns, 8) / 8.0
    v[15] = min(field.terrain_turns, 5) / 5.0

    return v


# ===== BattleState 全体の特徴量ベクトル =====

class BattleFeaturizer:
    """
    BattleStateを固定長のnumpy配列に変換する。

    構成:
      自分の場ポケモン (59次元)
      相手の場ポケモン (59次元)
      自分の控え1体目  (59次元)
      自分の控え2体目  (59次元)
      相手の控え1体目  (59次元)
      相手の控え2体目  (59次元)
      フィールド状態   (16次元)
      ターン情報       (2次元)  [ターン/最大ターン, P1残ポケ数/3]
      ─────────────────────────
      合計            (416次元)
    """

    TOTAL_DIM = POKEMON_FULL_DIM * 6 + FIELD_FEAT_DIM + 2  # 59*6+16+2 = 372

    def __init__(self):
        self._db_cache: dict[str, dict] = {}  # name_en → {type1, type2, base_stats}

    def _load_pokemon_static(self, name_en: str) -> dict:
        """DBからポケモンの静的情報を取得（キャッシュ付き）"""
        if name_en in self._db_cache:
            return self._db_cache[name_en]

        conn = get_connection()
        c = conn.cursor()

        # 通常形
        c.execute("""
            SELECT type1, type2, hp, attack, defense, sp_attack, sp_defense, speed
            FROM pokemon WHERE name_en = ?
        """, (name_en,))
        row = c.fetchone()

        if row is None:
            # メガ形態を試す
            c.execute("""
                SELECT type1, type2, hp, attack, defense, sp_attack, sp_defense, speed
                FROM mega_evolution WHERE mega_name_en = ?
            """, (name_en,))
            row = c.fetchone()

        conn.close()

        if row:
            data = {
                "type1": row["type1"],
                "type2": row["type2"],
                "base_stats": {
                    "hp":        row["hp"],
                    "attack":    row["attack"],
                    "defense":   row["defense"],
                    "sp_attack": row["sp_attack"],
                    "sp_defense":row["sp_defense"],
                    "speed":     row["speed"],
                }
            }
        else:
            data = {"type1": None, "type2": None, "base_stats": {}}

        self._db_cache[name_en] = data
        return data

    def _get_bench(self, player_state) -> list:
        """場に出ていない控えポケモンを最大2体返す"""
        bench = [
            p for i, p in enumerate(player_state.selected)
            if i != player_state.active_index and not p.is_fainted
        ]
        return bench[:2]

    def encode(self, state: BattleState) -> np.ndarray:
        """BattleStateを固定長ベクトルに変換"""
        vectors = []

        for player_id in ["p1", "p2"]:
            player = state.p1 if player_id == "p1" else state.p2

            # 場のポケモン
            active = player.active
            bench  = self._get_bench(player)

            pokes = [active] + bench
            # 不足分はNoneで補完（最大3体: 場1 + 控え2）
            while len(pokes) < 3:
                pokes.append(None)

            for poke in pokes:
                if poke is not None:
                    static = self._load_pokemon_static(poke.name_en)
                    vec = encode_pokemon_full(
                        poke,
                        type1=static.get("type1"),
                        type2=static.get("type2"),
                        base_stats=static.get("base_stats"),
                    )
                else:
                    vec = np.zeros(POKEMON_FULL_DIM, dtype=np.float32)
                vectors.append(vec)

        # フィールド
        vectors.append(encode_field(state.field_state))

        # ターン情報
        turn_info = np.array([
            state.turn / MAX_TURNS,
            sum(1 for p in state.p1.selected if not p.is_fainted) / SELECT_SIZE,
        ], dtype=np.float32)
        vectors.append(turn_info)

        return np.concatenate(vectors)

    @property
    def feature_dim(self) -> int:
        return self.TOTAL_DIM


from game_state import MAX_TURNS, SELECT_SIZE, MAX_MOVES


# ===== 行動エンコード =====
# 行動は意味カテゴリ (ActionCategory) で表現する。
# ActionClassifier が返す 0〜11 の整数をそのまま使用。

MAX_ACTIONS = 12  # ActionCategory の総数 (action_classifier.NUM_ACTION_CATEGORIES)

def encode_action_index(category: int) -> int:
    """
    ActionCategory の整数値をそのまま返す（後方互換ラッパー）。
    直接 category 値を使うことを推奨。
    """
    return int(category)


if __name__ == "__main__":
    # 簡単な動作テスト
    from game_state import PokemonStatus, PlayerState, BattleState, FieldState, Weather

    poke1 = PokemonStatus(
        name_jp="ガブリアス", name_en="garchomp",
        current_hp=270, max_hp=341,
        move_names=["じしん", "げきりん", "かみくだく", "つるぎのまい"],
        move_pp=[10, 10, 10, 20],
    )
    p1 = PlayerState(player_id="p1", player_name="テスト1")
    p1.selected = [poke1]

    poke2 = PokemonStatus(
        name_jp="ゲンガー", name_en="gengar",
        current_hp=120, max_hp=251,
        move_names=["シャドーボール", "ヘドロばくだん", "サイコキネシス", "みちづれ"],
        move_pp=[15, 15, 10, 10],
    )
    p2 = PlayerState(player_id="p2", player_name="テスト2")
    p2.selected = [poke2]

    state = BattleState(turn=5, p1=p1, p2=p2)

    featurizer = BattleFeaturizer()
    vec = featurizer.encode(state)
    print(f"特徴量ベクトル次元: {vec.shape[0]} (期待値: {featurizer.feature_dim})")
    print(f"ベクトルの先頭10要素: {vec[:10]}")
    print(f"行動候補: {state.get_available_actions('p1')}")

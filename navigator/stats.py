"""
navigator/stats.py
==================
ポケモンチャンピオンズ（レベル50）ステータス実数値計算。

前提:
  - レベル: 50 固定
  - 個体値: 31 固定（チャンピオンズは最大個体値が標準）
  - 努力値: PokemonStatus.evs から取得
  - 性格補正: NATURE_TABLE から取得

使い方:
    from navigator.stats import get_actual_stats
    stats = get_actual_stats(my_poke, base_stats={"H":108,"A":130,...})
    print(stats["S"])  # 素早さ実数値
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.game_state import PokemonStatus  # type: ignore

# ===== 性格補正テーブル =====
# キー: 性格名（日本語）
# 値: {能力略号: 倍率} — 上昇が 1.1、下降が 0.9
# ニュートラル性格はキー自体が存在しない（補正なし）

NATURE_TABLE: dict[str, dict[str, float]] = {
    # 攻撃↑
    "いじっぱり": {"A": 1.1, "C": 0.9},
    "ゆうかん":   {"A": 1.1, "S": 0.9},
    "やんちゃ":   {"A": 1.1, "D": 0.9},
    "ずぶとい":   {"B": 1.1, "A": 0.9},
    # 防御↑
    "のんき":     {"B": 1.1, "S": 0.9},
    "わんぱく":   {"B": 1.1, "C": 0.9},
    "いやしんぼ": {"B": 1.1, "D": 0.9},
    # 特攻↑
    "ひかえめ":   {"C": 1.1, "A": 0.9},
    "れいせい":   {"C": 1.1, "S": 0.9},
    "うっかりや": {"C": 1.1, "D": 0.9},
    "なまいき":   {"D": 1.1, "S": 0.9},
    # 特防↑
    "しんちょう": {"D": 1.1, "C": 0.9},
    "おだやか":   {"D": 1.1, "A": 0.9},
    "なまいき":   {"D": 1.1, "S": 0.9},
    # 素早さ↑
    "ようき":     {"S": 1.1, "C": 0.9},
    "おくびょう": {"S": 1.1, "A": 0.9},
    "せっかち":   {"S": 1.1, "D": 0.9},
    "むじゃき":   {"S": 1.1, "B": 0.9},
    "うっかりや": {"C": 1.1, "D": 0.9},
    # ニュートラル（補正なし）— テーブルに存在しない
    # まじめ / すなお / てれや / きまぐれ / ひねくれ
}

# 能力略号 → race_value.csv の列名マッピング
STAT_KEY_MAP = {
    "H": "H",  # HP
    "A": "A",  # 攻撃
    "B": "B",  # 防御
    "C": "C",  # 特攻
    "D": "D",  # 特防
    "S": "S",  # 素早さ
}


def get_nature_modifier(nature: str, stat_key: str) -> float:
    """
    性格名と能力略号から性格補正倍率を返す。

    Args:
        nature:   性格名（日本語）例: "ようき"
        stat_key: 能力略号 "H"/"A"/"B"/"C"/"D"/"S"

    Returns:
        1.1 / 0.9 / 1.0
    """
    mods = NATURE_TABLE.get(nature, {})
    return mods.get(stat_key, 1.0)


def calc_hp(base: int, ev: int = 0, iv: int = 31, level: int = 50) -> int:
    """
    HP実数値を計算する。

    公式: floor((base*2 + iv + ev//4) * level // 100) + level + 10
    """
    return (base * 2 + iv + ev // 4) * level // 100 + level + 10


def calc_stat(
    base: int,
    ev: int = 0,
    iv: int = 31,
    level: int = 50,
    nature_mod: float = 1.0,
) -> int:
    """
    HP以外のステータス実数値を計算する。

    公式: floor( floor((base*2 + iv + ev//4) * level // 100 + 5) * nature_mod )
    """
    raw = (base * 2 + iv + ev // 4) * level // 100 + 5
    return int(raw * nature_mod)


def get_actual_stats(
    pokemon: "PokemonStatus",
    base_stats: dict[str, int],
) -> dict[str, int]:
    """
    PokemonStatus（努力値・性格）と種族値辞書から、
    レベル50の全実数値を計算して返す。

    Args:
        pokemon:    PokemonStatus（.evs, .nature を使用）
        base_stats: {"H": 108, "A": 130, "B": 95, "C": 80, "D": 85, "S": 102} 形式

    Returns:
        {"H": 実HP, "A": 実攻撃, "B": 実防御, "C": 実特攻, "D": 実特防, "S": 実素早さ}
    """
    evs    = pokemon.evs if hasattr(pokemon, "evs") else {}
    nature = pokemon.nature if hasattr(pokemon, "nature") else "まじめ"
    result: dict[str, int] = {}

    for key in ("H", "A", "B", "C", "D", "S"):
        base  = base_stats.get(key, 50)
        ev    = evs.get(key, 0)
        if key == "H":
            result[key] = calc_hp(base, ev)
        else:
            mod = get_nature_modifier(nature, key)
            result[key] = calc_stat(base, ev, nature_mod=mod)

    return result


# ===== 種族値ローダー =====

_BASE_STATS_CACHE: dict[str, dict[str, int]] = {}


def load_base_stats(name_jp: str) -> dict[str, int] | None:
    """
    race_value.csv から日本語名で種族値を取得する（メモリキャッシュ付き）。

    Returns:
        {"H":..., "A":..., "B":..., "C":..., "D":..., "S":...} または None
    """
    if name_jp in _BASE_STATS_CACHE:
        return _BASE_STATS_CACHE[name_jp]

    import csv
    from pathlib import Path

    csv_path = Path(__file__).parent.parent / "data" / "race_value.csv"
    if not csv_path.exists():
        return None

    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("名前") == name_jp:
                stats = {
                    "H": int(row["H"]),
                    "A": int(row["A"]),
                    "B": int(row["B"]),
                    "C": int(row["C"]),
                    "D": int(row["D"]),
                    "S": int(row["S"]),
                }
                _BASE_STATS_CACHE[name_jp] = stats
                return stats

    return None


# ===== 動作確認 =====

if __name__ == "__main__":
    from simulator.game_state import PokemonStatus  # type: ignore

    # ようきガブリアス A252 S252 D4
    garchomp = PokemonStatus(
        name_jp="ガブリアス", name_en="garchomp",
        current_hp=301, max_hp=301,
    )
    garchomp.nature = "ようき"
    garchomp.evs = {"H": 0, "A": 252, "B": 0, "C": 0, "D": 4, "S": 252}

    base = load_base_stats("ガブリアス")
    if base:
        stats = get_actual_stats(garchomp, base)
        print("ようきガブリアス (A252/D4/S252):")
        print(f"  H={stats['H']}  A={stats['A']}  B={stats['B']}")
        print(f"  C={stats['C']}  D={stats['D']}  S={stats['S']}")
        # 期待値: H175 A182 B115 C91 D102 S169
    else:
        print("race_value.csv が見つかりません")

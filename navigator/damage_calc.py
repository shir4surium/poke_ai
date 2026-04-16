"""
navigator/damage_calc.py
========================
ポケモンチャンピオンズ（レベル50）ダメージ計算。

ダメージ公式（シングル・レベル50）:
  damage = floor(
    floor(
      floor(atk * 2 * power / def / 50) + 2
    ) * type_eff * stab * rand
  )

  rand: 0.85 〜 1.00 の乱数（最小/最大を返す）

チャンピオンズの HP 表示:
  - 残り HP% は小数点以下切り捨て表示
  - 例: 実残HP 71 / max 100 → 表示は「71%」
  - ダメージ% = 表示HP変化量 ± 1% の誤差がある
"""

from __future__ import annotations
import math


# ===== ダメージ計算 =====

def calc_damage_range(
    atk_stat: int,
    def_stat:  int,
    power:     int,
    type_eff:  float = 1.0,
    stab:      float = 1.0,
    level:     int   = 50,
) -> tuple[int, int]:
    """
    最小ダメージ（乱数0.85）と最大ダメージ（乱数1.00）を返す。

    Args:
        atk_stat: 攻撃（または特攻）実数値
        def_stat: 防御（または特防）実数値
        power:    技の基礎威力
        type_eff: タイプ相性倍率（0.25 / 0.5 / 1.0 / 2.0 / 4.0）
        stab:     タイプ一致補正（1.0 または 1.5）
        level:    攻撃者のレベル（デフォルト50）

    Returns:
        (min_damage, max_damage) の整数タプル
    """
    if power <= 0 or def_stat <= 0:
        return (0, 0)

    base = math.floor(atk_stat * 2 * power / def_stat / 50) + 2
    min_dmg = math.floor(math.floor(math.floor(base * type_eff) * stab) * 0.85)
    max_dmg = math.floor(math.floor(math.floor(base * type_eff) * stab) * 1.00)
    return (min_dmg, max_dmg)


def calc_damage_pct_range(
    atk_stat:   int,
    def_stat:   int,
    power:      int,
    defender_max_hp: int,
    type_eff:   float = 1.0,
    stab:       float = 1.0,
) -> tuple[float, float]:
    """
    ダメージを HP% 範囲（0.0〜1.0）で返す。
    チャンピオンズの表示（小数点以下切り捨て%）に対応するため
    floor した値で範囲を表現する。

    Returns:
        (min_pct, max_pct)  例: (0.38, 0.44)
    """
    if defender_max_hp <= 0:
        return (0.0, 0.0)
    min_dmg, max_dmg = calc_damage_range(atk_stat, def_stat, power, type_eff, stab)
    return (min_dmg / defender_max_hp, max_dmg / defender_max_hp)


# ===== 防御実数値の逆算 =====

def estimate_def_stat_range(
    atk_stat:    int,
    power:       int,
    type_eff:    float,
    stab:        float,
    damage_pct:  float,    # 観測されたダメージ割合（0.0〜1.0）
    defender_max_hp: int,
) -> tuple[int, int]:
    """
    与えたダメージ%から相手の防御（または特防）実数値の推定範囲を逆算する。

    チャンピオンズは残HP%が切り捨て表示のため、
    実際のダメージは `damage_pct * max_hp` 〜 `(damage_pct + 0.01) * max_hp - 1`
    の範囲にある。乱数0.85〜1.00も考慮して範囲を計算する。

    Args:
        atk_stat:        自分の攻撃（または特攻）実数値
        power:           使用した技の基礎威力
        type_eff:        タイプ相性倍率
        stab:            STAB倍率
        damage_pct:      観測された HP 変化% (0.0〜1.0, e.g. 0.30 = 30%)
        defender_max_hp: 相手の最大HP推定値（不明なら 100 として相対計算）

    Returns:
        (def_min, def_max) — 推定防御実数値の最小・最大
        例: (145, 175)
    """
    if power <= 0 or atk_stat <= 0:
        return (1, 999)

    # 実際のダメージ量の範囲（切り捨て表示±1%の誤差）
    dmg_observed_min = damage_pct * defender_max_hp
    dmg_observed_max = (damage_pct + 0.01) * defender_max_hp

    results: list[int] = []

    # 乱数0.85〜1.00のそれぞれで防御実数値を逆算
    for rand in [0.85, 1.00]:
        for dmg in [dmg_observed_min, dmg_observed_max]:
            if dmg <= 0:
                continue
            # damage = floor(floor(floor(atk*2*power/def/50)+2) * type_eff * stab * rand)
            # → base * type_eff * stab * rand ≈ dmg
            # → base ≈ dmg / (type_eff * stab * rand)
            # → floor(atk*2*power/def/50)+2 ≈ base
            # → atk*2*power/def/50 ≈ base - 2
            base_approx = dmg / (type_eff * stab * rand)
            inner = base_approx - 2
            if inner <= 0:
                continue
            # inner = floor(atk*2*power/def/50)
            # → def ≈ atk*2*power / (inner * 50)
            def_approx = atk_stat * 2 * power / (inner * 50)
            results.append(int(def_approx))

    if not results:
        return (1, 999)

    return (max(1, min(results) - 10), max(results) + 10)


# ===== 素早さ比較 =====

def compare_speed(
    my_speed:      int,
    moved_first:   bool,
    my_priority:   int = 0,
    opp_priority:  int = 0,
    trick_room:    bool = False,
) -> dict:
    """
    行動順の観察から相手の素早さ範囲を推定する。

    Returns:
        {"opp_speed_min": int, "opp_speed_max": int, "note": str}
    """
    # 優先度が異なる場合は素早さ比較にならない
    if my_priority != opp_priority:
        return {"opp_speed_min": 1, "opp_speed_max": 999, "note": "優先度差あり（比較不可）"}

    if trick_room:
        # トリックルーム: 遅い方が先行
        if moved_first:
            # 自分が先 = 自分の素早さが低い
            return {"opp_speed_min": my_speed, "opp_speed_max": 999, "note": "TR下: 相手素早さ≥自分"}
        else:
            return {"opp_speed_min": 1, "opp_speed_max": my_speed - 1, "note": "TR下: 相手素早さ<自分"}
    else:
        if moved_first:
            # 通常: 自分が先行 = 自分の方が速い
            return {"opp_speed_min": 1, "opp_speed_max": my_speed - 1, "note": f"相手素早さ<{my_speed}（自分先行）"}
        else:
            return {"opp_speed_min": my_speed, "opp_speed_max": 999, "note": f"相手素早さ≥{my_speed}（相手先行）"}


# ===== タイプ相性ローダー =====

_TYPE_CHART_CACHE: dict[tuple[str, str], float] | None = None


def get_type_effectiveness(attacking_type: str, defending_type: str) -> float:
    """
    タイプ相性倍率を返す（DB の type_chart テーブルを使用）。
    defending_type が None の場合は 1.0 を返す。
    """
    global _TYPE_CHART_CACHE

    if defending_type is None:
        return 1.0

    if _TYPE_CHART_CACHE is None:
        _load_type_chart()

    if _TYPE_CHART_CACHE is None:
        return 1.0

    return _TYPE_CHART_CACHE.get((attacking_type, defending_type), 1.0)


def _load_type_chart() -> None:
    global _TYPE_CHART_CACHE
    import sys
    from pathlib import Path
    ROOT = Path(__file__).parent.parent
    sys.path.insert(0, str(ROOT / "db"))
    try:
        import sqlite3
        db_path = ROOT / "db" / "champions.db"
        conn = sqlite3.connect(str(db_path))
        cur  = conn.cursor()
        cur.execute("SELECT attacking_type, defending_type, multiplier FROM type_chart")
        _TYPE_CHART_CACHE = {(r[0], r[1]): float(r[2]) for r in cur.fetchall()}
        conn.close()
    except Exception:
        _TYPE_CHART_CACHE = {}


def calc_combined_type_eff(
    attacking_type: str,
    defend_type1:   str | None,
    defend_type2:   str | None,
) -> float:
    """攻撃タイプ vs 防御タイプ1・タイプ2 の合成相性倍率を返す"""
    eff = get_type_effectiveness(attacking_type, defend_type1) if defend_type1 else 1.0
    if defend_type2:
        eff *= get_type_effectiveness(attacking_type, defend_type2)
    return eff


# ===== 動作確認 =====

if __name__ == "__main__":
    print("=== ダメージ計算テスト ===")

    # ようきガブリアス (A182) のじしん vs H252ドヒドイデ
    # ドヒドイデ: B152 D142 HP HP135
    # じしん: 威力100, じめん, 物理
    # タイプ相性: じめん vs どく/みず = どく×1.0, みず×1.0 = 1.0
    # ガブリアス はじめんタイプ → STAB 1.5
    atk = 182
    def_stat = 152
    power = 100
    type_eff = 1.0
    stab = 1.5
    max_hp_toxapex = 135

    min_d, max_d = calc_damage_range(atk, def_stat, power, type_eff, stab)
    print(f"じしん (A{atk} vs B{def_stat}): {min_d}〜{max_d} HP")
    print(f"  対HP{max_hp_toxapex}: {min_d/max_hp_toxapex*100:.1f}〜{max_d/max_hp_toxapex*100:.1f}%")

    print()
    print("=== 防御実数値逆算テスト ===")
    # 30%ダメージを与えた場合に逆算
    def_range = estimate_def_stat_range(atk, power, type_eff, stab, 0.30, max_hp_toxapex)
    print(f"30%ダメージ観測 → 相手防御実数値推定: {def_range[0]}〜{def_range[1]}")

    print()
    print("=== 素早さ比較テスト ===")
    result = compare_speed(my_speed=169, moved_first=True)
    print(f"自分S169, 先行: {result}")
    result = compare_speed(my_speed=169, moved_first=False)
    print(f"自分S169, 後行: {result}")

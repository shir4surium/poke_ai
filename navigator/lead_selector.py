"""
navigator/lead_selector.py
===========================
バトル開始前の選出ロジック（タイプ相性ベース）。

スコアリング方針:
  1. 各自ポケモン vs 相手6体のカバレッジスコアを計算
     - 相手1体に対してタイプ有効な技 (+2) or ニュートラル (+0.5)
     - 相手から弱点を突かれないなら追加点 (+1)
  2. 合計スコア上位3体を選出
  3. リード: 選出3体の中で相手の先頭（エース想定）に最もスコアが高い1体

必要なデータ:
  - race_value.csv (タイプ情報)
  - ActionClassifier (タイプ相性判定)
"""

from __future__ import annotations
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "ai"))
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "db"))

if TYPE_CHECKING:
    from simulator.game_state import PokemonStatus  # type: ignore


@dataclass
class SelectionResult:
    """選出推薦結果"""
    selected: list[str]         # 選出3体（日本語名）
    lead:     str               # 先頭に出すポケモン（日本語名）
    scores:   dict[str, float]  # 各ポケモンのスコア
    reasons:  dict[str, str]    # 各ポケモンの選出理由


# ===== タイプ情報ローダー =====

_POKE_TYPE_CACHE: dict[str, tuple[str | None, str | None]] = {}


def _get_types_jp(name_jp: str) -> tuple[str | None, str | None]:
    """日本語名でポケモンのタイプを取得（race_value.csv を参照）"""
    if name_jp in _POKE_TYPE_CACHE:
        return _POKE_TYPE_CACHE[name_jp]

    import csv

    # JP→EN タイプ変換テーブル
    JP_TO_EN = {
        "ノーマル": "Normal", "ほのお": "Fire",     "みず": "Water",
        "でんき":  "Electric", "くさ": "Grass",       "こおり": "Ice",
        "かくとう": "Fighting","どく": "Poison",      "じめん": "Ground",
        "ひこう":  "Flying",   "エスパー": "Psychic", "むし": "Bug",
        "いわ":    "Rock",     "ゴースト": "Ghost",   "ドラゴン": "Dragon",
        "あく":    "Dark",     "はがね": "Steel",     "フェアリー": "Fairy",
    }

    csv_path = ROOT / "data" / "race_value.csv"
    if csv_path.exists():
        with open(csv_path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("名前") == name_jp:
                    t1 = JP_TO_EN.get(row.get("タイプ", ""))
                    # 2列目タイプ（列名が空文字または2番目の無名列）
                    row_vals = list(row.values())
                    t2_jp = row_vals[9] if len(row_vals) > 9 else ""
                    t2 = JP_TO_EN.get(t2_jp) if t2_jp else None
                    _POKE_TYPE_CACHE[name_jp] = (t1, t2)
                    return (t1, t2)

    _POKE_TYPE_CACHE[name_jp] = (None, None)
    return (None, None)


def _get_type_eff(atk_type: str | None, def_type1: str | None, def_type2: str | None) -> float:
    """攻撃タイプ vs 防御タイプの合成相性倍率を返す"""
    if atk_type is None:
        return 1.0
    from navigator.damage_calc import calc_combined_type_eff
    return calc_combined_type_eff(atk_type, def_type1, def_type2)


# ===== スコアリング =====

def compute_matchup_score(
    my_poke_jp:       str,
    my_move_types:    list[str | None],   # 技のタイプ（EN、最大4）
    opponent_names:   list[str],          # 相手6体の日本語名
    my_type1:         str | None,
    my_type2:         str | None,
) -> tuple[float, str]:
    """
    自分の1ポケモンが相手6体に対するカバレッジスコアを計算。

    Returns:
        (score, reason_text)
    """
    score = 0.0
    cover_count = 0    # 相手の中で有利を取れる数
    weak_count  = 0    # 弱点を突かれる相手の数

    for opp_name in opponent_names:
        opp_t1, opp_t2 = _get_types_jp(opp_name)

        # 自分の技が相手に有効かチェック
        best_eff = 1.0
        for move_type in my_move_types:
            eff = _get_type_eff(move_type, opp_t1, opp_t2)
            best_eff = max(best_eff, eff)

        if best_eff >= 2.0:
            score += 2.0
            cover_count += 1
        elif best_eff >= 1.0:
            score += 0.5

        # 相手から弱点を突かれるかチェック
        opp_eff_on_me = max(
            _get_type_eff(opp_t1, my_type1, my_type2),
            _get_type_eff(opp_t2, my_type1, my_type2) if opp_t2 else 1.0,
        )
        if opp_eff_on_me <= 0.5:
            score += 1.0   # 弱点を突かれにくい → ボーナス
        elif opp_eff_on_me >= 2.0:
            weak_count += 1

    reason_parts = []
    if cover_count > 0:
        reason_parts.append(f"相手{cover_count}体にタイプ有効")
    if weak_count > 0:
        reason_parts.append(f"相手{weak_count}体から弱点")
    reason = "、".join(reason_parts) if reason_parts else "タイプ相性ニュートラル"

    return (score, reason)


# ===== 選出メイン =====

def _get_move_types_jp(pokemon: "PokemonStatus") -> list[str | None]:
    """ポケモンの技タイプ（EN）リストを取得"""
    import csv

    JP_TO_EN_TYPE = {
        "ノーマル": "Normal", "ほのお": "Fire",     "みず": "Water",
        "でんき":  "Electric", "くさ": "Grass",       "こおり": "Ice",
        "かくとう": "Fighting","どく": "Poison",      "じめん": "Ground",
        "ひこう":  "Flying",   "エスパー": "Psychic", "むし": "Bug",
        "いわ":    "Rock",     "ゴースト": "Ghost",   "ドラゴン": "Dragon",
        "あく":    "Dark",     "はがね": "Steel",     "フェアリー": "Fairy",
    }

    move_types: list[str | None] = []
    csv_path = ROOT / "data" / "list_wepon.csv"
    move_data: dict[str, str | None] = {}

    if csv_path.exists():
        with open(csv_path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                name = row.get("名前", "")
                t    = JP_TO_EN_TYPE.get(row.get("タイプ", ""))
                move_data[name] = t

    for move_name in pokemon.move_names:
        move_types.append(move_data.get(move_name))

    return move_types


def select_team(
    my_party:         list["PokemonStatus"],
    opponent_names:   list[str],
    lead_opponent:    str | None = None,  # 相手のリード（先頭）推測
) -> SelectionResult:
    """
    タイプ相性ベースでバトルの選出3体を推薦する。

    Args:
        my_party:       自パーティ最大6体
        opponent_names: 相手のパーティ（日本語名、最大6体）
        lead_opponent:  相手のリードとして想定するポケモン名
                        （None の場合は opponent_names[0]）

    Returns:
        SelectionResult
    """
    if lead_opponent is None and opponent_names:
        lead_opponent = opponent_names[0]

    scored: list[tuple[float, "PokemonStatus", str]] = []

    for poke in my_party:
        t1, t2     = _get_types_jp(poke.name_jp)
        move_types = _get_move_types_jp(poke)
        score, reason = compute_matchup_score(
            poke.name_jp, move_types, opponent_names, t1, t2
        )
        scored.append((score, poke, reason))

    # スコア降順でソート
    scored.sort(key=lambda x: -x[0])

    # 上位3体を選出
    top3 = scored[:3]
    selected_names = [p.name_jp for _, p, _ in top3]
    scores_dict    = {p.name_jp: s for s, p, _ in top3}
    reasons_dict   = {p.name_jp: r for _, p, r in top3}

    # リード: 選出3体の中で相手リードに最もスコアが高い1体
    lead = selected_names[0]
    if lead_opponent:
        lead_scores: list[tuple[float, str]] = []
        for _, poke, _ in top3:
            t1, t2     = _get_types_jp(poke.name_jp)
            move_types = _get_move_types_jp(poke)
            s, _ = compute_matchup_score(
                poke.name_jp, move_types, [lead_opponent], t1, t2
            )
            lead_scores.append((s, poke.name_jp))
        lead_scores.sort(key=lambda x: -x[0])
        lead = lead_scores[0][1]

    return SelectionResult(
        selected = selected_names,
        lead     = lead,
        scores   = scores_dict,
        reasons  = reasons_dict,
    )


# ===== 動作確認 =====

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT / "simulator"))

    from simulator.game_state import PokemonStatus  # type: ignore

    def make_poke(name_jp, moves):
        p = PokemonStatus(name_jp=name_jp, name_en=name_jp,
                          current_hp=300, max_hp=300)
        p.move_names = moves
        return p

    my_party = [
        make_poke("ガブリアス",  ["じしん", "げきりん", "かみくだく", "つるぎのまい"]),
        make_poke("ミミッキュ",  ["じゃれつく", "かげうち", "つるぎのまい", "トリックルーム"]),
        make_poke("テッカグヤ",  ["やどりぎのタネ", "ヘビーボンバー", "ボルトチェンジ", "ねっぷう"]),
        make_poke("トゲキッス",  ["エアスラッシュ", "マジカルシャイン", "はどうだん", "ほろびのうた"]),
        make_poke("ドリュウズ",  ["アイアンヘッド", "じしん", "つのドリル", "かたやぶり"]),
        make_poke("ウォッシュロトム", ["ハイドロポンプ", "10まんボルト", "ボルトチェンジ", "おにび"]),
    ]

    opponent = ["カイリュー", "ドヒドイデ", "テッカグヤ", "ミミッキュ", "ウーラオス", "トゲキッス"]

    result = select_team(my_party, opponent, lead_opponent="カイリュー")
    print("=== 選出推薦 ===")
    print(f"選出: {result.selected}")
    print(f"リード: {result.lead}")
    print("スコア:")
    for name, score in result.scores.items():
        print(f"  {name}: {score:.1f} — {result.reasons[name]}")

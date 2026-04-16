"""
CSV データ構築スクリプト
========================
1. race_value.csv  をコピーし、Champions DB のメガシンカ情報を追記
2. list_wepon.csv  をコピー

出力:
  data/race_value.csv  ← 元ファイル + メガシンカ行
  data/list_wepon.csv  ← 元ファイルのコピー

実行:
  python data_pipeline/build_pokemon_csv.py
"""

from __future__ import annotations
import csv
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC_DIR = Path("C:/Users/tbkPo/Desktop/p/claude/etc")
DST_DIR = ROOT / "data"

SRC_RACE   = SRC_DIR / "race_value.csv"
SRC_WEPON  = SRC_DIR / "list_wepon.csv"
DST_RACE   = DST_DIR / "race_value.csv"
DST_WEPON  = DST_DIR / "list_wepon.csv"
DB_PATH    = ROOT / "db" / "champions.db"

# ── 英語タイプ名 → 日本語タイプ名 ──
EN_TO_JP_TYPE: dict[str, str] = {
    "Normal":   "ノーマル",
    "Fire":     "ほのお",
    "Water":    "みず",
    "Electric": "でんき",
    "Grass":    "くさ",
    "Ice":      "こおり",
    "Fighting": "かくとう",
    "Poison":   "どく",
    "Ground":   "じめん",
    "Flying":   "ひこう",
    "Psychic":  "エスパー",
    "Bug":      "むし",
    "Rock":     "いわ",
    "Ghost":    "ゴースト",
    "Dragon":   "ドラゴン",
    "Dark":     "あく",
    "Steel":    "はがね",
    "Fairy":    "フェアリー",
}

# ── race_value.csv に存在しないベースポケモンの図鑑番号 (標準番号) ──
# Champions DB には存在するが race_value.csv に未収録のポケモン
_MISSING_BASE_NO: dict[str, int] = {
    "beedrill":   15,
    "pidgeot":    18,
    "alakazam":   65,
    "kangaskhan": 115,
    "starmie":    121,
    "mr-mime":    122,
    "jynx":       124,
    "pinsir":     127,
    "aerodactyl": 142,
    "steelix":    208,
    "mawile":     303,
    "aggron":     306,
    "manectric":  310,
    "sharpedo":   319,
    "absol":      359,
    "lopunny":    428,
    "togekiss":   468,
    "audino":     531,
}


def _load_race_value() -> tuple[list[dict], dict[str, int]]:
    """race_value.csv を読み込み (rows, jp名→図鑑番号マップ) を返す"""
    with open(SRC_RACE, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    jp_to_no: dict[str, int] = {}
    for r in rows:
        try:
            jp_to_no[r["名前"]] = int(r["No."])
        except (ValueError, KeyError):
            pass
    return rows, jp_to_no


def _get_mega_rows(jp_to_no: dict[str, int]) -> list[dict]:
    """Champions DB からメガシンカデータを取得し、CSV 行形式に変換して返す"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ベースポケモンの JP 名も取得
    cur.execute("SELECT name_en, name_jp FROM pokemon")
    en_to_jp: dict[str, str] = {r[0]: r[1] for r in cur.fetchall()}

    cur.execute("""
        SELECT base_pokemon_en, mega_name_jp, mega_name_en,
               type1, type2, hp, attack, defense, sp_attack, sp_defense, speed
        FROM mega_evolution
        ORDER BY mega_name_en
    """)
    megas = cur.fetchall()
    conn.close()

    mega_rows: list[dict] = []
    for (base_en, mega_jp, mega_en, t1_en, t2_en,
         hp, atk, defn, spa, spd, spe) in megas:

        # 図鑑番号: race_value からベース JP 名で取得 → なければ手動マップ
        base_jp = en_to_jp.get(base_en, "")
        no = jp_to_no.get(base_jp) or _MISSING_BASE_NO.get(base_en)
        if no is None:
            print(f"  [SKIP] 図鑑番号不明: {base_en} ({base_jp})", file=sys.stderr)
            continue

        t1_jp = EN_TO_JP_TYPE.get(t1_en or "", "")
        t2_jp = EN_TO_JP_TYPE.get(t2_en or "", "")
        total = hp + atk + defn + spa + spd + spe

        mega_rows.append({
            "No.":    str(no),
            "名前":   mega_jp,
            "H":      str(hp),
            "A":      str(atk),
            "B":      str(defn),
            "C":      str(spa),
            "D":      str(spd),
            "S":      str(spe),
            "タイプ":  t1_jp,
            "":        t2_jp,   # タイプ2（列ヘッダが空文字）
            "合計":   str(total),
            "種別":   "mega",
            "SV内定": "",
            "未進化":  "",
        })

    return mega_rows


def build_race_value_csv() -> None:
    """race_value.csv コピー＋メガシンカ追記"""
    print(f"race_value.csv を構築中...")
    rows, jp_to_no = _load_race_value()
    mega_rows = _get_mega_rows(jp_to_no)

    # 既存行 + メガシンカ行を図鑑番号でソート
    all_rows = rows + mega_rows
    def sort_key(r: dict) -> tuple[int, str]:
        try:
            return (int(r["No."]), r.get("種別", ""))
        except ValueError:
            return (9999, "")
    all_rows.sort(key=sort_key)

    fieldnames = ["No.", "名前", "H", "A", "B", "C", "D", "S",
                  "タイプ", "", "合計", "種別", "SV内定", "未進化"]

    with open(DST_RACE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"  -> {DST_RACE}")
    print(f"  既存: {len(rows)} 行 + メガシンカ: {len(mega_rows)} 行 = 合計 {len(all_rows)} 行")


def build_list_wepon_csv() -> None:
    """list_wepon.csv をコピー"""
    print(f"list_wepon.csv をコピー中...")
    shutil.copy2(SRC_WEPON, DST_WEPON)
    with open(DST_WEPON, encoding="utf-8-sig") as f:
        count = sum(1 for _ in f) - 1  # ヘッダを除く
    print(f"  -> {DST_WEPON} ({count} 件)")


if __name__ == "__main__":
    DST_DIR.mkdir(parents=True, exist_ok=True)
    build_race_value_csv()
    build_list_wepon_csv()
    print("\n完了")

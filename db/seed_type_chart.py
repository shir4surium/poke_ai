"""
タイプ相性テーブルの初期データ投入
18タイプ × 18タイプの全組み合わせを定義する
"""

from schema import get_connection

TYPES = [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"
]

# (攻撃タイプ, 防御タイプ): 倍率
# 記載のないものは 1.0 とする
TYPE_CHART: dict[tuple[str, str], float] = {
    # Normal
    ("Normal",   "Rock"):    0.5,
    ("Normal",   "Ghost"):   0.0,
    ("Normal",   "Steel"):   0.5,
    # Fire
    ("Fire",     "Fire"):    0.5,
    ("Fire",     "Water"):   0.5,
    ("Fire",     "Grass"):   2.0,
    ("Fire",     "Ice"):     2.0,
    ("Fire",     "Bug"):     2.0,
    ("Fire",     "Rock"):    0.5,
    ("Fire",     "Dragon"):  0.5,
    ("Fire",     "Steel"):   2.0,
    # Water
    ("Water",    "Fire"):    2.0,
    ("Water",    "Water"):   0.5,
    ("Water",    "Grass"):   0.5,
    ("Water",    "Ground"):  2.0,
    ("Water",    "Rock"):    2.0,
    ("Water",    "Dragon"):  0.5,
    # Electric
    ("Electric", "Water"):   2.0,
    ("Electric", "Electric"): 0.5,
    ("Electric", "Grass"):   0.5,
    ("Electric", "Ground"):  0.0,
    ("Electric", "Flying"):  2.0,
    ("Electric", "Dragon"):  0.5,
    # Grass
    ("Grass",    "Fire"):    0.5,
    ("Grass",    "Water"):   2.0,
    ("Grass",    "Grass"):   0.5,
    ("Grass",    "Poison"):  0.5,
    ("Grass",    "Ground"):  2.0,
    ("Grass",    "Flying"):  0.5,
    ("Grass",    "Bug"):     0.5,
    ("Grass",    "Rock"):    2.0,
    ("Grass",    "Dragon"):  0.5,
    ("Grass",    "Steel"):   0.5,
    # Ice
    ("Ice",      "Fire"):    0.5,
    ("Ice",      "Water"):   0.5,
    ("Ice",      "Grass"):   2.0,
    ("Ice",      "Ice"):     0.5,
    ("Ice",      "Ground"):  2.0,
    ("Ice",      "Flying"):  2.0,
    ("Ice",      "Dragon"):  2.0,
    ("Ice",      "Steel"):   0.5,
    # Fighting
    ("Fighting", "Normal"):  2.0,
    ("Fighting", "Ice"):     2.0,
    ("Fighting", "Poison"):  0.5,
    ("Fighting", "Flying"):  0.5,
    ("Fighting", "Psychic"): 0.5,
    ("Fighting", "Bug"):     0.5,
    ("Fighting", "Rock"):    2.0,
    ("Fighting", "Ghost"):   0.0,
    ("Fighting", "Dark"):    2.0,
    ("Fighting", "Steel"):   2.0,
    ("Fighting", "Fairy"):   0.5,
    # Poison
    ("Poison",   "Grass"):   2.0,
    ("Poison",   "Poison"):  0.5,
    ("Poison",   "Ground"):  0.5,
    ("Poison",   "Rock"):    0.5,
    ("Poison",   "Ghost"):   0.5,
    ("Poison",   "Steel"):   0.0,
    ("Poison",   "Fairy"):   2.0,
    # Ground
    ("Ground",   "Fire"):    2.0,
    ("Ground",   "Electric"): 2.0,
    ("Ground",   "Grass"):   0.5,
    ("Ground",   "Poison"):  2.0,
    ("Ground",   "Flying"):  0.0,
    ("Ground",   "Bug"):     0.5,
    ("Ground",   "Rock"):    2.0,
    ("Ground",   "Steel"):   2.0,
    # Flying
    ("Flying",   "Electric"): 0.5,
    ("Flying",   "Grass"):   2.0,
    ("Flying",   "Fighting"): 2.0,
    ("Flying",   "Bug"):     2.0,
    ("Flying",   "Rock"):    0.5,
    ("Flying",   "Steel"):   0.5,
    # Psychic
    ("Psychic",  "Fighting"): 2.0,
    ("Psychic",  "Poison"):  2.0,
    ("Psychic",  "Psychic"): 0.5,
    ("Psychic",  "Dark"):    0.0,
    ("Psychic",  "Steel"):   0.5,
    # Bug
    ("Bug",      "Fire"):    0.5,
    ("Bug",      "Grass"):   2.0,
    ("Bug",      "Fighting"): 0.5,
    ("Bug",      "Poison"):  0.5,
    ("Bug",      "Flying"):  0.5,
    ("Bug",      "Psychic"): 2.0,
    ("Bug",      "Ghost"):   0.5,
    ("Bug",      "Dark"):    2.0,
    ("Bug",      "Steel"):   0.5,
    ("Bug",      "Fairy"):   0.5,
    # Rock
    ("Rock",     "Fire"):    2.0,
    ("Rock",     "Ice"):     2.0,
    ("Rock",     "Fighting"): 0.5,
    ("Rock",     "Ground"):  0.5,
    ("Rock",     "Flying"):  2.0,
    ("Rock",     "Bug"):     2.0,
    ("Rock",     "Steel"):   0.5,
    # Ghost
    ("Ghost",    "Normal"):  0.0,
    ("Ghost",    "Psychic"): 2.0,
    ("Ghost",    "Ghost"):   2.0,
    ("Ghost",    "Dark"):    0.5,
    # Dragon
    ("Dragon",   "Dragon"):  2.0,
    ("Dragon",   "Steel"):   0.5,
    ("Dragon",   "Fairy"):   0.0,
    # Dark
    ("Dark",     "Fighting"): 0.5,
    ("Dark",     "Psychic"): 2.0,
    ("Dark",     "Ghost"):   2.0,
    ("Dark",     "Dark"):    0.5,
    ("Dark",     "Fairy"):   0.5,
    # Steel
    ("Steel",    "Fire"):    0.5,
    ("Steel",    "Water"):   0.5,
    ("Steel",    "Electric"): 0.5,
    ("Steel",    "Ice"):     2.0,
    ("Steel",    "Rock"):    2.0,
    ("Steel",    "Steel"):   0.5,
    ("Steel",    "Fairy"):   2.0,
    # Fairy
    ("Fairy",    "Fire"):    0.5,
    ("Fairy",    "Fighting"): 2.0,
    ("Fairy",    "Poison"):  0.5,
    ("Fairy",    "Dragon"):  2.0,
    ("Fairy",    "Dark"):    2.0,
    ("Fairy",    "Steel"):   0.5,
}


def seed_type_chart():
    conn = get_connection()
    c = conn.cursor()
    rows = []
    for atk in TYPES:
        for dfn in TYPES:
            mult = TYPE_CHART.get((atk, dfn), 1.0)
            rows.append((atk, dfn, mult))

    c.executemany(
        "INSERT OR REPLACE INTO type_chart (attacking_type, defending_type, multiplier) VALUES (?, ?, ?)",
        rows
    )
    conn.commit()
    conn.close()
    print(f"[DB] タイプ相性データ投入完了: {len(rows)} 件")


if __name__ == "__main__":
    seed_type_chart()

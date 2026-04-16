"""
game8.jpから取得したメガシンカ種族値でDBを更新するスクリプト
Champions独自メガも追加登録する

タイプ・特性は日本語で管理し、DB挿入時に英語に変換する
（type_chart テーブルとの整合性維持のため）
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "db"))
from schema import get_connection

# ===== タイプ 日→英変換（DBはtype_chartと整合させるため英語で保存）=====
TYPE_EN = {
    "ノーマル":   "Normal",
    "ほのお":     "Fire",
    "みず":       "Water",
    "でんき":     "Electric",
    "くさ":       "Grass",
    "こおり":     "Ice",
    "かくとう":   "Fighting",
    "どく":       "Poison",
    "じめん":     "Ground",
    "ひこう":     "Flying",
    "エスパー":   "Psychic",
    "むし":       "Bug",
    "いわ":       "Rock",
    "ゴースト":   "Ghost",
    "ドラゴン":   "Dragon",
    "あく":       "Dark",
    "はがね":     "Steel",
    "フェアリー": "Fairy",
}

# ===== 特性 日→英変換 =====
ABILITY_EN = {
    "あついしぼう":   "thick-fat",
    "かたいツメ":     "tough-claws",
    "ひでり":         "drought",
    "メガランチャー": "mega-launcher",
    "てきおうりょく": "adaptability",
    "ノーガード":     "no-guard",
    "トレース":       "trace",
    "シェルアーマー": "shell-armor",
    "かげふみ":       "shadow-tag",
    "おやこあい":     "parental-bond",
    "スカイスキン":   "aerilate",
    "かたやぶり":     "mold-breaker",
    "すなおこし":     "sand-stream",
    "ふみん":         "insomnia",
    "ひらいしん":     "lightning-rod",
    "かそく":         "speed-boost",
    "すいすい":       "swift-swim",
    "フェアリースキン": "pixilate",
    "マジックミラー": "magic-bounce",
    "ちからもち":     "huge-power",
    "フィルター":     "filter",
    "ヨガパワー":     "pure-power",
    "いかく":         "intimidate",
    "がんじょうあご": "strong-jaw",
    "ちからずく":     "sheer-force",
    "いたずらごころ": "prankster",
    "フリーズスキン": "refrigerate",
    "すなのちから":   "sand-force",
    "せいしんりょく": "inner-focus",
    "いやしのこころ": "healer",
    "マジックガード": "magic-guard",
    "れんぞくこうげき": "skill-link",
    "テクニシャン":   "technician",
    "サンパワー":     "solar-power",
    "ふゆう":         "levitate",
    "へんげんじざい": "protean",
    "マルチスケイル": "multiscale",
    "ドラゴンスキン": "dragonhide",
    "デルタストリーム": "delta-stream",
    "きもったま":     "scrappy",
    "てつのこぶし":   "iron-fist",
    "フェアリーオーラ": "fairy-aura",
    "しぜんかいふく": "natural-cure",
    "かんそうはだ":   "dry-skin",
    "ゆきふらし":     "snow-warning",
    "てんのめぐみ":   "serene-grace",
    "がんじょう":     "sturdy",
    "あめふらし":     "drizzle",
    "ようりょくそ":   "chlorophyll",
    "もうか":         "blaze",
    "不明":           "unknown",
}

# (ベースEN名, メガEN名, 日本語名, タイプ1(JP), タイプ2(JP), 特性(JP), HP, 攻撃, 防御, 特攻, 特防, 素早さ)
# ★暫定★ は正式データ確認後に更新すること
MEGA_DATA = [
    # ---- PokeAPI標準メガ (game8確認済み) ----
    ("venusaur",   "venusaur-mega",    "メガフシギバナ",   "くさ",     "どく",     "あついしぼう",    80, 100, 123, 122, 120,  80),
    ("charizard",  "charizard-mega-x", "メガリザードンX",  "ほのお",   "ドラゴン", "かたいツメ",      78, 130, 111, 130,  85, 100),
    ("charizard",  "charizard-mega-y", "メガリザードンY",  "ほのお",   "ひこう",   "ひでり",          78, 104,  78, 159, 115, 100),
    ("blastoise",  "blastoise-mega",   "メガカメックス",   "みず",     None,       "メガランチャー",  79, 103, 120, 135, 115,  78),
    ("beedrill",   "beedrill-mega",    "メガスピアー",     "むし",     "どく",     "てきおうりょく",  65, 150,  40,  15,  80, 145),
    ("pidgeot",    "pidgeot-mega",     "メガピジョット",   "ノーマル", "ひこう",   "ノーガード",      83,  80,  80, 135,  80, 121),
    ("alakazam",   "alakazam-mega",    "メガフーディン",   "エスパー", None,       "トレース",        55,  50,  65, 175, 105, 150),
    ("slowbro",    "slowbro-mega",     "メガヤドラン",     "みず",     "エスパー", "シェルアーマー",  95,  75, 180,  30, 135,  30),
    ("gengar",     "gengar-mega",      "メガゲンガー",     "ゴースト", "どく",     "かげふみ",        60,  65,  80, 170,  95, 130),
    ("kangaskhan", "kangaskhan-mega",  "メガガルーラ",     "ノーマル", None,       "おやこあい",     105, 125, 100,  60, 100, 100),
    ("pinsir",     "pinsir-mega",      "メガカイロス",     "むし",     "ひこう",   "スカイスキン",    65, 155, 120,  65,  90, 105),
    ("gyarados",   "gyarados-mega",    "メガギャラドス",   "みず",     "あく",     "かたやぶり",      95, 155, 109,  70, 130,  81),
    ("aerodactyl", "aerodactyl-mega",  "メガプテラ",       "いわ",     "ひこう",   "かたいツメ",      80, 135,  85,  70,  95, 150),
    ("mewtwo",     "mewtwo-mega-x",    "メガミュウツーX",  "エスパー", "かくとう", "ふみん",         106, 190, 100, 154, 100, 130),
    ("mewtwo",     "mewtwo-mega-y",    "メガミュウツーY",  "エスパー", None,       "ふみん",         106, 150,  70, 194, 120, 140),
    ("ampharos",   "ampharos-mega",    "メガデンリュウ",   "でんき",   "ドラゴン", "かたやぶり",      90,  95, 105, 165, 110,  45),
    ("scizor",     "scizor-mega",      "メガハッサム",     "むし",     "はがね",   "テクニシャン",    70, 150, 140,  65, 100,  75),
    ("heracross",  "heracross-mega",   "メガヘラクロス",   "むし",     "かくとう", "れんぞくこうげき", 80, 185, 115,  40, 105,  75),
    ("houndoom",   "houndoom-mega",    "メガヘルガー",     "あく",     "ほのお",   "サンパワー",      75,  90,  90, 140,  90, 115),
    ("tyranitar",  "tyranitar-mega",   "メガバンギラス",   "いわ",     "あく",     "すなおこし",     100, 164, 150,  95, 120,  71),
    ("sceptile",   "sceptile-mega",    "メガジュカイン",   "くさ",     "ドラゴン", "ひらいしん",      70, 110,  75, 145,  85, 145),
    ("blaziken",   "blaziken-mega",    "メガバシャーモ",   "ほのお",   "かくとう", "かそく",          80, 160,  80, 130,  80, 100),
    ("swampert",   "swampert-mega",    "メガラグラージ",   "みず",     "じめん",   "すいすい",       100, 150, 110,  95, 110,  70),
    ("gardevoir",  "gardevoir-mega",   "メガサーナイト",   "エスパー", "フェアリー","フェアリースキン", 68,  85,  65, 165, 135, 100),
    ("sableye",    "sableye-mega",     "メガヤミラミ",     "あく",     "ゴースト", "マジックミラー",  50,  85, 125,  85, 115,  20),
    ("mawile",     "mawile-mega",      "メガクチート",     "はがね",   "フェアリー","ちからもち",      50, 105, 125,  55,  95,  50),
    ("aggron",     "aggron-mega",      "メガボスゴドラ",   "はがね",   None,       "フィルター",      70, 140, 230,  60,  80,  50),
    ("medicham",   "medicham-mega",    "メガチャーレム",   "かくとう", "エスパー", "ヨガパワー",      60, 100,  85,  80,  85, 100),
    ("manectric",  "manectric-mega",   "メガライボルト",   "でんき",   None,       "いかく",          70,  75,  80, 135,  80, 135),
    ("sharpedo",   "sharpedo-mega",    "メガサメハダー",   "みず",     "あく",     "がんじょうあご",  70, 140,  70, 110,  65, 105),
    ("camerupt",   "camerupt-mega",    "メガバクーダ",     "ほのお",   "じめん",   "ちからずく",      70, 120, 100, 145, 105,  20),
    ("altaria",    "altaria-mega",     "メガチルタリス",   "ドラゴン", "フェアリー","フェアリースキン", 75, 110, 110, 110, 105,  80),
    ("banette",    "banette-mega",     "メガジュペッタ",   "ゴースト", None,       "いたずらごころ",  64, 165,  75,  93,  83,  75),
    ("absol",      "absol-mega",       "メガアブソル",     "あく",     None,       "マジックミラー",  65, 150,  60, 115,  60, 115),
    ("glalie",     "glalie-mega",      "メガオニゴーリ",   "こおり",   None,       "フリーズスキン",  80, 120,  80, 120,  80, 100),
    ("salamence",  "salamence-mega",   "メガボーマンダ",   "ドラゴン", "ひこう",   "スカイスキン",    95, 145, 130, 120,  90, 120),
    ("latias",     "latias-mega",      "メガラティアス",   "ドラゴン", "エスパー", "てきおうりょく",  80, 100, 120, 140, 150, 110),
    ("latios",     "latios-mega",      "メガラティオス",   "ドラゴン", "エスパー", "てきおうりょく",  80, 130, 100, 160, 120, 110),
    ("rayquaza",   "rayquaza-mega",    "メガレックウザ",   "ドラゴン", "ひこう",   "デルタストリーム",105, 180, 100, 180, 100, 115),
    ("lopunny",    "lopunny-mega",     "メガミミロップ",   "ノーマル", "かくとう", "きもったま",      65, 136,  94,  54,  96, 135),
    ("garchomp",   "garchomp-mega",    "メガガブリアス",   "ドラゴン", "じめん",   "すなのちから",   108, 170, 115, 120,  95,  92),
    ("lucario",    "lucario-mega",     "メガルカリオ",     "かくとう", "はがね",   "てきおうりょく", 147, 197, 108, 144,  90, 180),
    ("abomasnow",  "abomasnow-mega",   "メガユキノオー",   "くさ",     "こおり",   "ゆきふらし",      90, 132, 105, 132, 105,  30),
    ("gallade",    "gallade-mega",     "メガエルレイド",   "エスパー", "かくとう", "せいしんりょく",  68, 165,  95,  65, 115, 110),
    ("audino",     "audino-mega",      "メガタブンネ",     "ノーマル", "フェアリー","いやしのこころ", 103,  60, 126,  80, 126,  50),
    ("diancie",    "diancie-mega",     "メガディアンシー", "いわ",     "フェアリー","マジックミラー",  50, 160, 110, 160, 110, 110),
    ("steelix",    "steelix-mega",     "メガハガネール",   "はがね",   "じめん",   "すなのちから",    75, 125, 230,  55,  95,  30),
    # ---- Champions独自メガ (game8確認済み) ----
    ("feraligatr", "feraligatr-mega",  "メガオーダイル",   "みず",     "ドラゴン", "ドラゴンスキン",  85, 160, 125,  89,  93,  78),
    ("meganium",   "meganium-mega",    "メガメガニウム",   "くさ",     "フェアリー","サンパワー",      80,  92, 115, 143, 115,  80),
    ("dragonite",  "dragonite-mega",   "メガカイリュー",   "ドラゴン", "ひこう",   "マルチスケイル", 167, 129, 136, 216, 145, 152),
    ("braixen",    "braixen-mega",     "メガマフォクシー", "ほのお",   "エスパー", "ふゆう",         151,  80,  93, 211, 145, 204),
    ("greninja",   "greninja-mega",    "メガゲッコウガ",   "みず",     "あく",     "へんげんじざい",  72, 125,  77, 133,  81, 142),
    ("emboar",     "emboar-mega",      "メガエンブオー",   "ほのお",   "かくとう", "かたやぶり",     110, 148,  75, 110, 110,  75),
    ("froslass",   "froslass-mega",    "メガユキメノコ",   "こおり",   "ゴースト", "ゆきふらし",      70,  80,  70, 140, 100, 120),
    ("clefable",   "clefable-mega",    "メガピクシー",     "フェアリー","ひこう",  "マジックガード",  95,  80,  93, 135, 110,  70),
    ("floette",    "floette-mega",     "メガフラエッテ",   "フェアリー", None,     "フェアリーオーラ",74,  85,  87, 155, 148, 102),
    ("crabominable","crabominable-mega","メガケケンカニ",   "かくとう", "こおり",   "てつのこぶし",    97, 157, 122,  62, 107,  33),
    # ---- ★暫定★ (正式データ確認後に更新すること) ----
    ("typhlosion", "typhlosion-mega",  "メガバクフーン",   "ほのお",   None,       "もうか",          78,  84,  78, 155, 110,  95),
    ("togekiss",   "togekiss-mega",    "メガトゲキッス",   "フェアリー","ひこう",  "てんのめぐみ",    85,  60,  95, 145, 130,  85),
    ("donphan",    "donphan-mega",     "メガドンファン",   "じめん",   None,       "がんじょう",      90, 130, 130,  55,  65,  35),
    ("sudowoodo",  "sudowoodo-mega",   "メガウソッキー",   "いわ",     None,       "がんじょう",      70, 115, 130,  30,  65,  30),
    ("politoed",   "politoed-mega",    "メガニョロトノ",   "みず",     None,       "あめふらし",      90,  75,  75, 110, 110,  70),
    ("victreebel", "victreebel-mega",  "メガウツボット",   "くさ",     "どく",     "ようりょくそ",    80, 115,  60, 130,  70,  95),
    ("starmie",    "starmie-mega",     "メガスターミー",   "みず",     "エスパー", "しぜんかいふく",  60,  75,  85, 130, 110, 115),
    ("cloyster",   "cloyster-mega",    "メガパルシェン",   "みず",     "こおり",   "れんぞくこうげき", 50, 105, 200,  85,  45,  80),
    ("kingdra",    "kingdra-mega",     "メガキングドラ",   "みず",     "ドラゴン", "すいすい",        75,  95, 110, 120, 110,  85),
    ("mr-mime",    "mr-mime-mega",     "メガバリヤード",   "エスパー", "フェアリー","フィルター",      40,  45,  65, 120, 120,  90),
    ("jynx",       "jynx-mega",        "メガルージュラ",   "こおり",   "エスパー", "かんそうはだ",    65,  50,  35, 135,  95,  95),
]

# Champions独自メガのベースポケモンで未登録のもの
NEW_BASE_POKEMON = {
    "braixen":      ("マフォクシー",  "Fire",     "Psychic", 59,  59,  58,  90,  70,  73),
    "greninja":     ("ゲッコウガ",    "Water",    "Dark",    72,  95,  67, 103,  71, 122),
    "emboar":       ("エンブオー",    "Fire",     "Fighting",110, 123,  65, 100,  65,  65),
    "froslass":     ("ユキメノコ",    "Ice",      "Ghost",   70,  80,  70,  80,  70, 110),
    "clefable":     ("ピクシー",      "Fairy",    None,      95,  70,  73,  95,  90,  60),
    "floette":      ("フラエッテ",    "Fairy",    None,      54,  45,  47,  75,  98,  52),
    "crabominable": ("ケケンカニ",    "Fighting", "Ice",     97, 132,  77,  62,  67,  43),
}


def run():
    conn = get_connection()
    c = conn.cursor()

    # ベースポケモン仮登録
    for en, (jp, t1, t2, hp, atk, def_, spa, spd, spe) in NEW_BASE_POKEMON.items():
        c.execute("SELECT 1 FROM pokemon WHERE name_en=?", (en,))
        if not c.fetchone():
            c.execute(
                "INSERT INTO pokemon (name_en,name_jp,type1,type2,hp,attack,defense,"
                "sp_attack,sp_defense,speed,is_available) VALUES (?,?,?,?,?,?,?,?,?,?,1)",
                (en, jp, t1, t2, hp, atk, def_, spa, spd, spe)
            )
            print(f"ポケモン仮登録: {jp}({en})")

    updated, inserted = 0, 0
    for (base_en, mega_en, name_jp, t1_jp, t2_jp, ability_jp,
         hp, atk, def_, spa, spd, spe) in MEGA_DATA:
        # 日→英変換（DB保存はtype_chartと整合させるため英語）
        t1 = TYPE_EN.get(t1_jp, t1_jp) if t1_jp else None
        t2 = TYPE_EN.get(t2_jp, t2_jp) if t2_jp else None
        ability = ABILITY_EN.get(ability_jp, ability_jp)

        c.execute("SELECT 1 FROM pokemon WHERE name_en=?", (base_en,))
        if not c.fetchone():
            print(f"警告: ベース未登録スキップ {base_en}")
            continue

        c.execute("SELECT 1 FROM mega_evolution WHERE mega_name_en=?", (mega_en,))
        if c.fetchone():
            c.execute(
                "UPDATE mega_evolution SET mega_name_jp=?,type1=?,type2=?,ability=?,"
                "hp=?,attack=?,defense=?,sp_attack=?,sp_defense=?,speed=? "
                "WHERE mega_name_en=?",
                (name_jp, t1, t2, ability, hp, atk, def_, spa, spd, spe, mega_en)
            )
            updated += 1
        else:
            c.execute(
                "INSERT INTO mega_evolution (base_pokemon_en,mega_name_jp,mega_name_en,"
                "mega_stone,type1,type2,hp,attack,defense,sp_attack,sp_defense,speed,ability)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (base_en, name_jp, mega_en, "", t1, t2, hp, atk, def_, spa, spd, spe, ability)
            )
            inserted += 1
        print(f"  {name_jp}({mega_en}): {hp}/{atk}/{def_}/{spa}/{spd}/{spe}")

    conn.commit()
    c.execute("SELECT COUNT(*) FROM mega_evolution")
    total = c.fetchone()[0]
    conn.close()
    print(f"\n完了: 更新={updated}, 新規追加={inserted}, 合計={total}件")


if __name__ == "__main__":
    run()

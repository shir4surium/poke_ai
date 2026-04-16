"""
JSONファイルのポケモン名・タイプ・特性を日本語に変換するスクリプト
対象: champions_roster.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "db"))
from schema import get_connection

# ===== タイプ 英→日マッピング =====
TYPE_JP = {
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

# ===== 特性 英→日マッピング =====
ABILITY_JP = {
    "thick-fat":      "あついしぼう",
    "tough-claws":    "かたいツメ",
    "drought":        "ひでり",
    "mega-launcher":  "メガランチャー",
    "adaptability":   "てきおうりょく",
    "no-guard":       "ノーガード",
    "trace":          "トレース",
    "shell-armor":    "シェルアーマー",
    "shadow-tag":     "かげふみ",
    "parental-bond":  "おやこあい",
    "aerilate":       "スカイスキン",
    "mold-breaker":   "かたやぶり",
    "sand-stream":    "すなおこし",
    "steadfast":      "ふみん",
    "insomnia":       "ふみん",
    "lightning-rod":  "ひらいしん",
    "speed-boost":    "かそく",
    "swift-swim":     "すいすい",
    "pixilate":       "フェアリースキン",
    "magic-bounce":   "マジックミラー",
    "huge-power":     "ちからもち",
    "filter":         "フィルター",
    "pure-power":     "ヨガパワー",
    "intimidate":     "いかく",
    "strong-jaw":     "がんじょうあご",
    "sheer-force":    "ちからずく",
    "prankster":      "いたずらごころ",
    "refrigerate":    "フリーズスキン",
    "sand-force":     "すなのちから",
    "inner-focus":    "せいしんりょく",
    "healer":         "いやしのこころ",
    "magic-guard":    "マジックガード",
    "skill-link":     "れんぞくこうげき",
    "technician":     "テクニシャン",
    "solar-power":    "サンパワー",
    "levitate":       "ふゆう",
    "protean":        "へんげんじざい",
    "multiscale":     "マルチスケイル",
    "dragonhide":     "ドラゴンスキン",
    "delta-stream":   "デルタストリーム",
    "scrappy":        "きもったま",
    "iron-fist":      "てつのこぶし",
    "fairy-aura":     "フェアリーオーラ",
    "natural-cure":   "しぜんかいふく",
    "dry-skin":       "かんそうはだ",
    "snow-warning":   "ゆきふらし",
    "serene-grace":   "てんのめぐみ",
    "sturdy":         "がんじょう",
    "drizzle":        "あめふらし",
    "chlorophyll":    "ようりょくそ",
    "blaze":          "もうか",
    "torrent":        "げきりゅう",
    "overgrow":       "しんりょく",
    "static":         "せいでんき",
    "pressure":       "プレッシャー",
    "synchronize":    "シンクロ",
    "levitate":       "ふゆう",
    "unnerve":        "きんちょうかん",
    "unknown":        "不明",
}

# ===== アイテムカテゴリ 英→日 =====
CATEGORY_JP = {
    "general":   "どうぐ",
    "berries":   "きのみ",
    "MegaStone": "メガストーン",
    "Choice":    "こだわり系",
}


def build_en_to_jp_pokemon() -> dict:
    """DBから英語名→日本語名マッピングを構築"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT name_en, name_jp FROM pokemon")
    mapping = {r["name_en"]: r["name_jp"] for r in c.fetchall()}
    conn.close()
    return mapping


def localize_roster():
    roster_path = Path(__file__).parent / "champions_roster.json"
    roster = json.loads(roster_path.read_text(encoding="utf-8"))

    en_to_jp = build_en_to_jp_pokemon()

    # ===== available_pokemon: EN文字列 or {jp,en}辞書 → {jp, en} オブジェクト =====
    new_pokemon_list = []
    unmapped = []
    for item in roster["available_pokemon"]:
        # すでに辞書形式の場合はEN名を取り出す
        en = item["en"] if isinstance(item, dict) else item
        jp = en_to_jp.get(en)
        if jp:
            new_pokemon_list.append({"jp": jp, "en": en})
        else:
            new_pokemon_list.append({"jp": en, "en": en})
            unmapped.append(en)

    if unmapped:
        print(f"警告: JP名未解決 {len(unmapped)}件: {unmapped[:5]}")
    roster["available_pokemon"] = new_pokemon_list

    # ===== mega_evolutions: タイプ・特性を日本語化 =====
    new_megas = {}
    for base_en, info in roster["mega_evolutions"].items():
        if base_en == "_comment":
            new_megas[base_en] = info
            continue

        new_info = dict(info)

        # X/Y両形態
        if "mega_name_x" in info:
            new_info["stone_x_jp"] = _jp_stone(info.get("stone_x", ""))
            new_info["stone_y_jp"] = _jp_stone(info.get("stone_y", ""))
        else:
            new_info["stone_jp"] = _jp_stone(info.get("stone", ""))

        new_megas[base_en] = new_info

    roster["mega_evolutions"] = new_megas

    # ===== items: カテゴリ名を日本語追加 =====
    new_items = {}
    for cat_en, items in roster["items"].items():
        cat_jp = CATEGORY_JP.get(cat_en, cat_en)
        new_items[cat_jp] = items
    roster["items"] = new_items

    # 書き出し
    roster_path.write_text(
        json.dumps(roster, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"champions_roster.json 日本語化完了: ポケモン{len(new_pokemon_list)}件")


def _jp_stone(stone_en: str) -> str:
    """メガストーン名をそのまま（日本語はgame8データ準拠のため変更不要）"""
    # メガストーン名は既にgame8から日本語対応済み石名を使用予定
    # 現状は英語のまま返す（後でgamewithデータで補完）
    return stone_en


def generate_mega_reference():
    """メガシンカの日本語参照JSONを生成（DBから）"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT m.mega_name_jp, m.mega_name_en, m.base_pokemon_en,
               p.name_jp as base_jp,
               m.type1, m.type2, m.ability,
               m.hp, m.attack, m.defense, m.sp_attack, m.sp_defense, m.speed,
               m.mega_stone
        FROM mega_evolution m
        JOIN pokemon p ON m.base_pokemon_en = p.name_en
        ORDER BY m.mega_name_en
    """)
    rows = c.fetchall()
    conn.close()

    ref = []
    for r in rows:
        total = r["hp"] + r["attack"] + r["defense"] + r["sp_attack"] + r["sp_defense"] + r["speed"]
        ref.append({
            "日本語名":  r["mega_name_jp"],
            "英語名":    r["mega_name_en"],
            "ベース":    r["base_jp"],
            "タイプ1":   TYPE_JP.get(r["type1"], r["type1"]),
            "タイプ2":   TYPE_JP.get(r["type2"], r["type2"]) if r["type2"] else None,
            "特性":      ABILITY_JP.get(r["ability"], r["ability"]),
            "種族値": {
                "HP":  r["hp"],
                "こうげき": r["attack"],
                "ぼうぎょ": r["defense"],
                "とくこう": r["sp_attack"],
                "とくぼう": r["sp_defense"],
                "すばやさ": r["speed"],
                "合計":    total,
            },
            "メガストーン": r["mega_stone"],
            "英語名_en":   r["mega_name_en"],
        })

    out_path = Path(__file__).parent / "mega_reference_jp.json"
    out_path.write_text(
        json.dumps(ref, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"mega_reference_jp.json 生成完了: {len(ref)}件")
    return ref


def generate_pokemon_reference():
    """ポケモン全データの日本語参照JSONを生成（DBから）"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT name_jp, name_en, type1, type2,
               hp, attack, defense, sp_attack, sp_defense, speed,
               ability1, ability2, hidden_ability
        FROM pokemon WHERE is_available = 1
        ORDER BY name_jp
    """)
    rows = c.fetchall()
    conn.close()

    ref = []
    for r in rows:
        ref.append({
            "日本語名":  r["name_jp"],
            "英語名":    r["name_en"],
            "タイプ1":   TYPE_JP.get(r["type1"], r["type1"]),
            "タイプ2":   TYPE_JP.get(r["type2"], r["type2"]) if r["type2"] else None,
            "種族値": {
                "HP":       r["hp"],
                "こうげき": r["attack"],
                "ぼうぎょ": r["defense"],
                "とくこう": r["sp_attack"],
                "とくぼう": r["sp_defense"],
                "すばやさ": r["speed"],
                "合計":     r["hp"]+r["attack"]+r["defense"]+r["sp_attack"]+r["sp_defense"]+r["speed"],
            },
            "特性1":     ABILITY_JP.get(r["ability1"], r["ability1"]) if r["ability1"] else None,
            "特性2":     ABILITY_JP.get(r["ability2"], r["ability2"]) if r["ability2"] else None,
            "夢特性":    ABILITY_JP.get(r["hidden_ability"], r["hidden_ability"]) if r["hidden_ability"] else None,
        })

    out_path = Path(__file__).parent / "pokemon_reference_jp.json"
    out_path.write_text(
        json.dumps(ref, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"pokemon_reference_jp.json 生成完了: {len(ref)}件")


if __name__ == "__main__":
    print("=== JSONファイル日本語化 ===")
    localize_roster()
    print("\n=== メガシンカ参照JSON生成 ===")
    generate_mega_reference()
    print("\n=== ポケモン参照JSON生成 ===")
    generate_pokemon_reference()
    print("\n完了")

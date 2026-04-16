"""
Phase 2: DBシーディングスクリプト

champions_roster.json を読み込み、PokeAPI からデータを取得して
champions.db に投入する。

実行順:
  1. seed_pokemon()   - ポケモン基本データ
  2. seed_mega()      - メガシンカデータ
  3. seed_items()     - アイテムデータ
"""

import json
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "db"))
from schema import get_connection, init_db
from seed_type_chart import seed_type_chart
from pokeapi_client import fetch_pokemon, fetch_item

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROSTER_PATH = Path(__file__).parent / "champions_roster.json"

# PokeAPI stat名 → DBカラム名マッピング
STAT_MAP = {
    "hp":              "hp",
    "attack":          "attack",
    "defense":         "defense",
    "special-attack":  "sp_attack",
    "special-defense": "sp_defense",
    "speed":           "speed",
}

# タイプ名の正規化 (PokeAPI → DB統一表記)
def normalize_type(t: str) -> str:
    return t.capitalize()


def seed_pokemon(roster: dict):
    """PokeAPI からポケモン基本データを取得してDBに投入"""
    conn = get_connection()
    c = conn.cursor()

    available = set(roster["available_pokemon"])
    total = len(available)
    ok, skip, fail = 0, 0, 0

    for i, name in enumerate(sorted(available), 1):
        # 既に登録済みならスキップ
        c.execute("SELECT 1 FROM pokemon WHERE name_en = ?", (name,))
        if c.fetchone():
            skip += 1
            continue

        logger.info(f"[{i}/{total}] 取得中: {name}")
        data = fetch_pokemon(name)
        if data is None:
            logger.warning(f"  スキップ (取得失敗): {name}")
            fail += 1
            continue

        # ステータス抽出
        stats = {s["stat"]["name"]: s["base_stat"] for s in data["stats"]}

        # タイプ
        types = [t["type"]["name"] for t in data["types"]]
        type1 = normalize_type(types[0])
        type2 = normalize_type(types[1]) if len(types) > 1 else None

        # 特性
        abilities = [a["ability"]["name"] for a in data["abilities"]]
        hidden_abilities = [
            a["ability"]["name"] for a in data["abilities"] if a.get("is_hidden")
        ]
        normal_abilities = [
            a["ability"]["name"] for a in data["abilities"] if not a.get("is_hidden")
        ]

        ability1 = normal_abilities[0] if len(normal_abilities) > 0 else None
        ability2 = normal_abilities[1] if len(normal_abilities) > 1 else None
        hidden_ability = hidden_abilities[0] if hidden_abilities else None

        # 日本語名: PokeAPI species から取得（キャッシュ済みなら利用）
        name_jp = _fetch_jp_name(name)

        try:
            c.execute("""
                INSERT OR REPLACE INTO pokemon
                (name_en, name_jp, type1, type2,
                 hp, attack, defense, sp_attack, sp_defense, speed,
                 ability1, ability2, hidden_ability, is_available)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                name, name_jp, type1, type2,
                stats.get("hp", 0),
                stats.get("attack", 0),
                stats.get("defense", 0),
                stats.get("special-attack", 0),
                stats.get("special-defense", 0),
                stats.get("speed", 0),
                ability1, ability2, hidden_ability,
            ))
            ok += 1
        except Exception as e:
            logger.error(f"  DB挿入失敗 {name}: {e}")
            fail += 1

    conn.commit()
    conn.close()
    logger.info(f"ポケモン投入完了: 成功={ok}, スキップ={skip}, 失敗={fail}")


def _fetch_jp_name(pokemon_en: str) -> str:
    """
    PokeAPI species エンドポイントから日本語名を取得する。
    メガ形態 (venusaur-mega, charizard-mega-x など) はベース名で検索する。
    """
    from pokeapi_client import fetch
    import re
    # メガ形態のベース名を抽出 (例: charizard-mega-x → charizard)
    base = re.sub(r"-mega.*$", "", pokemon_en)
    data = fetch(f"pokemon-species/{base}")
    if data is None:
        return pokemon_en
    for entry in data.get("names", []):
        if entry["language"]["name"] == "ja":
            jp_base = entry["name"]
            # メガ形態の場合は「メガ○○」「メガ○○X/Y」の形式で返す
            if "-mega" in pokemon_en:
                suffix = ""
                if pokemon_en.endswith("-x"):
                    suffix = "X"
                elif pokemon_en.endswith("-y"):
                    suffix = "Y"
                return f"メガ{jp_base}{suffix}"
            return jp_base
    return pokemon_en


def seed_mega(roster: dict):
    """メガシンカデータをDBに投入。PokeAPI既存メガとChampions独自メガを区別して処理"""
    conn = get_connection()
    c = conn.cursor()

    mega_data = roster.get("mega_evolutions", {})
    ok, skip_excl, fail = 0, 0, 0

    for base_name, info in mega_data.items():
        if base_name == "_comment":
            continue

        # X/Y両形態がある場合
        if "mega_name_x" in info:
            entries = [
                (info["mega_name_x"], info["stone_x"], False),
                (info["mega_name_y"], info["stone_y"], False),
            ]
        else:
            is_excl = info.get("champions_exclusive", False)
            entries = [(info.get("mega_name", ""), info.get("stone", ""), is_excl)]

        for mega_name, stone, is_exclusive in entries:
            if not mega_name:
                continue

            # 既に登録済みか確認
            c.execute("SELECT 1 FROM mega_evolution WHERE mega_name_en = ?", (mega_name,))
            if c.fetchone():
                continue

            # ベースポケモンが存在するか確認
            c.execute("SELECT type1, type2, hp, attack, defense, sp_attack, sp_defense, speed FROM pokemon WHERE name_en = ?", (base_name,))
            base_row = c.fetchone()
            if not base_row:
                logger.warning(f"  ベースポケモン未登録のためスキップ: {base_name}")
                continue

            if is_exclusive:
                # Champions独自メガ: PokeAPIに存在しないためベースポケモンのデータをコピー
                logger.info(f"  [Champions独自] {mega_name} (ベースデータ使用)")
                stats = {
                    "hp": base_row["hp"], "attack": base_row["attack"],
                    "defense": base_row["defense"], "special-attack": base_row["sp_attack"],
                    "special-defense": base_row["sp_defense"], "speed": base_row["speed"],
                }
                type1 = base_row["type1"]
                type2 = base_row["type2"]
                ability = "unknown"
                name_jp = mega_name  # 正確な日本語名は後で手動更新
                skip_excl += 1
            else:
                logger.info(f"  [PokeAPI] {mega_name}")
                data = fetch_pokemon(mega_name)
                if data is None:
                    logger.warning(f"  スキップ (取得失敗): {mega_name}")
                    fail += 1
                    continue
                stats = {s["stat"]["name"]: s["base_stat"] for s in data["stats"]}
                types = [t["type"]["name"] for t in data["types"]]
                type1 = normalize_type(types[0])
                type2 = normalize_type(types[1]) if len(types) > 1 else None
                abilities = [a["ability"]["name"] for a in data["abilities"]]
                ability = abilities[0] if abilities else ""
                name_jp = _fetch_jp_name(mega_name)

            try:
                c.execute("""
                    INSERT OR REPLACE INTO mega_evolution
                    (base_pokemon_en, mega_name_jp, mega_name_en, mega_stone,
                     type1, type2, hp, attack, defense, sp_attack, sp_defense, speed, ability)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    base_name, name_jp, mega_name, stone,
                    type1, type2,
                    stats.get("hp", 0), stats.get("attack", 0), stats.get("defense", 0),
                    stats.get("special-attack", 0), stats.get("special-defense", 0),
                    stats.get("speed", 0), ability,
                ))
                ok += 1
            except Exception as e:
                logger.error(f"  DB挿入失敗 {mega_name}: {e}")
                fail += 1

    conn.commit()
    conn.close()
    logger.info(f"メガシンカ投入完了: 成功={ok}, Champions独自(要確認)={skip_excl}, 失敗={fail}")


def seed_items(roster: dict):
    """アイテムデータをPokeAPIから取得してDBに投入"""
    conn = get_connection()
    c = conn.cursor()

    items_data = roster.get("items", {})
    ok, skip, fail = 0, 0, 0

    for category, items in items_data.items():
        for item in items:
            name_en = item["name_en"]
            name_jp = item["name_jp"]

            c.execute("SELECT 1 FROM item WHERE name_en = ?", (name_en,))
            if c.fetchone():
                skip += 1
                continue

            logger.info(f"アイテム取得中: {name_en}")
            data = fetch_item(name_en)
            description = ""
            if data:
                for entry in data.get("flavor_text_entries", []):
                    if entry.get("language", {}).get("name") == "ja":
                        description = entry.get("text", "").replace("\n", " ")
                        break

            try:
                c.execute("""
                    INSERT OR REPLACE INTO item (name_jp, name_en, category, description)
                    VALUES (?, ?, ?, ?)
                """, (name_jp, name_en, category, description))
                ok += 1
            except Exception as e:
                logger.error(f"  DB挿入失敗 {name_en}: {e}")
                fail += 1

    conn.commit()
    conn.close()
    logger.info(f"アイテム投入完了: 成功={ok}, スキップ={skip}, 失敗={fail}")


def run():
    roster = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))

    logger.info("=== DBスキーマ初期化 ===")
    init_db()
    seed_type_chart()

    logger.info("=== ポケモン基本データ投入 ===")
    seed_pokemon(roster)

    logger.info("=== メガシンカデータ投入 ===")
    seed_mega(roster)

    logger.info("=== アイテムデータ投入 ===")
    seed_items(roster)

    logger.info("=== Phase 2 完了 ===")


if __name__ == "__main__":
    run()

"""
Champions AI - DB から _tmp_jsdata.js を再生成するスクリプト
Render のビルド時や DB 更新後に実行する。
"""
import sys, sqlite3, json, csv
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).parent.parent
DB_PATH  = BASE_DIR / 'db' / 'champions.db'
CSV_PATH = BASE_DIR / 'data' / 'list_wepon.csv'
OUT_PATH = Path(__file__).parent / '_tmp_jsdata.js'

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ─── POKEMON_DATA ───
    cur.execute('''
        SELECT p.name_jp, p.name_en,
               p.ability1, p.ability2, p.hidden_ability
        FROM   pokemon p
        WHERE  p.is_available = 1
        ORDER  BY p.name_jp
    ''')
    pokemon_list = []
    for r in cur.fetchall():
        abilities = [a for a in [r['ability1'], r['ability2'], r['hidden_ability']] if a]
        pokemon_list.append({'n': r['name_jp'], 'e': r['name_en'], 'a': abilities})

    # ─── ITEMS_LIST (メガストーン以外) ───
    cur.execute('''
        SELECT name_jp FROM item
        WHERE  category != 'MegaStone'
        ORDER  BY name_jp
    ''')
    items_list = [r[0] for r in cur.fetchall()]

    # ─── MEGA_MAP ───
    cur.execute('''
        SELECT m.base_pokemon_en, m.mega_name_jp, m.mega_stone
        FROM   mega_evolution m
        ORDER  BY m.base_pokemon_en, m.mega_name_jp
    ''')
    mega_map: dict[str, list] = {}
    for r in cur.fetchall():
        key = r[0]
        if key not in mega_map:
            mega_map[key] = []
        mega_map[key].append({'m': r[1], 's': r[2] or ''})

    conn.close()

    # ─── MOVES_LIST (list_wepon.csv) ───
    moves_list = []
    if CSV_PATH.exists():
        with open(CSV_PATH, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            # 技名の列を探す（「技名」「name」「名前」等）
            for row in reader:
                name = row.get('技名') or row.get('name') or row.get('名前') or list(row.values())[0]
                if name and name.strip():
                    moves_list.append(name.strip())

    # ─── JS 出力 ───
    out = []
    out.append('const MOVES_LIST = ' + json.dumps(moves_list, ensure_ascii=False) + ';')
    out.append('const ITEMS_LIST = ' + json.dumps(items_list, ensure_ascii=False) + ';')
    out.append('const MEGA_MAP = ' + json.dumps(mega_map, ensure_ascii=False) + ';')
    out.append('const POKEMON_DATA = ' + json.dumps(pokemon_list, ensure_ascii=False) + ';')

    OUT_PATH.write_text('\n'.join(out), encoding='utf-8')
    print(f'Written: {OUT_PATH.stat().st_size} bytes')
    print(f'  POKEMON_DATA: {len(pokemon_list)}件')
    print(f'  MOVES_LIST:   {len(moves_list)}件')
    print(f'  ITEMS_LIST:   {len(items_list)}件')
    print(f'  MEGA_MAP:     {len(mega_map)}件')

if __name__ == '__main__':
    main()

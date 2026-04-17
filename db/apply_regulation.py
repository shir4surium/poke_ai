"""
Champions AI - MA-1 レギュレーション適用スクリプト
- pokemon テーブルに regulation カラムを追加
- MA-1 リストのポケモンに regulation='champions-ma-1', is_available=1 を設定
- MA-1 リスト外のポケモンは is_available=0 に設定
"""
import sqlite3, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = Path(__file__).parent / 'champions.db'

# ===== MA-1 対象ポケモン（DB の name_jp 形式） =====
MA1_JP = [
    # Gen1
    'フシギバナ', 'リザードン', 'カメックス', 'スピアー', 'ピジョット',
    'アーボック', 'ピカチュウ', 'ライチュウ', 'ライチュウ(アローラ)',
    'ピクシー', 'キュウコン', 'キュウコン(アローラ)',
    'ウインディ', 'ウインディ(ヒスイ)', 'フーディン', 'カイリキー',
    'ウツボット', 'ヤドラン', 'ヤドラン(ガラル)', 'ゲンガー',
    'ガルーラ', 'スターミー', 'カイロス',
    'ケンタロス',
    'ケンタロス(パルデア単)', 'ケンタロス(パルデア炎)', 'ケンタロス(パルデア水)',
    'ギャラドス', 'メタモン', 'シャワーズ', 'サンダース', 'ブースター',
    'プテラ', 'カビゴン', 'カイリュー',
    # Gen2
    'メガニウム', 'バクフーン', 'バクフーン(ヒスイ)', 'オーダイル',
    'アリアドス', 'デンリュウ', 'マリルリ', 'ニョロトノ',
    'エーフィ', 'ブラッキー', 'ヤドキング', 'ヤドキング(ガラル)',
    'フォレトス', 'ハガネール', 'ハッサム', 'ヘラクロス',
    'エアームド', 'ヘルガー', 'バンギラス',
    # Gen3
    'ペリッパー', 'サーナイト', 'ヤミラミ', 'ボスゴドラ',
    'チャーレム', 'ライボルト', 'サメハダー', 'バクーダ',
    'コータス', 'チルタリス', 'ミロカロス', 'ポワルン',
    'ジュペッタ', 'チリーン', 'アブソル', 'オニゴーリ',
    # Gen4
    'ドダイトス', 'ゴウカザル', 'エンペルト', 'レントラー',
    'ロズレイド', 'ラムパルド', 'トリデプス', 'ミミロップ',
    'ミカルゲ', 'ガブリアス', 'ルカリオ', 'カバルドン',
    'ドクロッグ', 'ユキノオー', 'マニューラ', 'ドサイドン',
    'リーフィア', 'グレイシア', 'グライオン', 'マンムー',
    'エルレイド', 'ユキメノコ',
    # ロトム（6フォルム）
    'ロトム', 'ヒートロトム', 'ウォッシュロトム', 'フロストロトム', 'スピンロトム', 'カットロトム',
    # Gen5
    'ジャローダ', 'エンブオー', 'ダイケンキ', 'ダイケンキ(ヒスイ)',
    'ミルホッグ', 'レパルダス', 'ヤナッキー', 'バオッキー', 'ヒヤッキー',
    'ドリュウズ', 'タブンネ', 'ローブシン', 'エルフーン', 'ワルビアル',
    'デスカーン', 'ダストダス', 'ゾロアーク', 'ゾロアーク(ヒスイ)',
    'ランクルス', 'バイバニラ', 'エモンガ', 'シャンデラ', 'ツンベアー',
    'マッギョ', 'マッギョ(ガラル)', 'ゴルーグ', 'サザンドラ', 'ウルガモス',
    # Gen6
    'ブリガロン', 'マフォクシー', 'ゲッコウガ', 'ホルード', 'ファイアロー',
    'ビビヨン', 'フラエッテ', 'フラージェス', 'ゴロンダ', 'ニャオニクス',
    'トリミアン', 'ギルガルド', 'フレフワン', 'ペロリーム', 'ブロスター',
    'エレザード', 'ガチゴラス', 'アマルルガ', 'ニンフィア', 'ルチャブル',
    'デデンネ', 'ヌメルゴン', 'ヌメルゴン(ヒスイ)', 'クレッフィ',
    'オーロット', 'パンプジン', 'クレベース', 'クレベース(ヒスイ)', 'オンバーン',
    # Gen7
    'ジュナイパー', 'ジュナイパー(ヒスイ)', 'ガオガエン', 'アシレーヌ',
    'ドデカバシ', 'ケケンカニ',
    # ルガルガン（3フォルム）
    'ルガルガン(まひるのすがた)', 'ルガルガン(まよなかのすがた)', 'ルガルガン(たそがれのすがた)',
    'ドヒドイデ', 'バンバドロ', 'オニシズクモ', 'エンニュート', 'アマージョ',
    'ヤレユータン', 'ナゲツケサル', 'ミミッキュ', 'ジジーロン', 'ジャラランガ',
    # Gen8
    'アーマーガア', 'アップリュー', 'タルップル', 'サダイジャ', 'ポットデス',
    'ブリムオン', 'バリコオル', 'デスバーン', 'マホイップ', 'モルペコ',
    'ドラパルト', 'アヤシシ', 'バサギリ',
    # イダイトウ（♂♀）
    'イダイトウ(オス)', 'イダイトウ(メス)',
    'オオニューラ',
    # Gen9
    'マスカーニャ', 'ラウドボーン', 'ウェーニバル', 'イッカネズミ', 'キョジオーン',
    'グレンアルマ', 'ソウブレイズ', 'ハラバリー', 'スコヴィラン', 'クエスパトラ',
    'デカヌチャン',
    # イルカマン（♂♀フォルム）
    'イルカマン(ナイーブフォルム)', 'イルカマン(マイティフォルム)',
    'ミミズズ', 'キラフロル', 'リキキリン', 'ドドゲザン', 'ヤバソチャ',
    'ブリジュラス', 'カミツオロチ',
]

# ===== 不足ポケモンを INSERT する追加データ =====
# MA-1 リストにあるが DB に存在しない Pokemon を手動定義
MISSING_POKEMON = [
    # ジジーロン = Drampa (Gen7, ドラゴン/ノーマル)
    {
        'name_jp': 'ジジーロン', 'name_en': 'drampa',
        'type1': 'Dragon', 'type2': 'Normal',
        'hp': 78, 'attack': 60, 'defense': 85, 'sp_attack': 135, 'sp_defense': 91, 'speed': 36,
        'ability1': 'sap-sipper', 'ability2': 'cloud-nine', 'hidden_ability': 'berserk',
        'is_available': 1,
    },
    # バリコオル = Arctovish (Gen8, みず/こおり)
    {
        'name_jp': 'バリコオル', 'name_en': 'arctovish',
        'type1': 'Water', 'type2': 'Ice',
        'hp': 90, 'attack': 90, 'defense': 100, 'sp_attack': 80, 'sp_defense': 90, 'speed': 55,
        'ability1': 'water-absorb', 'ability2': 'ice-body', 'hidden_ability': 'slush-rush',
        'is_available': 1,
    },
    # デスバーン = Runerigus (Gen8, じめん/ゴースト)
    {
        'name_jp': 'デスバーン', 'name_en': 'runerigus',
        'type1': 'Ground', 'type2': 'Ghost',
        'hp': 58, 'attack': 95, 'defense': 145, 'sp_attack': 50, 'sp_defense': 105, 'speed': 30,
        'ability1': 'wandering-spirit', 'ability2': None, 'hidden_ability': None,
        'is_available': 1,
    },
]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. regulation カラムを追加（存在しない場合のみ）
    cols = [row[1] for row in c.execute('PRAGMA table_info(pokemon)')]
    if 'regulation' not in cols:
        c.execute('ALTER TABLE pokemon ADD COLUMN regulation TEXT')
        print('[DB] regulation カラムを追加しました')
    else:
        print('[DB] regulation カラムは既に存在します')

    # 2. 不足ポケモンを INSERT
    inserted = 0
    for p in MISSING_POKEMON:
        c.execute('SELECT id FROM pokemon WHERE name_en=?', (p['name_en'],))
        if c.fetchone():
            print(f'  SKIP (already exists): {p["name_jp"]}')
            continue
        c.execute('''
            INSERT INTO pokemon
              (name_jp, name_en, type1, type2,
               hp, attack, defense, sp_attack, sp_defense, speed,
               ability1, ability2, hidden_ability, is_available)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            p['name_jp'], p['name_en'], p['type1'], p['type2'],
            p['hp'], p['attack'], p['defense'],
            p['sp_attack'], p['sp_defense'], p['speed'],
            p['ability1'], p['ability2'], p['hidden_ability'],
            p['is_available'],
        ))
        print(f'  INSERT: {p["name_jp"]}')
        inserted += 1

    # 3. 全ポケモンを is_available=0, regulation=NULL にリセット
    c.execute('UPDATE pokemon SET is_available=0, regulation=NULL')
    print('[DB] 全ポケモンを is_available=0 にリセット')

    # 4. MA-1 リストを適用
    found, not_found = [], []
    for name_jp in MA1_JP:
        c.execute('SELECT id FROM pokemon WHERE name_jp=?', (name_jp,))
        row = c.fetchone()
        if row:
            c.execute(
                "UPDATE pokemon SET is_available=1, regulation='champions-ma-1' WHERE name_jp=?",
                (name_jp,)
            )
            found.append(name_jp)
        else:
            not_found.append(name_jp)

    conn.commit()
    conn.close()

    print(f'\n[結果]')
    print(f'  新規 INSERT: {inserted}件')
    print(f'  MA-1 タグ付け: {len(found)}件')
    if not_found:
        print(f'  DB に未登録 (スキップ): {len(not_found)}件')
        for n in not_found:
            print(f'    - {n}')
    print('\n完了。data/_gen_jsdata.py を実行して jsdata を再生成してください。')


if __name__ == '__main__':
    main()

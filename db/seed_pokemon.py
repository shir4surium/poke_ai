"""
Champions AI - Gen7以降のポケモンを race_value.csv から DB に追加するシードスクリプト
既にDBに存在するポケモンはスキップ（INSERT OR IGNORE）する。
英語名・特性は PokeAPI から取得し data/pokeapi_cache/ にキャッシュする。
"""
import sys, os, csv, json, sqlite3, time, urllib.request, urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR  = Path(__file__).parent.parent
DB_PATH   = BASE_DIR / 'db' / 'champions.db'
CSV_PATH  = BASE_DIR / 'data' / 'race_value.csv'
CACHE_DIR = BASE_DIR / 'data' / 'pokeapi_cache'
CACHE_DIR.mkdir(exist_ok=True)

# 日本語タイプ → 英語
TYPE_JP = {
    'ノーマル':'Normal','ほのお':'Fire','みず':'Water','くさ':'Grass',
    'でんき':'Electric','こおり':'Ice','かくとう':'Fighting','どく':'Poison',
    'じめん':'Ground','ひこう':'Flying','エスパー':'Psychic','むし':'Bug',
    'いわ':'Rock','ゴースト':'Ghost','ドラゴン':'Dragon','あく':'Dark',
    'はがね':'Steel','フェアリー':'Fairy',
}

# 日本語名 → PokeAPI スラッグ（name_en として DB に保存）
JP_TO_EN = {
    # アローラのすがた
    'ライチュウ(アローラ)':'raichu-alola',
    'サンド(アローラ)':'sandshrew-alola',
    'サンドパン(アローラ)':'sandslash-alola',
    'ロコン(アローラ)':'vulpix-alola',
    'キュウコン(アローラ)':'ninetales-alola',
    'ディグダ(アローラ)':'diglett-alola',
    'ダグトリオ(アローラ)':'dugtrio-alola',
    'ニャース(アローラ)':'meowth-alola',
    'ペルシアン(アローラ)':'persian-alola',
    'イシツブテ(アローラ)':'geodude-alola',
    'ゴローン(アローラ)':'graveler-alola',
    'ゴローニャ(アローラ)':'golem-alola',
    'ベトベター(アローラ)':'grimer-alola',
    'ベトベトン(アローラ)':'muk-alola',
    'ナッシー(アローラ)':'exeggutor-alola',
    # ガラルのすがた
    'ニャース(ガラル)':'meowth-galar',
    'ヤドン(ガラル)':'slowpoke-galar',
    'ヤドラン(ガラル)':'slowbro-galar',
    'ヤドキング(ガラル)':'slowking-galar',
    'マタドガス(ガラル)':'weezing-galar',
    'フリーザー(ガラル)':'articuno-galar',
    'サンダー(ガラル)':'zapdos-galar',
    'ファイヤー(ガラル)':'moltres-galar',
    # ヒスイのすがた
    'ガーディ(ヒスイ)':'growlithe-hisui',
    'ウインディ(ヒスイ)':'arcanine-hisui',
    'ビリリダマ(ヒスイ)':'voltorb-hisui',
    'マルマイン(ヒスイ)':'electrode-hisui',
    'バクフーン(ヒスイ)':'typhlosion-hisui',
    'ハリーセン(ヒスイ)':'qwilfish-hisui',
    'ニューラ(ヒスイ)':'sneasel-hisui',
    'ダイケンキ(ヒスイ)':'samurott-hisui',
    'ドレディア(ヒスイ)':'lilligant-hisui',
    'ゾロア(ヒスイ)':'zorua-hisui',
    'ゾロアーク(ヒスイ)':'zoroark-hisui',
    'ウォーグル(ヒスイ)':'braviary-hisui',
    'ヌメイル(ヒスイ)':'sliggoo-hisui',
    'ヌメルゴン(ヒスイ)':'goodra-hisui',
    'クレベース(ヒスイ)':'avalugg-hisui',
    'ジュナイパー(ヒスイ)':'decidueye-hisui',
    'バサギリ':'kleavor',
    'ガチグマ':'ursaluna',
    '暁ガチグマ':'ursaluna-bloodmoon',
    'イダイトウ(オス)':'basculegion-male',
    'イダイトウ(メス)':'basculegion-female',
    'オオニューラ':'sneasler',
    'ハリーマン':'overqwil',
    'アヤシシ':'wyrdeer',
    # パルデアのすがた
    'ウパー(パルデア)':'wooper-paldea',
    'ケンタロス(パルデア単)':'tauros-paldea-combat',
    'ケンタロス(パルデア炎)':'tauros-paldea-blaze',
    'ケンタロス(パルデア水)':'tauros-paldea-aqua',
    # Gen1 missed
    'メタモン':'ditto',
    # Gen2 missed
    'キレイハナ':'bellossom',
    'ポリゴン2':'porygon2',
    'オドシシ':'stantler',
    'バルキー':'tyrogue',
    'エレキッド':'elekid',
    'ブビィ':'magby',
    # Gen3 missed
    'チリーン':'chimecho',
    'リーシャン':'chingling',
    # Gen4 missed/forms
    'メタグロス':'metagross',
    'ポリゴンZ':'porygon-z',
    'ヒードラン':'heatran',
    'レジギガス':'regigigas',
    'ヒートロトム':'rotom-heat',
    'ウォッシュロトム':'rotom-wash',
    'フロストロトム':'rotom-frost',
    'スピンロトム':'rotom-fan',
    'カットロトム':'rotom-mow',
    'ギラティナ(アナザーフォルム)':'giratina-altered',
    'ギラティナ(オリジンフォルム)':'giratina-origin',
    'シェイミ(ランドフォルム)':'shaymin-land',
    'シェイミ(スカイフォルム)':'shaymin-sky',
    'ディアルガ(オリジンフォルム)':'dialga-origin',
    'パルキア(オリジンフォルム)':'palkia-origin',
    # Gen5 forms
    'トルネロス(けしんフォルム)':'tornadus-incarnate',
    'トルネロス(れいじゅうフォルム)':'tornadus-therian',
    'ボルトロス(けしんフォルム)':'thundurus-incarnate',
    'ボルトロス(れいじゅうフォルム)':'thundurus-therian',
    'ランドロス(けしんフォルム)':'landorus-incarnate',
    'ランドロス(れいじゅうフォルム)':'landorus-therian',
    'ラブトロス(けしんフォルム)':'enamorus-incarnate',
    'ラブトロス(れいじゅうフォルム)':'enamorus-therian',
    'ホワイトキュレム':'kyurem-white',
    'ブラックキュレム':'kyurem-black',
    'ケルディオ(いつものすがた)':'keldeo-ordinary',
    'ケルディオ(かくごのすがた)':'keldeo-resolute',
    'メロエッタ(ボイスフォルム)':'meloetta-aria',
    'メロエッタ(ステップフォルム)':'meloetta-pirouette',
    # Gen6
    'ハリマロン':'chespin',
    'ハリボーグ':'quilladin',
    'ブリガロン':'chesnaught',
    'いましめられしフーパ':'hoopa-confined',
    'ときはなたれしフーパ':'hoopa-unbound',
    'デオキシス(ノーマルフォルム)':'deoxys-normal',
    'デオキシス(アタックフォルム)':'deoxys-attack',
    'デオキシス(ディフェンスフォルム)':'deoxys-defense',
    'デオキシス(スピードフォルム)':'deoxys-speed',
    # Gen7 new Pokemon
    'モクロー':'rowlet',
    'フクスロー':'dartrix',
    'ジュナイパー':'decidueye',
    'ニャビー':'litten',
    'ニャヒート':'torracat',
    'ガオガエン':'incineroar',
    'アシマリ':'popplio',
    'オシャマリ':'brionne',
    'アシレーヌ':'primarina',
    'ツツケラ':'pikipek',
    'ケララッパ':'trumbeak',
    'ドデカバシ':'toucannon',
    'ヤングース':'yungoos',
    'デカグース':'gumshoos',
    'アゴジムシ':'grubbin',
    'デンヂムシ':'charjabug',
    'クワガノン':'vikavolt',
    'マケンカニ':'crabrawler',
    'オドリドリ(めらめらスタイル)':'oricorio-baile',
    'オドリドリ(ぱちぱちスタイル)':'oricorio-pom-pom',
    'オドリドリ(ふらふらスタイル)':'oricorio-pau',
    'オドリドリ(まいまいスタイル)':'oricorio-sensu',
    'アブリー':'cutiefly',
    'アブリボン':'ribombee',
    'イワンコ':'rockruff',
    'ルガルガン(まひるのすがた)':'lycanroc-midday',
    'ルガルガン(まよなかのすがた)':'lycanroc-midnight',
    'ルガルガン(たそがれのすがた)':'lycanroc-dusk',
    'ヒドイデ':'mareanie',
    'ドヒドイデ':'toxapex',
    'ドロバンコ':'mudbray',
    'バンバドロ':'mudsdale',
    'シズクモ':'dewpider',
    'オニシズクモ':'araquanid',
    'カリキリ':'fomantis',
    'ラランテス':'lurantis',
    'ヤトウモリ':'salandit',
    'エンニュート':'salazzle',
    'アマカジ':'bounsweet',
    'アママイコ':'steenee',
    'アマージョ':'tsareena',
    'キュワワー':'comfey',
    'ヤレユータン':'oranguru',
    'ナゲツケサル':'passimian',
    'スナバァ':'sandygast',
    'シロデスナ':'palossand',
    'メテノ(りゅうせい)':'minior-red-meteor',
    'メテノ(コア)':'minior-red',
    'ネッコアラ':'komala',
    'ミミッキュ':'mimikyu-disguised',
    'ハギギシリ':'bruxish',
    'ジャラコ':'jangmo-o',
    'ジャランゴ':'hakamo-o',
    'ジャラランガ':'kommo-o',
    'コスモッグ':'cosmog',
    'コスモウム':'cosmoem',
    'ソルガレオ':'solgaleo',
    'ルナアーラ':'lunala',
    'ネクロズマ':'necrozma',
    '日食ネクロズマ':'necrozma-dusk-mane',
    '月食ネクロズマ':'necrozma-dawn-wings',
    'マギアナ':'magearna',
    # Gen8 new Pokemon
    'サルノリ':'grookey',
    'バチンキー':'thwackey',
    'ゴリランダー':'rillaboom',
    'ヒバニー':'scorbunny',
    'ラビフット':'raboot',
    'エースバーン':'cinderace',
    'メッソン':'sobble',
    'ジメレオン':'drizzile',
    'インテレオン':'inteleon',
    'ホシガリス':'skwovet',
    'ヨクバリス':'greedent',
    'ココガラ':'rookidee',
    'アオガラス':'corvisquire',
    'アーマーガア':'corviknight',
    'カムカメ':'chewtle',
    'カジリガメ':'drednaw',
    'タンドン':'rolycoly',
    'トロッゴン':'carkol',
    'セキタンザン':'coalossal',
    'カジッチュ':'applin',
    'アップリュー':'flapple',
    'タルップル':'appletun',
    'スナヘビ':'silicobra',
    'サダイジャ':'sandaconda',
    'ウッウ':'cramorant',
    'サシカマス':'arrokuda',
    'カマスジョー':'barraskewda',
    'エレズン':'toxel',
    'ストリンダー':'toxtricity-amped',
    'ヤバチャ':'sinistea-phony',
    'ポットデス':'polteageist-phony',
    'ミブリム':'hatenna',
    'テブリム':'hattrem',
    'ブリムオン':'hatterene',
    'ベロバー':'impidimp',
    'ギモー':'morgrem',
    'オーロンゲ':'grimmsnarl',
    'ニャイキング':'perrserker',
    'マホミル':'milcery',
    'マホイップ':'alcremie',
    'タイレーツ':'falinks',
    'バチンウニ':'pincurchin',
    'ユキハミ':'snom',
    'モスノウ':'frosmoth',
    'イシヘンジン':'stonjourner',
    'コオリッポ(アイスフェイス)':'eiscue-ice',
    'コオリッポ(ナイスフェイス)':'eiscue-noice',
    'イエッサン(オス)':'indeedee-male',
    'イエッサン(メス)':'indeedee-female',
    'モルペコ':'morpeko-full-belly',
    'ゾウドウ':'clobbopus',
    'ダイオウドウ':'grapploct',
    'ジュラルドン':'duraludon',
    'ドラメシヤ':'dreepy',
    'ドロンチ':'drakloak',
    'ドラパルト':'dragapult',
    'ザシアン(れきせんのゆうしゃ)':'zacian-hero-of-many-battles',
    'ザシアン(けんのおう)':'zacian-crowned',
    'ザマゼン(れきせんのゆうしゃ)':'zamazenta-hero-of-many-battles',
    'ザマゼンタ(たてのおう)':'zamazenta-crowned',
    'ムゲンダイナ':'eternatus',
    'ダクマ':'kubfu',
    'ウーラオス(いちげきのかた)':'urshifu-single-strike',
    'ウーラオス(れんげきのかた)':'urshifu-rapid-strike',
    'ザルード':'zarude',
    'レジエレキ':'regieleki',
    'レジドラゴ':'regidrago',
    'ブリザポス':'glastrier',
    'レイスポス':'spectrier',
    'バドレックス':'calyrex',
    'バドレックス(はくばじょうのすがた)':'calyrex-ice',
    'バドレックス(こくばじょうのすがた)':'calyrex-shadow',
    # Gen9 new Pokemon
    'ニャオハ':'sprigatito',
    'ニャローテ':'floragato',
    'マスカーニャ':'meowscarada',
    'ホゲータ':'fuecoco',
    'アチゲータ':'crocalor',
    'ラウドボーン':'skeledirge',
    'クワッス':'quaxly',
    'ウェルカモ':'quaxwell',
    'ウェーニバル':'quaquaval',
    'グルトン':'lechonk',
    'パフュートン\n(オス)':'oinkologne-male',
    'パフュートン\n(メス)':'oinkologne-female',
    'タマンチュラ':'tarountula',
    'ワナイダー':'spidops',
    'マメバッタ':'nymble',
    'エクスレッグ':'lokix',
    'パモ':'pawmi',
    'パモット':'pawmo',
    'パーモット':'pawmot',
    'ワッカネズミ':'tandemaus',
    'イッカネズミ':'maushold',
    'パピモッチ':'fidough',
    'バウッツェル':'dachsbun',
    'ミニーブ':'smoliv',
    'オリーニョ':'dolliv',
    'オリーヴァ':'arboliva',
    'イキリンコ':'squawkabilly-green-plumage',
    'コジオ':'nacli',
    'ジオヅム':'naclstack',
    'キョジオーン':'garganacl',
    'カルボウ':'charcadet',
    'グレンアルマ':'armarouge',
    'ソウブレイズ':'ceruledge',
    'ズピカ':'tadbulb',
    'ハラバリー':'bellibolt',
    'カイデン':'wattrel',
    'タイカイデン':'kilowattrel',
    'オラチフ':'maschiff',
    'マフィティフ':'mabosse',
    'シルシュルー':'shroodle',
    'タギングル':'grafaiai',
    'アノクサ':'bramblin',
    'アノホラグサ':'brambleghast',
    'ノノクラゲ':'toedscool',
    'リククラゲ':'toedscruel',
    'ガケガニ':'klawf',
    'カプサイジ':'capsakid',
    'スコヴィラン':'scovillain',
    'シガロコ':'rellor',
    'ベラカス':'rabsca',
    'ヒラヒナ':'flittle',
    'クエスパトラ':'espathra',
    'カヌチャン':'tinkatink',
    'ナカヌチャン':'tinkatuff',
    'デカヌチャン':'tinkaton',
    'ウミディグダ':'wiglett',
    'ウミトリオ':'wugtrio',
    'オトシドリ':'bombirdier',
    'ナミイルカ':'finizen',
    'イルカマン(ナイーブフォルム)':'palafin-zero',
    'イルカマン(マイティフォルム)':'palafin',
    'ブロロン':'varoom',
    'ブロロローム':'revavroom',
    'モトトカゲ':'cyclizar',
    'ミミズズ':'orthworm',
    'キラーメ':'glimmet',
    'キラフロル':'glimmora',
    'ボチ':'greavard',
    'ハカドッグ':'houndstone',
    'カラミンゴ':'flamigo',
    'アルクジラ':'cetoddle',
    'ハルクジラ':'cetitan',
    'ミガルーサ':'veluza',
    'ヘイラッシャ':'dondozo',
    'シャリタツ':'tatsugiri',
    'コノヨザル':'annihilape',
    'ドオー':'clodsire',
    'リキキリン':'farigiraf',
    'ドドゲザン':'kingambit',
    'イダイナキバ':'great-tusk',
    'サケブシッポ':'scream-tail',
    'アラブルタケ':'brute-bonnet',
    'ハバタクカミ':'flutter-mane',
    'チヲハウハネ':'slither-wing',
    'スナノケガワ':'sandy-shocks',
    'テツノワダチ':'iron-treads',
    'テツノツツミ':'iron-bundle',
    'テツノカイナ':'iron-hands',
    'テツノコウベ':'iron-jugulis',
    'テツノドクガ':'iron-moth',
    'テツノイバラ':'iron-thorns',
    'セビエ':'frigibax',
    'セゴール':'arctibax',
    'セグレイブ':'baxcalibur',
    'コレクレー':'gimmighoul',
    'サーフゴー':'gholdengo',
    'チオンジェン':'wo-chien',
    'パオジアン':'chien-pao',
    'ディンルー':'ting-lu',
    'イーユイ':'chi-yu',
    'トドロクツキ':'roaring-moon',
    'テツノブジン':'iron-valiant',
    'コライドン':'koraidon',
    'ミライドン':'miraidon',
    'ウネルミナモ':'walking-wake',
    'テツノイサハ':'iron-leaves',
    'カミッチュ':'dipplin',
    'チャデス':'poltchageist',
    'ヤバソチャ':'sinistcha',
    'イイネイヌ':'okidogi',
    'マシマシラ':'munkidori',
    'キチキギス':'fezandipiti',
    'オーガポン(みどりのめん)':'ogerpon-teal-mask',
    'オーガポン(いどのめん)':'ogerpon-wellspring-mask',
    'オーガポン(かまどのめん)':'ogerpon-hearthflame-mask',
    'オーガポン(いしずえのめん)':'ogerpon-cornerstone-mask',
    'ブリジュラス':'archaludon',
    'カミツオロチ':'hydrapple',
    'ウガツホムラ':'gouging-fire',
    'タケルライコ':'raging-bolt',
    'テツノイワオ':'iron-boulder',
    'テツノカシラ':'iron-crown',
    'テラパゴス':'terapagos',
    'テラパゴス(テラスタルフォルム)':'terapagos-terastal',
    'テラパゴス(ステラフォルム)':'terapagos-stellar',
    'モモワロウ':'pecharunt',
    # Kapu
    'カプ・コケコ':'tapu-koko',
    'カプ・テテフ':'tapu-lele',
    'カプ・ブルル':'tapu-bulu',
    'カプ・レヒレ':'tapu-fini',
}

POKEAPI_BASE = 'https://pokeapi.co/api/v2'


def fetch_json(url: str) -> dict | None:
    """URL から JSON を取得。失敗時は None を返す。"""
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f'  [WARN] fetch failed: {url} → {e}')
        return None


def get_pokemon_api_data(name_en: str) -> dict | None:
    """PokeAPI から ability・type を取得（キャッシュ優先）。"""
    cache_file = CACHE_DIR / f'poke_{name_en}.json'
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding='utf-8'))
    time.sleep(0.3)   # レート制限回避
    data = fetch_json(f'{POKEAPI_BASE}/pokemon/{name_en}')
    if data:
        cache_file.write_text(json.dumps(data), encoding='utf-8')
    return data


def parse_abilities(api_data: dict) -> tuple[str | None, str | None, str | None]:
    """API データから (ability1, ability2, hidden) を取得。"""
    ab = {a['slot']: a['ability']['name'] for a in api_data.get('abilities', [])}
    return ab.get(1), ab.get(2), ab.get(3)


def read_race_csv() -> dict[str, dict]:
    """race_value.csv から SV内定=SV のポケモンを読み込む。"""
    rows = {}
    with open(CSV_PATH, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row.get('SV内定', '') != 'SV':
                continue
            name = row['名前'].strip()
            if not name:
                continue
            rows[name] = row
    return rows


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    cur = conn.cursor()

    # 既存の日本語名を取得
    cur.execute('SELECT name_jp FROM pokemon')
    existing = {r[0] for r in cur.fetchall()}

    csv_data = read_race_csv()
    added = 0
    skipped = 0
    errors = []

    for name_jp, row in csv_data.items():
        # メガ・キョダイ・ゲンシ等はスキップ（ポケモンテーブルではなくmega_evolutionテーブル）
        if any(name_jp.startswith(p) for p in ('メガ', 'ゲンシ', 'キョダイ')):
            continue
        if name_jp in existing:
            skipped += 1
            continue

        name_en = JP_TO_EN.get(name_jp)
        if not name_en:
            print(f'  [SKIP] 英語名マッピングなし: {name_jp}')
            errors.append(name_jp)
            continue

        # 種族値
        try:
            hp  = int(row['H']); atk = int(row['A']); defense = int(row['B'])
            spa = int(row['C']); spd = int(row['D']); spe = int(row['S'])
        except Exception:
            print(f'  [SKIP] 種族値パースエラー: {name_jp}')
            errors.append(name_jp)
            continue

        # タイプ（列名が '' の場合は第2タイプ）
        type1_jp = row.get('タイプ', '').strip()
        type2_jp = row.get('', '').strip()
        type1 = TYPE_JP.get(type1_jp, type1_jp or 'Normal')
        type2 = TYPE_JP.get(type2_jp, type2_jp) if type2_jp else None

        # 特性（PokeAPI）
        ab1 = ab2 = ab_h = None
        api_data = get_pokemon_api_data(name_en)
        if api_data:
            ab1, ab2, ab_h = parse_abilities(api_data)
        else:
            print(f'  [WARN] API取得失敗 ({name_en}), 特性なしで登録')

        try:
            cur.execute(
                '''INSERT OR IGNORE INTO pokemon
                   (name_jp, name_en, type1, type2, hp, attack, defense,
                    sp_attack, sp_defense, speed,
                    ability1, ability2, hidden_ability, is_available)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1)''',
                (name_jp, name_en, type1, type2, hp, atk, defense,
                 spa, spd, spe, ab1, ab2, ab_h)
            )
            conn.commit()
            print(f'  [ADD] {name_jp} ({name_en})')
            added += 1
        except sqlite3.IntegrityError as e:
            print(f'  [ERR] {name_jp}: {e}')
            errors.append(name_jp)

    conn.close()
    print(f'\n完了: 追加={added}, スキップ={skipped}, エラー={len(errors)}')
    if errors:
        print('エラーのあったポケモン:', errors)


if __name__ == '__main__':
    main()

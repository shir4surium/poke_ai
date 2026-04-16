"""
行動意味分類器 (ActionClassifier)

技・交代をスロット番号ではなく対戦文脈に基づく12カテゴリに分類する。

技カテゴリ (0〜9):
  0  PHYSICAL_STAB       物理・自タイプ一致 (STAB)
  1  PHYSICAL_COVERAGE   物理・相手に有効 (>1x)
  2  PHYSICAL_NEUTRAL    物理・相手に等倍以下
  3  SPECIAL_STAB        特殊・自タイプ一致 (STAB)
  4  SPECIAL_COVERAGE    特殊・相手に有効 (>1x)
  5  SPECIAL_NEUTRAL     特殊・相手に等倍以下
  6  STATUS_BUFF         変化技・自強化 (能力↑ / 回復 / 壁)
  7  STATUS_DEBUFF       変化技・相手弱体 (状態異常 / 能力↓ / 撒き菱)
  8  PRIORITY_MOVE       先制技 (priority ≥ 1)
  9  MEGA_MOVE           メガシンカ技

交代カテゴリ (10〜11):
  10 SWITCH_TYPE_ADV     相手技を半減以下で受ける控えへ交代
  11 SWITCH_SAFE         等倍受け / HP保全 / ピボット的交代
"""

from __future__ import annotations
import sys
import json
import time
import logging
from enum import IntEnum
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "db"))
sys.path.insert(0, str(ROOT / "data_pipeline"))

logger = logging.getLogger(__name__)

DATA_DIR  = ROOT / "data"
CACHE_DIR = ROOT / "data" / "pokeapi_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

REQUEST_INTERVAL = 0.3  # PokeAPI レート制限

# ── タイプ名変換 ────────────────────────────────────────────────────────────
# list_wepon.csv / race_value.csv は日本語タイプ名
# Champions DB / PokeAPI は英語大文字先頭 ("Fire", "Dragon" など)
JP_TO_EN_TYPE: dict[str, str] = {
    "ノーマル": "Normal",   "ほのお":   "Fire",     "みず":     "Water",
    "でんき":  "Electric",  "くさ":     "Grass",     "こおり":   "Ice",
    "かくとう": "Fighting", "どく":     "Poison",    "じめん":   "Ground",
    "ひこう":  "Flying",    "エスパー": "Psychic",   "むし":     "Bug",
    "いわ":    "Rock",      "ゴースト": "Ghost",     "ドラゴン": "Dragon",
    "あく":    "Dark",      "はがね":   "Steel",     "フェアリー": "Fairy",
}

# list_wepon.csv の分類列
JP_CATEGORY_MAP: dict[str, str] = {
    "物理": "physical", "特殊": "special", "変化": "status",
}

# 変化技のbuff判定キーワード (JP)
# 効果テキストパターン: "ランクを〇段階上げる" "ランクが〇段階上がる" "〇段階ずつ上げる/上がる"
_JP_BUFF_KEYWORDS: list[str] = [
    "段階上がる",      # N段階上がる (こうそくいどう 等)
    "段階上げる",      # N段階上げる (つるぎのまい 等)
    "ずつ上がる",      # N段階ずつ上がる (めいそう 等)
    "ずつ上げる",      # N段階ずつ上げる (りゅうのまい 等)
    "回復する",        # HP回復 (じこさいせい 等)
    "HPを回復",        # HP回復(別表現)
    "半分回復",        # HP回復(別表現)
    "ひかりのかべ",    # Light Screen
    "リフレクター",    # Reflect
    "オーロラベール",  # Aurora Veil
    "バトンタッチ",    # Baton Pass
    "フィールド",      # 各種テレイン
    "トリックルーム",  # Trick Room
    "テールウインド",  # Tailwind
    "天気を",          # 天気変化技 (あまごい, にほんばれ 等)
    "すなあらし",      # Sandstorm (天気を含まない別表記対策)
    "その番に受ける",  # Protect 系
]


# ===== カテゴリ定義 =====

class ActionCategory(IntEnum):
    PHYSICAL_STAB     = 0
    PHYSICAL_COVERAGE = 1
    PHYSICAL_NEUTRAL  = 2
    SPECIAL_STAB      = 3
    SPECIAL_COVERAGE  = 4
    SPECIAL_NEUTRAL   = 5
    STATUS_BUFF       = 6
    STATUS_DEBUFF     = 7
    PRIORITY_MOVE     = 8
    MEGA_MOVE         = 9
    SWITCH_TYPE_ADV   = 10
    SWITCH_SAFE       = 11

NUM_ACTION_CATEGORIES = len(ActionCategory)  # 12

# カテゴリラベル (ログ表示用)
CATEGORY_LABELS = {
    ActionCategory.PHYSICAL_STAB:     "物理STAB",
    ActionCategory.PHYSICAL_COVERAGE: "物理有効",
    ActionCategory.PHYSICAL_NEUTRAL:  "物理等倍以下",
    ActionCategory.SPECIAL_STAB:      "特殊STAB",
    ActionCategory.SPECIAL_COVERAGE:  "特殊有効",
    ActionCategory.SPECIAL_NEUTRAL:   "特殊等倍以下",
    ActionCategory.STATUS_BUFF:       "変化・自強化",
    ActionCategory.STATUS_DEBUFF:     "変化・相手弱体",
    ActionCategory.PRIORITY_MOVE:     "先制技",
    ActionCategory.MEGA_MOVE:         "メガシンカ",
    ActionCategory.SWITCH_TYPE_ADV:   "タイプ有利交代",
    ActionCategory.SWITCH_SAFE:       "安全交代",
}

# ===== 変化技の効果分類キーワード =====
# PokeAPI の effect_entries[short_effect] を用いる

_BUFF_KEYWORDS = [
    "raises the user", "user's", "sharply raises", "boosts", "restores",
    "heals", "recover", "reflects", "light screen", "aurora veil",
    "weather", "terrain", "trick room", "protects", "substitute",
    "rapid spin", "magic coat", "baton pass",
]
_DEBUFF_KEYWORDS = [
    "lowers the target", "poisons", "badly poisons", "burns", "paralyzes",
    "puts the target to sleep", "freezes", "confuses", "infatuates",
    "entry hazard", "spikes", "stealth rock", "toxic spikes", "sticky web",
    "taunt", "encore", "flinch", "leech", "badly damages",
]

# ===== よく使われる技の手動マッピング (PokeAPI なしでも動作) =====
# (category, priority, is_buff):
#   category: "physical" / "special" / "status"
#   priority: int
#   effect_type: "buff" / "debuff" / None (攻撃技はNone)
_KNOWN_MOVES: dict[str, tuple[str, int, str | None]] = {
    # --- ステータス技・自強化 ---
    "Swords Dance":      ("status", 0, "buff"),
    "Dragon Dance":      ("status", 0, "buff"),
    "Calm Mind":         ("status", 0, "buff"),
    "Nasty Plot":        ("status", 0, "buff"),
    "Quiver Dance":      ("status", 0, "buff"),
    "Shell Smash":       ("status", 0, "buff"),
    "Bulk Up":           ("status", 0, "buff"),
    "Coil":              ("status", 0, "buff"),
    "Work Up":           ("status", 0, "buff"),
    "Agility":           ("status", 0, "buff"),
    "Rock Polish":       ("status", 0, "buff"),
    "Roost":             ("status", 0, "buff"),
    "Recover":           ("status", 0, "buff"),
    "Slack Off":         ("status", 0, "buff"),
    "Soft-Boiled":       ("status", 0, "buff"),
    "Moonlight":         ("status", 0, "buff"),
    "Morning Sun":       ("status", 0, "buff"),
    "Synthesis":         ("status", 0, "buff"),
    "Wish":              ("status", 0, "buff"),
    "Substitute":        ("status", 0, "buff"),
    "Protect":           ("status", 4, "buff"),
    "Detect":            ("status", 4, "buff"),
    "Reflect":           ("status", 0, "buff"),
    "Light Screen":      ("status", 0, "buff"),
    "Aurora Veil":       ("status", 0, "buff"),
    "Tailwind":          ("status", 0, "buff"),
    "Rain Dance":        ("status", 0, "buff"),
    "Sunny Day":         ("status", 0, "buff"),
    "Sandstorm":         ("status", 0, "buff"),
    "Hail":              ("status", 0, "buff"),
    "Trick Room":        ("status", 0, "buff"),
    "Electric Terrain":  ("status", 0, "buff"),
    "Grassy Terrain":    ("status", 0, "buff"),
    "Psychic Terrain":   ("status", 0, "buff"),
    "Misty Terrain":     ("status", 0, "buff"),
    "Baton Pass":        ("status", 0, "buff"),
    "Defog":             ("status", 0, "buff"),
    "Rapid Spin":        ("status", 0, "buff"),
    "Magic Coat":        ("status", 0, "buff"),
    # --- ステータス技・相手弱体 ---
    "Toxic":             ("status", 0, "debuff"),
    "Will-O-Wisp":       ("status", 0, "debuff"),
    "Thunder Wave":      ("status", 0, "debuff"),
    "Glare":             ("status", 0, "debuff"),
    "Sleep Powder":      ("status", 0, "debuff"),
    "Spore":             ("status", 0, "debuff"),
    "Hypnosis":          ("status", 0, "debuff"),
    "Stealth Rock":      ("status", 0, "debuff"),
    "Spikes":            ("status", 0, "debuff"),
    "Toxic Spikes":      ("status", 0, "debuff"),
    "Sticky Web":        ("status", 0, "debuff"),
    "Taunt":             ("status", 0, "debuff"),
    "Encore":            ("status", 0, "debuff"),
    "Leech Seed":        ("status", 0, "debuff"),
    "Knock Off":         ("physical", 0, None),  # 実際は道具を落とす副効果
    "Trick":             ("status", 0, "debuff"),
    "Switcheroo":        ("status", 0, "debuff"),
    "Parting Shot":      ("status", -1, "debuff"),
    "Memento":           ("status", 0, "debuff"),
    "Haze":              ("status", 0, "debuff"),
    "Clear Smog":        ("special", 0, None),
    # --- 先制技 ---
    "Quick Attack":      ("physical", 1, None),
    "Bullet Punch":      ("physical", 1, None),
    "Ice Shard":         ("physical", 1, None),
    "Shadow Sneak":      ("physical", 1, None),
    "Mach Punch":        ("physical", 1, None),
    "Aqua Jet":          ("physical", 1, None),
    "Vacuum Wave":       ("special", 1, None),
    "Water Shuriken":    ("special", 1, None),
    "Fake Out":          ("physical", 3, None),
    "Extreme Speed":     ("physical", 2, None),
    "First Impression":  ("physical", 2, None),
    "Prankster":         ("status", 1, "buff"),
    # --- ピボット技 (physical) ---
    "U-turn":            ("physical", 0, None),
    "Flip Turn":         ("physical", 0, None),
    "Volt Switch":       ("special", 0, None),
    "Teleport":          ("status", -6, "buff"),
}


# ===== ActionClassifier =====

class ActionClassifier:
    """
    技名・ポケモン名から ActionCategory を返す。

    DBからタイプ情報を取得し、PokeAPI から技データを取得（キャッシュ付き）。
    """

    def __init__(self):
        self._move_cache: dict[str, dict] = {}   # slug → {category, priority, effect_type, type}
        self._poke_cache: dict[str, dict] = {}   # name_en → {type1, type2}
        self._type_chart: dict[tuple[str, str], float] | None = None
        # CSV から読み込む日本語名ルックアップ
        self._jp_poke_types: dict[str, tuple[str | None, str | None]] = {}
        self._jp_move_data:  dict[str, dict] = {}
        self._load_csv_data()

    # ── タイプ相性 ──────────────────────────────────────────────

    def _get_type_chart(self) -> dict[tuple[str, str], float]:
        if self._type_chart is None:
            from schema import get_connection
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT attacking_type, defending_type, multiplier FROM type_chart")
            self._type_chart = {(r[0], r[1]): r[2] for r in c.fetchall()}
            conn.close()
        return self._type_chart

    def _type_eff(self, atk_type: str, def_type1: str | None, def_type2: str | None) -> float:
        """攻撃タイプ → 防御タイプ(1,2) の有効倍率"""
        if not atk_type or not def_type1:
            return 1.0
        chart = self._get_type_chart()
        eff = chart.get((atk_type, def_type1), 1.0)
        if def_type2:
            eff *= chart.get((atk_type, def_type2), 1.0)
        return eff

    def _is_stab(self, move_type: str, type1: str | None, type2: str | None) -> bool:
        return bool(move_type and (move_type == type1 or move_type == type2))

    # ── CSV 読み込み ──────────────────────────────────────────────

    def _load_csv_data(self) -> None:
        """race_value.csv と list_wepon.csv をメモリに読み込む"""
        import csv, re
        priority_re = re.compile(r'優先度:\+(\d+)')

        race_path = DATA_DIR / "race_value.csv"
        if race_path.exists():
            with open(race_path, encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    t1_en = JP_TO_EN_TYPE.get(row.get("タイプ", ""))
                    t2_jp = row.get("", "")  # タイプ2 (列ヘッダが空文字)
                    t2_en = JP_TO_EN_TYPE.get(t2_jp) if t2_jp else None
                    self._jp_poke_types[row["名前"]] = (t1_en, t2_en)

        wepon_path = DATA_DIR / "list_wepon.csv"
        if wepon_path.exists():
            with open(wepon_path, encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    name   = row["名前"]
                    cat    = JP_CATEGORY_MAP.get(row.get("分類", ""), "status")
                    mt_en  = JP_TO_EN_TYPE.get(row.get("タイプ", ""))
                    effect = row.get("効果", "")

                    m    = priority_re.search(effect)
                    pri  = int(m.group(1)) if m else 0

                    eff_type: str | None = None
                    if cat == "status":
                        eff_type = "buff" if any(kw in effect for kw in _JP_BUFF_KEYWORDS) else "debuff"

                    self._jp_move_data[name] = {
                        "category":   cat,
                        "move_type":  mt_en,
                        "priority":   pri,
                        "effect_type": eff_type,
                    }

    # ── ポケモンタイプ取得 ────────────────────────────────────────

    def _poke_types(self, name_en: str) -> tuple[str | None, str | None]:
        """英語名からタイプ(type1, type2)を返す（DB → PokeAPI fallback）"""
        if name_en in self._poke_cache:
            d = self._poke_cache[name_en]
            return d["type1"], d["type2"]

        from schema import get_connection
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT type1, type2 FROM pokemon WHERE name_en = ?", (name_en,))
        row = c.fetchone()
        if row is None:
            c.execute("SELECT type1, type2 FROM mega_evolution WHERE mega_name_en = ?", (name_en,))
            row = c.fetchone()
        conn.close()

        if row:
            self._poke_cache[name_en] = {"type1": row["type1"], "type2": row["type2"]}
            return row["type1"], row["type2"]

        # Champions DB に未収録 → PokeAPI から取得
        type1, type2 = self._fetch_poke_types_api(name_en)
        self._poke_cache[name_en] = {"type1": type1, "type2": type2}
        if type1:
            logger.debug(f"PokeAPI で取得: {name_en} → {type1}/{type2}")
        else:
            logger.debug(f"タイプ不明: {name_en}")
        return type1, type2

    def _fetch_poke_types_api(self, name_en: str) -> tuple[str | None, str | None]:
        """PokeAPI からポケモンタイプを取得（キャッシュ付き）"""
        import urllib.request
        slug = name_en.lower().replace(" ", "-").replace("'", "").replace(".", "")
        cache_path = CACHE_DIR / f"poke_{slug}.json"

        if cache_path.exists():
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            url = f"https://pokeapi.co/api/v2/pokemon/{slug}/"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "champions-ai-project/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw = json.loads(resp.read().decode())
                time.sleep(REQUEST_INTERVAL)
                cache_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                logger.debug(f"PokeAPI pokemon fetch failed ({name_en}): {e}")
                time.sleep(REQUEST_INTERVAL)
                return None, None

        types_sorted = sorted(raw.get("types", []), key=lambda t: t.get("slot", 99))
        type1 = types_sorted[0]["type"]["name"].capitalize() if len(types_sorted) > 0 else None
        type2 = types_sorted[1]["type"]["name"].capitalize() if len(types_sorted) > 1 else None
        return type1, type2

    def _poke_types_jp(self, name_jp: str) -> tuple[str | None, str | None]:
        """日本語名からタイプ(type1, type2)を返す（CSV データ使用）"""
        return self._jp_poke_types.get(name_jp, (None, None))

    # ── 技データ取得 ──────────────────────────────────────────────

    @staticmethod
    def _to_slug(move_name: str) -> str:
        """Showdown 技名 → PokeAPI スラッグ変換"""
        return move_name.lower().replace(" ", "-").replace("'", "")

    def _load_move(self, move_name_en: str) -> dict:
        """
        技データを返す。
        優先度: 手動マッピング > キャッシュ > PokeAPI
        """
        if move_name_en in self._move_cache:
            return self._move_cache[move_name_en]

        # 手動マッピング
        if move_name_en in _KNOWN_MOVES:
            cat, pri, eff_type = _KNOWN_MOVES[move_name_en]
            result = {
                "category": cat,
                "priority": pri,
                "effect_type": eff_type,
                "move_type": None,  # タイプは別途 PokeAPI で補完
            }
            self._move_cache[move_name_en] = result
            return result

        # PokeAPI キャッシュファイル
        slug = self._to_slug(move_name_en)
        cache_path = CACHE_DIR / f"move_{slug}.json"

        if cache_path.exists():
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            raw = self._fetch_move_api(slug)
            if raw:
                cache_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

        result = self._parse_move_raw(raw) if raw else {
            "category": "status", "priority": 0, "effect_type": "debuff", "move_type": None
        }
        self._move_cache[move_name_en] = result
        return result

    def _fetch_move_api(self, slug: str) -> dict | None:
        """PokeAPI から技データを取得"""
        import urllib.request
        url = f"https://pokeapi.co/api/v2/move/{slug}/"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "champions-ai-project/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                time.sleep(REQUEST_INTERVAL)
                return json.loads(resp.read().decode())
        except Exception:
            time.sleep(REQUEST_INTERVAL)
            return None

    @staticmethod
    def _parse_move_raw(raw: dict) -> dict:
        """PokeAPI レスポンスから必要フィールドを抽出"""
        category = raw.get("damage_class", {}).get("name", "status")   # physical/special/status
        priority = raw.get("priority", 0)
        move_type = raw.get("type", {}).get("name", "").capitalize()   # "Fire" 形式

        # 効果テキストで buff/debuff を判定
        effect_entries = raw.get("effect_entries", [])
        effect_text = ""
        for e in effect_entries:
            if e.get("language", {}).get("name") == "en":
                effect_text = (e.get("short_effect") or e.get("effect") or "").lower()
                break

        effect_type: str | None = None
        if category == "status":
            if any(kw in effect_text for kw in _BUFF_KEYWORDS):
                effect_type = "buff"
            else:
                effect_type = "debuff"

        return {
            "category":    category,
            "priority":    priority,
            "effect_type": effect_type,
            "move_type":   move_type,
        }

    def _load_move_jp(self, move_name_jp: str) -> dict:
        """日本語技名から技データを返す（CSV 優先）"""
        if move_name_jp in self._jp_move_data:
            return self._jp_move_data[move_name_jp]
        return {"category": "status", "priority": 0, "effect_type": "debuff", "move_type": None}

    # ── 分類メイン ────────────────────────────────────────────────

    def classify_move(
        self,
        move_name_en: str,
        user_name_en: str,
        opponent_name_en: str,
        is_mega: bool = False,
    ) -> int:
        """
        技行動を ActionCategory に分類する。

        Args:
            move_name_en:     使用技名（英語）
            user_name_en:     使用ポケモン英語名
            opponent_name_en: 相手ポケモン英語名
            is_mega:          メガシンカを伴うか
        """
        if is_mega:
            return int(ActionCategory.MEGA_MOVE)

        move = self._load_move(move_name_en)
        priority = move.get("priority", 0)

        if priority >= 1:
            return int(ActionCategory.PRIORITY_MOVE)

        category = move.get("category", "status")
        move_type = move.get("move_type") or ""

        if category == "status":
            eff_type = move.get("effect_type", "debuff")
            if eff_type == "buff":
                return int(ActionCategory.STATUS_BUFF)
            return int(ActionCategory.STATUS_DEBUFF)

        # 物理 / 特殊の分岐
        u_type1, u_type2 = self._poke_types(user_name_en)
        o_type1, o_type2 = self._poke_types(opponent_name_en)

        is_stab = self._is_stab(move_type, u_type1, u_type2)
        effectiveness = self._type_eff(move_type, o_type1, o_type2)

        if category == "physical":
            if is_stab:
                return int(ActionCategory.PHYSICAL_STAB)
            if effectiveness > 1.0:
                return int(ActionCategory.PHYSICAL_COVERAGE)
            return int(ActionCategory.PHYSICAL_NEUTRAL)
        else:  # special
            if is_stab:
                return int(ActionCategory.SPECIAL_STAB)
            if effectiveness > 1.0:
                return int(ActionCategory.SPECIAL_COVERAGE)
            return int(ActionCategory.SPECIAL_NEUTRAL)

    def classify_switch(
        self,
        current_name_en: str,
        incoming_name_en: str,
        opponent_name_en: str,
    ) -> int:
        """
        交代行動を ActionCategory に分類する。

        交代先が相手の主タイプ技を半減以下で受けられるか = タイプ有利交代。
        それ以外 = 安全交代（HP温存・ピボット等）。
        """
        inc_type1, inc_type2 = self._poke_types(incoming_name_en)
        opp_type1, opp_type2 = self._poke_types(opponent_name_en)

        # 相手の type1 で交代先を攻撃したとき 0.5x 以下 → タイプ有利交代
        if opp_type1 and inc_type1:
            eff = self._type_eff(opp_type1, inc_type1, inc_type2)
            if eff <= 0.5:
                return int(ActionCategory.SWITCH_TYPE_ADV)

        return int(ActionCategory.SWITCH_SAFE)

    def classify_move_jp(
        self,
        move_name_jp: str,
        user_name_jp: str,
        opponent_name_jp: str,
        is_mega: bool = False,
    ) -> int:
        """
        技行動を ActionCategory に分類する（日本語名版）。

        Champions ゲーム連携用: 技名・ポケモン名がすべて日本語の場合に使用。
        CSV データ (list_wepon.csv / race_value.csv) を参照する。

        Args:
            move_name_jp:     使用技名（日本語）
            user_name_jp:     使用ポケモン日本語名
            opponent_name_jp: 相手ポケモン日本語名
            is_mega:          メガシンカを伴うか
        """
        if is_mega:
            return int(ActionCategory.MEGA_MOVE)

        move     = self._load_move_jp(move_name_jp)
        priority = move.get("priority", 0)

        if priority >= 1:
            return int(ActionCategory.PRIORITY_MOVE)

        category  = move.get("category", "status")
        move_type = move.get("move_type") or ""

        if category == "status":
            eff_type = move.get("effect_type", "debuff")
            return int(ActionCategory.STATUS_BUFF if eff_type == "buff" else ActionCategory.STATUS_DEBUFF)

        u_type1, u_type2 = self._poke_types_jp(user_name_jp)
        o_type1, o_type2 = self._poke_types_jp(opponent_name_jp)

        is_stab       = self._is_stab(move_type, u_type1, u_type2)
        effectiveness = self._type_eff(move_type, o_type1, o_type2)

        if category == "physical":
            if is_stab:             return int(ActionCategory.PHYSICAL_STAB)
            if effectiveness > 1.0: return int(ActionCategory.PHYSICAL_COVERAGE)
            return int(ActionCategory.PHYSICAL_NEUTRAL)
        else:  # special
            if is_stab:             return int(ActionCategory.SPECIAL_STAB)
            if effectiveness > 1.0: return int(ActionCategory.SPECIAL_COVERAGE)
            return int(ActionCategory.SPECIAL_NEUTRAL)

    def classify_switch_jp(
        self,
        current_name_jp: str,
        incoming_name_jp: str,
        opponent_name_jp: str,
    ) -> int:
        """交代行動を分類する（日本語名版）"""
        inc_type1, inc_type2 = self._poke_types_jp(incoming_name_jp)
        opp_type1, _         = self._poke_types_jp(opponent_name_jp)

        if opp_type1 and inc_type1:
            eff = self._type_eff(opp_type1, inc_type1, inc_type2)
            if eff <= 0.5:
                return int(ActionCategory.SWITCH_TYPE_ADV)
        return int(ActionCategory.SWITCH_SAFE)


# ===== 事前フェッチ =====

def prefetch_moves(move_names: list[str], classifier: ActionClassifier | None = None) -> None:
    """
    使用される技名を先にまとめて PokeAPI から取得する。
    training 前に一度だけ呼ぶことで学習中の通信待ちをなくす。
    """
    if classifier is None:
        classifier = ActionClassifier()
    total = len(move_names)
    fetched = 0
    for i, name in enumerate(move_names, 1):
        slug = ActionClassifier._to_slug(name)
        cache_path = CACHE_DIR / f"move_{slug}.json"
        if cache_path.exists() or name in _KNOWN_MOVES:
            continue
        logger.info(f"  [{i}/{total}] 技フェッチ: {name}")
        raw = classifier._fetch_move_api(slug)
        if raw:
            cache_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            fetched += 1
    logger.info(f"技フェッチ完了: {fetched} 件")


def prefetch_pokemon(poke_names: list[str], classifier: ActionClassifier | None = None) -> None:
    """
    使用されるポケモン名を先にまとめて Champions DB / PokeAPI から取得する。
    Champions DB 未収録のポケモン (gen8ou 等) のタイプを事前キャッシュし、
    training 中の通信待ちをなくす。
    """
    if classifier is None:
        classifier = ActionClassifier()

    # Champions DB にないポケモンのみフェッチ
    from schema import get_connection
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT name_en FROM pokemon")
    db_names = {r[0] for r in c.fetchall()}
    c.execute("SELECT mega_name_en FROM mega_evolution")
    db_names |= {r[0] for r in c.fetchall()}
    conn.close()

    need = [n for n in poke_names if n and n not in db_names and n not in classifier._poke_cache]
    # PokeAPI キャッシュ済みを除外
    def _slug(n: str) -> str:
        return n.lower().replace(" ", "-").replace("'", "")
    need = [n for n in need if not (CACHE_DIR / f"poke_{_slug(n)}.json").exists()]

    if not need:
        logger.info("ポケモンフェッチ: 全件キャッシュ済み")
        return

    logger.info(f"ポケモンタイプをフェッチ中 ({len(need)} 件)...")
    fetched = 0
    for i, name in enumerate(need, 1):
        type1, type2 = classifier._fetch_poke_types_api(name)
        if type1:
            fetched += 1
            logger.debug(f"  [{i}/{len(need)}] {name} → {type1}/{type2}")
    logger.info(f"ポケモンフェッチ完了: {fetched} 件")


# ===== 動作確認 =====

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    clf = ActionClassifier()

    test_cases = [
        # (move, user, opponent, is_mega, expected_label)
        ("Earthquake",   "garchomp",    "corviknight",  False, "物理STAB"),
        ("Moonblast",    "togekiss",    "garchomp",     False, "特殊STAB"),    # togekiss=Fairy, Moonblast=Fairy → STAB
        ("Scald",        "slowbro",     "ferrothorn",   False, "特殊STAB"),    # slowbro=Water, Scald=Water → STAB
        ("Toxic",        "ferrothorn",  "landorus",     False, "変化・相手弱体"),
        ("Swords Dance", "garchomp",    "corviknight",  False, "変化・自強化"),
        ("Quick Attack", "lopunny",     "garchomp",     False, "先制技"),
        ("Earthquake",   "lopunny",     "heatran",      True,  "メガシンカ"),
        ("Knock Off",    "ferrothorn",  "slowbro",      False, "物理等倍以下"),
    ]

    print(f"{'技':<20} {'使用者':<15} {'相手':<15} → カテゴリ")
    print("-" * 70)
    for move, user, opp, mega, expected in test_cases:
        cat = clf.classify_move(move, user, opp, is_mega=mega)
        label = CATEGORY_LABELS[cat]
        mark = "OK" if label == expected else "NG"
        print(f"{move:<20} {user:<15} {opp:<15} -> [{cat:2d}] {label} {mark}")

    # 交代テスト
    print("\n交代分類:")
    switch_cases = [
        ("garchomp",   "heatran",     "corviknight", "タイプ有利交代"),
        ("ferrothorn", "excadrill",   "toxapex",     "タイプ有利交代"),  # excadrill=Ground/Steel, toxapex type1=Poison, Poison vs Steel=0.5x → 有利
    ]
    for cur, inc, opp, expected in switch_cases:
        cat = clf.classify_switch(cur, inc, opp)
        label = CATEGORY_LABELS[cat]
        mark = "OK" if label == expected else "NG"
        print(f"  {cur} -> {inc} (vs {opp}): [{cat}] {label} {mark}")

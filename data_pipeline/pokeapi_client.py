"""
PokeAPI クライアント

User-Agentヘッダーを付与して接続する。
レート制限対策として1リクエストごとにウェイトを入れる。
"""

import json
import time
import logging
import urllib.request
import urllib.error
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_URL = "https://pokeapi.co/api/v2"
HEADERS = {"User-Agent": "champions-ai-project/1.0"}
CACHE_DIR = Path(__file__).parent.parent / "data" / "pokeapi_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
REQUEST_INTERVAL = 0.5  # 秒


def _cache_path(endpoint: str) -> Path:
    safe = endpoint.replace("/", "_").strip("_")
    return CACHE_DIR / f"{safe}.json"


def fetch(endpoint: str, use_cache: bool = True) -> dict | None:
    """
    PokeAPI からデータを取得する（キャッシュ付き）

    Args:
        endpoint: APIエンドポイント (例: "pokemon/bulbasaur", "move/tackle")
        use_cache: Trueの場合ローカルキャッシュを優先
    Returns:
        レスポンスのdict、失敗時はNone
    """
    cache_file = _cache_path(endpoint)

    if use_cache and cache_file.exists():
        with open(cache_file, encoding="utf-8") as f:
            return json.load(f)

    url = f"{BASE_URL}/{endpoint}"
    req = urllib.request.Request(url, headers=HEADERS)

    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        time.sleep(REQUEST_INTERVAL)
        return data
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP {e.code}: {url}")
        return None
    except Exception as e:
        logger.error(f"取得失敗 {url}: {e}")
        return None


def fetch_pokemon(name_or_id: str | int) -> dict | None:
    return fetch(f"pokemon/{name_or_id}")


def fetch_move(name_or_id: str | int) -> dict | None:
    return fetch(f"move/{name_or_id}")


def fetch_item(name_or_id: str | int) -> dict | None:
    return fetch(f"item/{name_or_id}")

"""
Pokémon Showdown リプレイ収集スクリプト

対象フォーマット: gen8ou, gen8ubers (メガシンカあり環境 = チャンピオンズに最も近い)
API仕様: https://replay.pokemonshowdown.com/search.json
"""

import json
import time
import logging
from pathlib import Path
from dataclasses import dataclass

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

REPLAY_DIR = Path(__file__).parent.parent / "data" / "replays"
REPLAY_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://replay.pokemonshowdown.com"
SEARCH_URL = f"{BASE_URL}/search.json"

# チャンピオンズに近い環境 (メガシンカが使えるGen8フォーマット)
# gen8ubers: レーティングなし試合が多いため除外
# gen8randombattle: パーティが固定でないため除外
TARGET_FORMATS = [
    "gen8ou",
    "gen8nationaldexag",  # メガシンカ + 伝説あり環境 (補助)
]

# レート制限: Showdownの負荷を抑えるため
REQUEST_INTERVAL = 1.0  # 秒


@dataclass
class ReplayMeta:
    replay_id: str
    format_id: str
    players: list[str]
    rating: int | None
    upload_time: int


def fetch_replay_list(
    format_id: str,
    page: int = 1,
    rating_min: int = 1500,
) -> list[ReplayMeta]:
    """
    Showdown APIからリプレイ一覧を取得する

    Args:
        format_id: フォーマット名 (例: "gen8ou")
        page: ページ番号 (1始まり)
        rating_min: 最低レート (品質フィルタ)
    Returns:
        ReplayMetaのリスト
    """
    params = {
        "format": format_id,
        "page": page,
    }
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error(f"リプレイ一覧取得失敗 format={format_id} page={page}: {e}")
        return []

    results = []
    for item in data:
        rating = item.get("rating")
        # レートフィルタ (0 または None はフリー対戦のため除外)
        if not rating or rating < rating_min:
            continue
        # players フィールドはリスト形式 ["p1name", "p2name"]
        players_raw = item.get("players", [])
        if isinstance(players_raw, list):
            players = players_raw[:2]
        else:
            players = [item.get("p1", ""), item.get("p2", "")]
        results.append(ReplayMeta(
            replay_id=item["id"],
            format_id=format_id,
            players=players,
            rating=rating,
            upload_time=item.get("uploadtime", 0),
        ))
    return results


def fetch_replay_log(replay_id: str) -> str | None:
    """
    個別リプレイのログテキストを取得する

    Args:
        replay_id: リプレイID (例: "gen8ou-1234567890")
    Returns:
        ログテキスト (失敗時はNone)
    """
    url = f"{BASE_URL}/{replay_id}.log"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logger.error(f"リプレイログ取得失敗 id={replay_id}: {e}")
        return None


def save_replay(meta: ReplayMeta, log_text: str):
    """リプレイをJSONLファイルに保存する (フォーマット別に分ける)"""
    out_path = REPLAY_DIR / f"{meta.format_id}.jsonl"
    record = {
        "id": meta.replay_id,
        "format": meta.format_id,
        "players": meta.players,
        "rating": meta.rating,
        "upload_time": meta.upload_time,
        "log": log_text,
    }
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def is_already_collected(replay_id: str, format_id: str) -> bool:
    """重複収集を避けるため、既収集IDをチェックする"""
    out_path = REPLAY_DIR / f"{format_id}.jsonl"
    if not out_path.exists():
        return False
    with open(out_path, encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                if record["id"] == replay_id:
                    return True
            except json.JSONDecodeError:
                continue
    return False


def collect(
    formats: list[str] = TARGET_FORMATS,
    pages_per_format: int = 10,
    rating_min: int = 1000,
):
    """
    メイン収集処理

    Args:
        formats: 収集対象フォーマットのリスト
        pages_per_format: フォーマットごとに取得するページ数
        rating_min: 最低レート
    """
    total_saved = 0

    for fmt in formats:
        logger.info(f"=== フォーマット: {fmt} 収集開始 ===")
        saved_count = 0

        for page in range(1, pages_per_format + 1):
            logger.info(f"  ページ {page}/{pages_per_format} 取得中...")
            metas = fetch_replay_list(fmt, page=page, rating_min=rating_min)

            if not metas:
                logger.info(f"  ページ {page}: データなし、終了")
                break

            for meta in metas:
                if is_already_collected(meta.replay_id, fmt):
                    logger.debug(f"  スキップ (既収集): {meta.replay_id}")
                    continue

                log_text = fetch_replay_log(meta.replay_id)
                time.sleep(REQUEST_INTERVAL)

                if log_text is None:
                    continue

                save_replay(meta, log_text)
                saved_count += 1
                logger.info(
                    f"  保存: {meta.replay_id} "
                    f"(rating={meta.rating}, players={meta.players})"
                )

            time.sleep(REQUEST_INTERVAL)

        logger.info(f"=== {fmt}: {saved_count} 件保存 ===")
        total_saved += saved_count

    logger.info(f"収集完了: 合計 {total_saved} 件")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Showdownリプレイ収集スクリプト")
    parser.add_argument("--formats", nargs="+", default=TARGET_FORMATS,
                        help="収集対象フォーマット (例: gen8ou gen8ubers)")
    parser.add_argument("--pages", type=int, default=10,
                        help="フォーマットごとのページ数")
    parser.add_argument("--rating-min", type=int, default=1000,
                        help="最低レートフィルタ")
    args = parser.parse_args()

    collect(
        formats=args.formats,
        pages_per_format=args.pages,
        rating_min=args.rating_min,
    )

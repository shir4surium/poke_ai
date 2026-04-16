"""
Phase 1 実行スクリプト

手順:
  1. リプレイ収集 (scraper.py)
  2. ログパース (parser.py)
  3. DB初期化 (db/schema.py + seed_type_chart.py)
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# db/ を import パスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "db"))

from scraper import collect, TARGET_FORMATS
from parser import run_all
from schema import init_db
from seed_type_chart import seed_type_chart


def main():
    # Step 1: DB初期化
    print("\n=== Step 1: DB初期化 ===")
    init_db()
    seed_type_chart()

    # Step 2: リプレイ収集
    print("\n=== Step 2: Showdownリプレイ収集 ===")
    print("対象フォーマット:", TARGET_FORMATS)
    collect(
        formats=TARGET_FORMATS,
        pages_per_format=5,   # まずは5ページ (約50試合/フォーマット)
        rating_min=1500,
    )

    # Step 3: ログパース
    print("\n=== Step 3: ログパース ===")
    run_all()

    print("\n=== Phase 1 完了 ===")
    print("次のステップ: data/parsed/ にパース済みデータが生成されています")


if __name__ == "__main__":
    main()

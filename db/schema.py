"""
チャンピオンズ対戦AI - データベーススキーマ定義
SQLiteを使用してポケモン・技・アイテム・タイプ相性のマスタデータを管理する
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "champions.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # ポケモンマスタ
    c.execute("""
        CREATE TABLE IF NOT EXISTS pokemon (
            id          INTEGER PRIMARY KEY,
            name_jp     TEXT NOT NULL,
            name_en     TEXT NOT NULL UNIQUE,
            type1       TEXT NOT NULL,
            type2       TEXT,
            hp          INTEGER NOT NULL,
            attack      INTEGER NOT NULL,
            defense     INTEGER NOT NULL,
            sp_attack   INTEGER NOT NULL,
            sp_defense  INTEGER NOT NULL,
            speed       INTEGER NOT NULL,
            ability1    TEXT,
            ability2    TEXT,
            hidden_ability TEXT,
            is_available INTEGER NOT NULL DEFAULT 1  -- チャンピオンズで使用可能か
        )
    """)

    # メガシンカマスタ
    c.execute("""
        CREATE TABLE IF NOT EXISTS mega_evolution (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            base_pokemon_en TEXT NOT NULL REFERENCES pokemon(name_en),
            mega_name_jp    TEXT NOT NULL,
            mega_name_en    TEXT NOT NULL UNIQUE,
            mega_stone      TEXT NOT NULL,
            type1           TEXT NOT NULL,
            type2           TEXT,
            hp              INTEGER NOT NULL,
            attack          INTEGER NOT NULL,
            defense         INTEGER NOT NULL,
            sp_attack       INTEGER NOT NULL,
            sp_defense      INTEGER NOT NULL,
            speed           INTEGER NOT NULL,
            ability         TEXT NOT NULL
        )
    """)

    # 技マスタ
    c.execute("""
        CREATE TABLE IF NOT EXISTS move (
            id          INTEGER PRIMARY KEY,
            name_jp     TEXT NOT NULL,
            name_en     TEXT NOT NULL UNIQUE,
            type        TEXT NOT NULL,
            category    TEXT NOT NULL CHECK(category IN ('Physical', 'Special', 'Status')),
            power       INTEGER,           -- 変化技はNULL
            accuracy    INTEGER,           -- 必中はNULL
            pp          INTEGER NOT NULL,
            priority    INTEGER NOT NULL DEFAULT 0,
            effect      TEXT,              -- 追加効果の説明
            effect_chance INTEGER          -- 追加効果の発動確率(%)
        )
    """)

    # ポケモンが覚える技の対応テーブル
    c.execute("""
        CREATE TABLE IF NOT EXISTS pokemon_learnset (
            pokemon_en  TEXT NOT NULL REFERENCES pokemon(name_en),
            move_en     TEXT NOT NULL REFERENCES move(name_en),
            PRIMARY KEY (pokemon_en, move_en)
        )
    """)

    # アイテムマスタ
    c.execute("""
        CREATE TABLE IF NOT EXISTS item (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name_jp     TEXT NOT NULL,
            name_en     TEXT NOT NULL UNIQUE,
            category    TEXT NOT NULL,  -- 'Berry', 'MegaStone', 'Choice', 'General' など
            description TEXT
        )
    """)

    # タイプ相性テーブル (攻撃タイプ × 防御タイプ = 倍率)
    c.execute("""
        CREATE TABLE IF NOT EXISTS type_chart (
            attacking_type  TEXT NOT NULL,
            defending_type  TEXT NOT NULL,
            multiplier      REAL NOT NULL,  -- 0, 0.5, 1, 2
            PRIMARY KEY (attacking_type, defending_type)
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] スキーマ初期化完了: {DB_PATH}")


if __name__ == "__main__":
    init_db()

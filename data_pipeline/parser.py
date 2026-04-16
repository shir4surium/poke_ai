"""
Pokémon Showdown リプレイログ パーサー

入力: Showdownの .log テキスト
出力: ターン毎の行動・結果をJSON構造に変換する

Showdownログの主要コマンド:
  |player|p1|NAME         プレイヤー情報
  |poke|p1|Pokemon, L50  パーティ開示
  |switch|p1a|Pokemon|HP  交代
  |move|p1a|技名|対象      技使用
  |-damage|p1a|HP          ダメージ
  |-heal|p1a|HP            回復
  |-status|p1a|brn         状態異常付与
  |turn|N                  ターン開始
  |win|PLAYER              勝者
"""

import json
import re
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

PARSED_DIR = Path(__file__).parent.parent / "data" / "parsed"
PARSED_DIR.mkdir(parents=True, exist_ok=True)


# ---------- データクラス定義 ----------

@dataclass
class PokemonState:
    """1ターン時点でのポケモン状態"""
    name: str
    current_hp: int | None = None   # 現在HP (実数値)
    max_hp: int | None = None       # 最大HP
    hp_percent: float | None = None # HP割合 (0.0-1.0)
    status: str | None = None       # brn/par/slp/psn/tox/frz/None
    is_mega: bool = False
    fainted: bool = False


@dataclass
class Action:
    """1ターンの行動記録"""
    player: str          # "p1" or "p2"
    action_type: str     # "move" or "switch"
    move_name: str | None = None
    switch_to: str | None = None


@dataclass
class TurnRecord:
    """1ターンの完全な記録"""
    turn_number: int
    active: dict[str, str] = field(default_factory=dict)  # {"p1": "Pokemon名", "p2": "Pokemon名"}
    actions: list[Action] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)  # ダメージ・状態異常など
    hp_snapshot: dict[str, PokemonState] = field(default_factory=dict)  # ターン終了時HP


@dataclass
class BattleRecord:
    """1試合の完全な記録"""
    replay_id: str
    format_id: str
    players: dict[str, str] = field(default_factory=dict)  # {"p1": "NAME", "p2": "NAME"}
    party: dict[str, list[str]] = field(default_factory=dict)  # {"p1": [...], "p2": [...]}
    lead: dict[str, str] = field(default_factory=dict)  # {"p1": "先発ポケモン名", "p2": ...}
    turns: list[TurnRecord] = field(default_factory=list)
    winner: str | None = None  # "p1" or "p2"
    winner_name: str | None = None


# ---------- パーサー本体 ----------

class ShowdownLogParser:

    def parse(self, replay_id: str, format_id: str, log_text: str) -> BattleRecord:
        record = BattleRecord(replay_id=replay_id, format_id=format_id)
        current_turn: TurnRecord | None = None
        active: dict[str, str] = {}
        hp_tracker: dict[str, PokemonState] = {}

        for raw_line in log_text.splitlines():
            line = raw_line.strip()
            if not line or not line.startswith("|"):
                continue
            parts = line.split("|")
            if len(parts) < 2:
                continue
            cmd = parts[1]

            # --- プレイヤー情報 ---
            if cmd == "player" and len(parts) >= 4:
                slot = parts[2]   # "p1" or "p2"
                name = parts[3]
                record.players[slot] = name

            # --- パーティ開示 ---
            elif cmd == "poke" and len(parts) >= 4:
                slot = parts[2]
                pokemon_raw = parts[3].split(",")[0].strip()
                pokemon_name = self._normalize_pokemon_name(pokemon_raw)
                record.party.setdefault(slot, []).append(pokemon_name)

            # --- 先発・交代 ---
            elif cmd == "switch" or cmd == "drag":
                if len(parts) >= 5:
                    slot_raw = parts[2]   # "p1a" or "p2a"
                    slot = slot_raw[:2]   # "p1" or "p2"
                    pokemon_raw = parts[3].split(",")[0].strip()
                    pokemon_name = self._normalize_pokemon_name(pokemon_raw)
                    hp_str = parts[4] if len(parts) > 4 else None

                    active[slot] = pokemon_name
                    state = hp_tracker.setdefault(
                        f"{slot}:{pokemon_name}",
                        PokemonState(name=pokemon_name)
                    )
                    if hp_str:
                        self._update_hp(state, hp_str)

                    if current_turn is None:
                        # ターン0: 先発登場
                        record.lead[slot] = pokemon_name
                    else:
                        # ターン中の交代アクション
                        current_turn.actions.append(Action(
                            player=slot,
                            action_type="switch",
                            switch_to=pokemon_name,
                        ))
                        current_turn.active = dict(active)

            # --- 技使用 ---
            elif cmd == "move" and len(parts) >= 4:
                slot_raw = parts[2]
                slot = slot_raw[:2]
                move_name = parts[3]
                if current_turn is not None:
                    current_turn.actions.append(Action(
                        player=slot,
                        action_type="move",
                        move_name=move_name,
                    ))

            # --- ダメージ ---
            elif cmd == "-damage" and len(parts) >= 4:
                slot_raw = parts[2]
                slot = slot_raw[:2]
                hp_str = parts[3]
                pokemon_name = active.get(slot, "")
                key = f"{slot}:{pokemon_name}"
                state = hp_tracker.setdefault(key, PokemonState(name=pokemon_name))
                self._update_hp(state, hp_str)
                if current_turn is not None:
                    current_turn.events.append({
                        "type": "damage",
                        "target": slot,
                        "pokemon": pokemon_name,
                        "hp": hp_str,
                    })

            # --- 回復 ---
            elif cmd == "-heal" and len(parts) >= 4:
                slot_raw = parts[2]
                slot = slot_raw[:2]
                hp_str = parts[3]
                pokemon_name = active.get(slot, "")
                key = f"{slot}:{pokemon_name}"
                state = hp_tracker.setdefault(key, PokemonState(name=pokemon_name))
                self._update_hp(state, hp_str)
                if current_turn is not None:
                    current_turn.events.append({
                        "type": "heal",
                        "target": slot,
                        "pokemon": pokemon_name,
                        "hp": hp_str,
                    })

            # --- 状態異常付与 ---
            elif cmd == "-status" and len(parts) >= 4:
                slot_raw = parts[2]
                slot = slot_raw[:2]
                status = parts[3]
                pokemon_name = active.get(slot, "")
                key = f"{slot}:{pokemon_name}"
                state = hp_tracker.get(key)
                if state:
                    state.status = status
                if current_turn is not None:
                    current_turn.events.append({
                        "type": "status",
                        "target": slot,
                        "pokemon": pokemon_name,
                        "status": status,
                    })

            # --- 状態異常回復 ---
            elif cmd == "-curestatus" and len(parts) >= 4:
                slot_raw = parts[2]
                slot = slot_raw[:2]
                pokemon_name = active.get(slot, "")
                key = f"{slot}:{pokemon_name}"
                state = hp_tracker.get(key)
                if state:
                    state.status = None

            # --- メガシンカ ---
            elif cmd == "-mega" and len(parts) >= 4:
                slot_raw = parts[2]
                slot = slot_raw[:2]
                mega_name = parts[3] if len(parts) > 3 else ""
                active[slot] = mega_name
                key = f"{slot}:{mega_name}"
                state = hp_tracker.setdefault(key, PokemonState(name=mega_name))
                state.is_mega = True
                if current_turn is not None:
                    current_turn.active = dict(active)
                    current_turn.events.append({
                        "type": "mega",
                        "player": slot,
                        "pokemon": mega_name,
                    })

            # --- 瀕死 ---
            elif cmd == "faint" and len(parts) >= 3:
                slot_raw = parts[2]
                slot = slot_raw[:2]
                pokemon_name = active.get(slot, "")
                key = f"{slot}:{pokemon_name}"
                state = hp_tracker.get(key)
                if state:
                    state.fainted = True
                    state.current_hp = 0
                if current_turn is not None:
                    current_turn.events.append({
                        "type": "faint",
                        "player": slot,
                        "pokemon": pokemon_name,
                    })

            # --- ターン開始 ---
            elif cmd == "turn" and len(parts) >= 3:
                if current_turn is not None:
                    # ターン終了時のHPスナップショットを保存
                    current_turn.hp_snapshot = {
                        k: asdict(v) for k, v in hp_tracker.items()
                    }
                    record.turns.append(current_turn)

                turn_num = int(parts[2])
                current_turn = TurnRecord(
                    turn_number=turn_num,
                    active=dict(active),
                )

            # --- 勝者 ---
            elif cmd == "win" and len(parts) >= 3:
                winner_name = parts[2]
                record.winner_name = winner_name
                for slot, name in record.players.items():
                    if name == winner_name:
                        record.winner = slot
                        break

        # 最終ターンを追加
        if current_turn is not None:
            current_turn.hp_snapshot = {
                k: asdict(v) for k, v in hp_tracker.items()
            }
            record.turns.append(current_turn)

        return record

    def _normalize_pokemon_name(self, raw: str) -> str:
        """ポケモン名の正規化 (性別記号など除去)"""
        name = raw.strip()
        name = re.sub(r"-[MF]$", "", name)  # 性別形
        return name

    def _update_hp(self, state: PokemonState, hp_str: str):
        """
        HP文字列をパースして状態を更新する
        形式例: "287/350", "75/100", "0 fnt"
        """
        hp_str = hp_str.split()[0]  # "0 fnt" → "0"
        if "/" in hp_str:
            cur_str, max_str = hp_str.split("/")
            try:
                state.current_hp = int(cur_str)
                state.max_hp = int(max_str)
                state.hp_percent = state.current_hp / state.max_hp if state.max_hp > 0 else 0.0
            except ValueError:
                pass
        else:
            try:
                state.current_hp = int(hp_str)
                if state.max_hp:
                    state.hp_percent = state.current_hp / state.max_hp
            except ValueError:
                pass


# ---------- バッチ処理 ----------

def parse_replay_file(jsonl_path: Path) -> list[BattleRecord]:
    """JSONLファイルを読み込んでパース済みレコードのリストを返す"""
    parser = ShowdownLogParser()
    records = []

    with open(jsonl_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(f"JSONデコード失敗: 行 {i+1}")
                continue

            replay_id = raw.get("id", "")
            format_id = raw.get("format", "")
            log_text = raw.get("log", "")

            try:
                record = parser.parse(replay_id, format_id, log_text)
                records.append(record)
            except Exception as e:
                logger.error(f"パース失敗 id={replay_id}: {e}")

    return records


def save_parsed(records: list[BattleRecord], out_path: Path):
    """パース結果をJSONLで保存"""
    with open(out_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
    logger.info(f"パース結果保存: {out_path} ({len(records)} 件)")


def run_all():
    """data/replays/ 以下の全JSONLをパースしてdata/parsed/に保存"""
    replay_dir = Path(__file__).parent.parent / "data" / "replays"
    for jsonl_path in replay_dir.glob("*.jsonl"):
        logger.info(f"パース中: {jsonl_path.name}")
        records = parse_replay_file(jsonl_path)
        out_path = PARSED_DIR / jsonl_path.name
        save_parsed(records, out_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_all()

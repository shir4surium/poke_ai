"""
navigator/api.py
================
Champions AI 対戦ナビゲーター FastAPI エンドポイント。

起動:
    cd c:/Users/tbkPo/Desktop/p/champions_AI
    uvicorn navigator.api:app --reload --port 8000

エンドポイント一覧:
    POST /setup/party      — 自分のパーティ登録
    POST /setup/opponent   — 相手のパーティ登録 → 選出推薦返却
    POST /battle/start     — 選出確定・バトル開始
    POST /battle/turn      — ターン入力 → 行動推薦返却
    GET  /battle/state     — 現在の状態確認
    POST /battle/reset     — ナビゲーターリセット
    GET  /                 — ヘルスチェック
"""

from __future__ import annotations
import sys
import logging
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "db"))
sys.path.insert(0, str(ROOT / "ai"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from navigator.schemas import (
    SetupPartyRequest, SetupOpponentRequest, StartBattleRequest,
    TurnInput, TurnOutput, SelectionResultOut, StateResponse,
)
from navigator.battle_navigator import BattleNavigator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

MODELS_DIR = ROOT / "ai" / "models"

# ===== FastAPI アプリ =====

app = FastAPI(
    title       = "Champions AI Battle Navigator",
    description = "ポケモンチャンピオンズ対戦ナビゲーター API",
    version     = "1.0.0",
)

# CORS — 将来のフロントエンド・映像解析プログラムからの呼び出しを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# グローバルナビゲーターインスタンス
_navigator: Optional[BattleNavigator] = None


def get_navigator() -> BattleNavigator:
    """ナビゲーターインスタンスを取得（未初期化なら初期化）"""
    global _navigator
    if _navigator is None:
        raise HTTPException(status_code=503, detail="ナビゲーターが初期化されていません。サーバーを再起動してください。")
    return _navigator


# ===== 起動イベント =====

@app.on_event("startup")
async def startup_event() -> None:
    """サーバー起動時に ChampionsAgent を初期化する"""
    global _navigator
    logger.info("Champions AI ナビゲーター起動中...")

    agent = None
    try:
        from ai.agent import ChampionsAgent  # type: ignore

        # RL学習済み → 模倣学習済み → 未学習の順で読み込む
        ckpt_candidates = [
            MODELS_DIR / "rl_best.pt",
            MODELS_DIR / "policy_value_best.pt",
        ]
        ckpt = next((c for c in ckpt_candidates if c.exists()), None)

        if ckpt:
            logger.info(f"チェックポイント読み込み: {ckpt}")
            agent = ChampionsAgent.from_checkpoint(str(ckpt), num_sims=100)
            logger.info("ChampionsAgent 初期化完了")
        else:
            logger.warning("学習済みモデルが見つかりません。未学習モデルを使用します。")
            agent = ChampionsAgent.new(num_sims=50)

    except Exception as e:
        logger.error(f"ChampionsAgent 初期化失敗: {e}")
        logger.warning("MCTS なしでナビゲーターを起動します（フォールバック推薦を使用）")

    _navigator = BattleNavigator(agent=agent)
    logger.info("ナビゲーター起動完了")


# ===== エンドポイント =====

FRONTEND_DIR = ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

@app.get("/", tags=["システム"])
def health_check() -> dict:
    """ヘルスチェック"""
    nav = _navigator
    return {
        "status":  "ok",
        "message": "Champions AI Battle Navigator",
        "agent_loaded": nav is not None and nav.agent is not None,
        "battle_started": nav._battle_started if nav else False,
    }


@app.post("/setup/party", tags=["セットアップ"])
def setup_party(req: SetupPartyRequest) -> dict:
    """
    自分のパーティを登録する。

    バトル開始前に1回呼び出す。複数回呼ぶと上書きされる。

    Request body:
        {
            "my_party": [
                {
                    "name_jp": "ガブリアス",
                    "name_en": "garchomp",
                    "item": "こだわりスカーフ",
                    "ability": "さめはだ",
                    "gender": "♂",
                    "nature": "ようき",
                    "evs": {"H": 0, "A": 252, "B": 0, "C": 0, "D": 4, "S": 252},
                    "moves": ["じしん", "げきりん", "かみくだく", "つるぎのまい"]
                },
                ...
            ]
        }
    """
    nav = get_navigator()
    nav.setup_my_party(req.my_party)
    return {
        "status":  "ok",
        "message": f"{len(req.my_party)}体のパーティを登録しました",
        "party":   [p.name_jp for p in nav._my_party],
    }


@app.post("/setup/opponent", tags=["セットアップ"])
def setup_opponent(req: SetupOpponentRequest) -> SelectionResultOut:
    """
    相手のパーティを登録し、選出推薦を返す。

    Request body:
        {"opponent_party": ["カイリュー", "ドヒドイデ", "テッカグヤ", "ミミッキュ", "ウーラオス", "トゲキッス"]}

    Response:
        {"selected": [...], "lead": "...", "scores": {...}, "reasons": {...}}
    """
    nav = get_navigator()
    if not nav._my_party:
        raise HTTPException(status_code=400, detail="先に /setup/party を呼んでください")
    return nav.setup_opponent(req.opponent_party)


@app.post("/battle/start", tags=["バトル"])
def start_battle(req: StartBattleRequest) -> dict:
    """
    選出を確定してバトルを開始する。

    Request body:
        {
            "selected":  ["ガブリアス", "ミミッキュ", "テッカグヤ"],
            "lead_my":   "ガブリアス",
            "lead_opp":  "カイリュー"
        }
    """
    nav = get_navigator()
    if not nav._my_party:
        raise HTTPException(status_code=400, detail="先に /setup/party を呼んでください")
    if len(req.selected) != 3:
        raise HTTPException(status_code=400, detail="選出は3体指定してください")

    try:
        nav.start_battle(req.selected, req.lead_my, req.lead_opp)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"バトル開始エラー: {e}")

    return {
        "status":  "ok",
        "message": f"バトル開始: {req.lead_my} vs {req.lead_opp}",
        "selected": req.selected,
        "lead_my":  req.lead_my,
        "lead_opp": req.lead_opp,
    }


@app.post("/battle/turn", tags=["バトル"])
def process_turn(req: TurnInput) -> TurnOutput:
    """
    ターンの観測情報を入力し、次の行動推薦を返す。

    映像解析プログラムは各ターン終了後にこのエンドポイントを呼び出す。

    Request body（フィールドはすべてオプション、観測できたものだけ送る）:
        {
            "turn": 1,
            "ability_activations": [
                {"player": "p2", "ability": "いかく", "pokemon": "カイリュー"}
            ],
            "opponent_hp_pct": 72,
            "my_hp_after": 212,
            "opponent_action": {
                "move": "ダブルウイング",
                "my_hp_after": 212
            }
        }

    Response:
        {
            "recommendations": [
                {"action": "じしん", "confidence": 65.2, "category": "物理STAB", "reason": "..."},
                {"action": "げきりん", "confidence": 22.8, "category": "物理STAB", "reason": "..."},
                {"action": "交代: ミミッキュ", "confidence": 12.0, "category": "安全交代", "reason": "..."}
            ],
            "opponent_estimate": {
                "item": "こだわり系（推測）",
                "item_confidence": 0.6,
                "speed_tier": "素早さ実数値 1〜168",
                ...
            },
            "battle_state_summary": "ターン1 | 自:ガブリアス(212/301) vs 相手:カイリュー(残72%) | ..."
        }
    """
    nav = get_navigator()
    if not nav._battle_started:
        raise HTTPException(status_code=400, detail="先に /battle/start を呼んでください")

    try:
        return nav.process_turn(req)
    except Exception as e:
        logger.error(f"ターン処理エラー: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"ターン処理エラー: {e}")


@app.get("/battle/state", tags=["バトル"])
def get_state() -> StateResponse:
    """現在の対戦状態を返す"""
    nav  = get_navigator()
    info = nav.get_state_info()
    return StateResponse(
        turn           = info.get("turn", 0),
        my_active      = info.get("my_active"),
        opp_active     = info.get("opp_active"),
        my_hp          = info.get("my_hp"),
        opp_hp_pct     = info.get("opp_hp_pct"),
        my_selected    = info.get("my_selected", []),
        opp_revealed   = info.get("opp_revealed", []),
        battle_started = info.get("battle_started", False),
    )


@app.post("/battle/reset", tags=["バトル"])
def reset_battle() -> dict:
    """ナビゲーターをリセットして次のバトルに備える"""
    nav = get_navigator()
    nav.reset()
    return {"status": "ok", "message": "ナビゲーターをリセットしました"}


# ===== 直接実行 =====

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("navigator.api:app", host="0.0.0.0", port=8000, reload=True)

import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('c:/Users/tbkPo/Desktop/p/champions_AI/data/_tmp_jsdata.js', encoding='utf-8') as f:
    jsdata = f.read()

PART1 = '''<!DOCTYPE html>
<html lang="ja" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Champions AI 対戦ナビゲーター</title>
<style>
html[data-theme="dark"]{--bg:#0f1117;--bg2:#1a1d27;--bg3:#242838;--border:#2e3348;--accent:#4f8ef7;--green:#34c97a;--yellow:#f5a623;--red:#e85d75;--text:#e8eaf0;--text2:#8b90a7;--text3:#5a5f76;}
html[data-theme="light"]{--bg:#f4f6fb;--bg2:#ffffff;--bg3:#eef0f7;--border:#d0d4e8;--accent:#2563eb;--green:#16a34a;--yellow:#d97706;--red:#dc2626;--text:#1e2030;--text2:#4b5280;--text3:#9298b8;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:\'Hiragino Sans\',\'Meiryo\',sans-serif;font-size:14px;min-height:100vh;transition:background .2s,color .2s}
header{background:var(--bg2);border-bottom:1px solid var(--border);padding:10px 20px;display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:100}
header h1{font-size:15px;font-weight:700;color:var(--text);flex:1;letter-spacing:.5px}
header h1 span{color:var(--accent)}
.steps{display:flex}
.step{display:flex;align-items:center;gap:5px;padding:5px 12px;font-size:12px;color:var(--text3)}
.step::after{content:\'›\';margin-left:6px;color:var(--text3)}
.step:last-child::after{display:none}
.step.active{color:var(--accent);font-weight:700}
.step.done{color:var(--green)}
.step-num{width:18px;height:18px;border-radius:50%;border:1.5px solid currentColor;display:flex;align-items:center;justify-content:center;font-size:10px;flex-shrink:0}
.btn-theme{background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:5px 12px;font-size:12px;color:var(--text2);cursor:pointer;font-family:inherit;white-space:nowrap}
.btn-theme:hover{background:var(--border)}
#home-btn{background:none;border:1px solid var(--border);border-radius:6px;padding:5px 12px;font-size:12px;color:var(--text2);cursor:pointer;font-family:inherit;white-space:nowrap;display:none}
#home-btn:hover{background:var(--bg3);color:var(--text)}
main{max-width:1120px;margin:0 auto;padding:20px 16px}
.page{display:none}.page.active{display:block}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:18px 20px;margin-bottom:14px}
.card-title{font-size:14px;font-weight:700;margin-bottom:14px;color:var(--text);display:flex;align-items:center;gap:8px}
.badge{font-size:10px;font-weight:600;padding:2px 8px;border-radius:20px;background:var(--accent);color:#fff}
label{font-size:12px;color:var(--text2);display:block;margin-bottom:3px}
input[type=text],input[type=number],select{background:var(--bg3);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:6px 9px;font-size:13px;width:100%;transition:border-color .2s;font-family:inherit}
input:focus,select:focus{outline:none;border-color:var(--accent)}
input[type=number]{-moz-appearance:textfield}
input[type=number]::-webkit-inner-spin-button{display:none}
select option{background:var(--bg3);color:var(--text)}
input.invalid{border-color:var(--red)!important}
input.valid{border-color:var(--green)!important}
.grid{display:grid;gap:8px}.grid-2{grid-template-columns:1fr 1fr}.grid-3{grid-template-columns:1fr 1fr 1fr}.grid-6{grid-template-columns:repeat(6,1fr)}
.field{display:flex;flex-direction:column;gap:3px}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:9px 20px;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;transition:all .2s;font-family:inherit}
.btn-primary{background:var(--accent);color:#fff}.btn-primary:hover{filter:brightness(1.1);transform:translateY(-1px)}
.btn-secondary{background:var(--bg3);color:var(--text);border:1px solid var(--border)}.btn-secondary:hover{border-color:var(--accent);color:var(--accent)}
.btn-success{background:var(--green);color:#fff}.btn-success:hover{filter:brightness(1.1)}
.btn-sm{padding:5px 12px;font-size:12px}
.btn-row{display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap;margin-top:4px}
.poke-slot{background:var(--bg2);border:1px solid var(--border);border-radius:10px;overflow:hidden;margin-bottom:8px}
.poke-slot-header{display:flex;align-items:center;gap:10px;padding:10px 14px;cursor:pointer;user-select:none;transition:background .15s}
.poke-slot-header:hover{background:var(--bg3)}
.slot-num{width:22px;height:22px;background:var(--bg3);border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:var(--text2);flex-shrink:0}
.slot-summary{flex:1;font-size:12px;color:var(--text2)}.slot-summary strong{color:var(--text)}
.slot-expand{color:var(--text3);transition:transform .2s}
.poke-slot.open .slot-expand{transform:rotate(90deg)}
.poke-slot-body{display:none;padding:14px;border-top:1px solid var(--border);background:var(--bg3)}
.poke-slot.open .poke-slot-body{display:block}
.ev-row{display:grid;grid-template-columns:repeat(6,1fr);gap:5px}
.ev-label{font-size:10px;text-align:center;color:var(--text3);margin-bottom:2px}
.moves-row{display:grid;grid-template-columns:1fr 1fr;gap:5px}
.selection-result{background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:14px;margin-top:14px}
.selection-pills{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.pill{padding:5px 12px;border-radius:20px;font-size:13px;font-weight:600;background:var(--bg2);border:1px solid var(--border)}
.pill.lead{border-color:var(--accent);color:var(--accent)}
.score-bars{margin-top:12px}
.score-row{display:flex;align-items:center;gap:8px;margin-bottom:5px}
.score-name{width:90px;font-size:12px;color:var(--text);flex-shrink:0}
.score-bar-wrap{flex:1;background:var(--bg2);border-radius:4px;height:7px;overflow:hidden}
.score-bar{height:100%;background:var(--accent);border-radius:4px;transition:width .6s}
.score-val{width:28px;font-size:11px;color:var(--text2);text-align:right}
.battle-layout{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:700px){.battle-layout{grid-template-columns:1fr}}
.state-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.turn-badge{background:var(--accent);color:#fff;padding:3px 12px;border-radius:20px;font-size:13px;font-weight:700}
.matchup{display:flex;align-items:center;justify-content:center;gap:10px;padding:10px 0}
.pokemon-box{text-align:center;flex:1}
.pokemon-name{font-size:14px;font-weight:700;margin-bottom:3px}
.hp-bar-wrap{background:var(--bg3);height:7px;border-radius:4px;overflow:hidden;margin:3px 0}
.hp-bar{height:100%;border-radius:4px;transition:width .4s}
.hp-bar.high{background:var(--green)}.hp-bar.mid{background:var(--yellow)}.hp-bar.low{background:var(--red)}
.hp-text{font-size:11px;color:var(--text2)}
.vs-badge{color:var(--text3);font-size:16px;font-weight:700}
.opp-revealed{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}
.opp-poke-tag{font-size:11px;padding:2px 8px;border-radius:6px;background:var(--bg3);border:1px solid var(--border)}
.turn-section{margin-bottom:12px}
.turn-section-title{font-size:11px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;padding-bottom:4px;border-bottom:1px solid var(--border)}
.toggle-section{display:flex;align-items:center;gap:5px;cursor:pointer;color:var(--text3);font-size:12px}
.toggle-section input{width:auto}
.collapsible{display:none;padding-top:6px}.collapsible.open{display:block}
.rec-card{background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:12px;margin-bottom:8px;transition:border-color .2s}
.rec-card.rank-1{border-color:var(--accent)}
.rec-header{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.rec-rank{width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;flex-shrink:0}
.rec-rank.r1{background:var(--accent);color:#fff}
.rec-rank.r2,.rec-rank.r3{background:var(--bg2);color:var(--text2);border:1px solid var(--border)}
.rec-action{font-size:14px;font-weight:700;flex:1}
.rec-cat{font-size:11px;padding:2px 7px;border-radius:10px;background:var(--bg2);color:var(--text2);border:1px solid var(--border)}
.conf-wrap{display:flex;align-items:center;gap:8px;margin-bottom:5px}
.conf-bar-wrap{flex:1;background:var(--bg2);height:5px;border-radius:3px;overflow:hidden}
.conf-bar{height:100%;border-radius:3px;transition:width .6s}
.conf-bar.high{background:var(--green)}.conf-bar.mid{background:var(--yellow)}.conf-bar.low{background:var(--red)}
.conf-pct{font-size:13px;font-weight:700;width:40px;text-align:right}
.conf-pct.high{color:var(--green)}.conf-pct.mid{color:var(--yellow)}.conf-pct.low{color:var(--red)}
.rec-reason{font-size:12px;color:var(--text2);line-height:1.5}
.estimate-panel{background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:12px}
.estimate-row{display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid var(--border)}
.estimate-row:last-child{border-bottom:none}
.est-label{font-size:11px;color:var(--text3);width:68px;flex-shrink:0}
.est-value{font-size:13px;color:var(--text);flex:1}
.est-badge{font-size:11px;padding:2px 6px;border-radius:10px;background:var(--yellow);color:#1a1d27;font-weight:700}
.est-badge.confirmed{background:var(--green)}
.text-muted{color:var(--text3);font-size:12px}
.notice{background:rgba(79,142,247,0.1);border:1px solid rgba(79,142,247,0.3);border-radius:8px;padding:9px 12px;font-size:12px;color:var(--text2);margin-bottom:10px}
.empty-state{text-align:center;padding:32px;color:var(--text3)}
.log-area{background:var(--bg);border-radius:6px;padding:8px;max-height:140px;overflow-y:auto;font-size:12px;color:var(--text2);font-family:monospace}
.log-entry{padding:2px 0;border-bottom:1px solid var(--border)}
/* コンボボックス */
.combo-wrap{position:relative;width:100%}
.combo-list{position:absolute;top:100%;left:0;right:0;background:var(--bg3);border:1px solid var(--border);border-radius:6px;max-height:200px;overflow-y:auto;z-index:500;display:none;list-style:none;margin-top:2px;box-shadow:0 4px 12px rgba(0,0,0,.3)}
.combo-list.open{display:block}
.combo-item{padding:6px 9px;cursor:pointer;font-size:13px;color:var(--text)}
.combo-item:hover,.combo-item.active{background:var(--border)}
/* ホーム画面 */
.home-btns{display:flex;gap:20px;justify-content:center;flex-wrap:wrap;margin-top:32px}
.home-btn{padding:20px 40px;font-size:16px;font-weight:700;border-radius:12px;border:2px solid transparent;cursor:pointer;transition:all .2s;font-family:inherit;display:flex;flex-direction:column;align-items:center;gap:8px;min-width:180px}
.home-btn-icon{font-size:36px}
.home-btn-primary{background:var(--accent);color:#fff;border-color:var(--accent)}.home-btn-primary:hover{filter:brightness(1.1);transform:translateY(-2px)}
.home-btn-secondary{background:var(--bg2);color:var(--text);border-color:var(--border)}.home-btn-secondary:hover{border-color:var(--accent);color:var(--accent)}
</style>
</head>
<body>
<header>
  <h1>Champions <span>AI</span> 対戦ナビゲーター</h1>
  <button id="home-btn" onclick="goHome()">← ホーム</button>
  <div class="steps" id="steps-display">
    <div class="step active" id="step-ind-1"><span class="step-num">1</span> パーティ設定</div>
    <div class="step" id="step-ind-2"><span class="step-num">2</span> 相手パーティ</div>
    <div class="step" id="step-ind-3"><span class="step-num">3</span> 選出確定</div>
    <div class="step" id="step-ind-4"><span class="step-num">4</span> バトル</div>
  </div>
  <button class="btn-theme" id="theme-btn" onclick="toggleTheme()">☀ ライト</button>
</header>
<main>
<!-- ホーム画面 -->
<div class="page active" id="page-0">
  <div style="text-align:center;padding:50px 20px 30px">
    <div style="font-size:52px;margin-bottom:12px">⚔</div>
    <h2 style="font-size:24px;font-weight:700;margin-bottom:6px">Champions AI</h2>
    <p class="text-muted" style="font-size:14px;margin-bottom:36px">対戦ナビゲーター</p>
    <div class="home-btns">
      <button class="home-btn home-btn-primary" onclick="enterBattleMode()">
        <span class="home-btn-icon">⚔</span>バトルAI
      </button>
      <button class="home-btn home-btn-secondary" onclick="enterPartyMode()">
        <span class="home-btn-icon">📋</span>パーティの登録
      </button>
    </div>
  </div>
</div>
<!-- パーティ設定 -->
<div class="page" id="page-1">
  <!-- 登録済みパーティ管理 -->
  <div class="card" id="party-manager-card">
    <div class="card-title">登録済みパーティ</div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px">
      <select id="saved-party-select" style="flex:1;min-width:180px"><option value="">-- 登録済みパーティを選択 --</option></select>
      <button class="btn btn-secondary btn-sm" onclick="loadSavedParty()">読み込む</button>
      <button class="btn btn-secondary btn-sm" onclick="deleteSavedParty()">削除</button>
    </div>
    <div style="display:flex;gap:8px">
      <input type="text" id="save-party-name" placeholder="パーティ名を入力" style="flex:1">
      <button class="btn btn-primary btn-sm" onclick="saveCurrentParty()">現在のパーティを保存</button>
    </div>
  </div>
  <!-- パーティ入力 -->
  <div class="card">
    <div class="card-title">自分のパーティ設定 <span class="badge">最大6体</span></div>
    <p class="text-muted" style="margin-bottom:12px">ポケモン名が入力された枠のみ登録されます。</p>
    <div id="party-slots"></div>
    <div class="notice" style="margin-top:2px">未使用の枠は空欄のまま次へ進んでください。</div>
  </div>
  <div class="btn-row">
    <button class="btn btn-secondary" id="party-only-back-btn" style="display:none" onclick="goStep(0)">← ホームへ戻る</button>
    <button class="btn btn-primary" id="battle-next-btn" onclick="submitParty()">次へ：相手パーティ入力 →</button>
  </div>
</div>
<!-- 相手パーティ -->
<div class="page" id="page-2">
  <div class="card">
    <div class="card-title">相手のパーティ入力 <span class="badge">6体</span></div>
    <p class="text-muted" style="margin-bottom:12px">相手の6体を入力してください（日本語名）。</p>
    <div class="grid grid-2" id="opp-inputs-area"></div>
    <div id="selection-result-area" style="display:none">
      <hr style="border:none;border-top:1px solid var(--border);margin:14px 0">
      <div class="card-title" style="margin-bottom:8px">AIによる選出推薦</div>
      <div class="selection-result" id="selection-result-box"></div>
    </div>
  </div>
  <div class="btn-row">
    <button class="btn btn-secondary" onclick="goStep(1)">← 戻る</button>
    <button class="btn btn-primary" onclick="submitOpponent()">選出推薦を取得</button>
    <button class="btn btn-success" id="goto-step3-btn" style="display:none" onclick="goStep(3)">次へ：選出確定 →</button>
  </div>
</div>
<!-- 選出確定 -->
<div class="page" id="page-3">
  <div class="card">
    <div class="card-title">選出確定</div>
    <p class="text-muted" style="margin-bottom:12px">バトルに出す3体とリードを確定してください。</p>
    <div class="grid grid-3" style="margin-bottom:12px">
      <div class="field"><label>選出1体目 ★リード候補</label><select id="sel0"><option value="">選択してください</option></select></div>
      <div class="field"><label>選出2体目</label><select id="sel1"><option value="">選択してください</option></select></div>
      <div class="field"><label>選出3体目</label><select id="sel2"><option value="">選択してください</option></select></div>
    </div>
    <div class="grid grid-2">
      <div class="field"><label>自分のリード</label><select id="lead-my"><option value="">選択してください</option></select></div>
      <div class="field"><label>相手のリード</label><select id="lead-opp"><option value="">選択してください</option></select></div>
    </div>
  </div>
  <div class="btn-row">
    <button class="btn btn-secondary" onclick="goStep(2)">← 戻る</button>
    <button class="btn btn-success" onclick="startBattle()">⚔ バトル開始！</button>
  </div>
</div>
<!-- バトル -->
<div class="page" id="page-4">
  <div class="card" style="margin-bottom:10px;padding:12px 18px">
    <div class="state-header">
      <div class="turn-badge" id="turn-badge">ターン 1</div>
      <div style="display:flex;gap:8px;align-items:center">
        <span class="text-muted" id="alive-info">自 3体 / 相手判明 1体</span>
        <button class="btn btn-secondary btn-sm" onclick="endBattle()">バトル終了</button>
      </div>
    </div>
    <div class="matchup">
      <div class="pokemon-box">
        <div class="pokemon-name" id="my-active-name">-</div>
        <div class="hp-bar-wrap"><div class="hp-bar high" id="my-hp-bar" style="width:100%"></div></div>
        <div class="hp-text" id="my-hp-text">HP: -</div>
      </div>
      <div class="vs-badge">VS</div>
      <div class="pokemon-box">
        <div class="pokemon-name" id="opp-active-name">-</div>
        <div class="hp-bar-wrap"><div class="hp-bar high" id="opp-hp-bar" style="width:100%"></div></div>
        <div class="hp-text" id="opp-hp-text">残HP: -</div>
      </div>
    </div>
    <div>
      <div class="text-muted" style="font-size:11px;margin-bottom:3px">判明した相手のポケモン</div>
      <div class="opp-revealed" id="opp-revealed-list"></div>
    </div>
  </div>
  <div class="battle-layout">
    <div>
      <div class="card">
        <div class="card-title">ターン入力</div>
        <div class="turn-section">
          <div class="turn-section-title">特性発動（任意）</div>
          <label class="toggle-section"><input type="checkbox" id="has-ability" onchange="toggleSection(\'ability-section\',this.checked)"> 特性が発動した</label>
          <div class="collapsible" id="ability-section">
            <div class="grid grid-2" style="margin-top:5px">
              <div class="field"><label>発動プレイヤー</label><select id="ab-player"><option value="p2">相手</option><option value="p1">自分</option></select></div>
              <div class="field"><label>特性名</label><input type="text" id="ab-name" placeholder="例: いかく"></div>
            </div>
            <div class="field" style="margin-top:5px"><label>発動ポケモン</label>
              <div class="combo-wrap"><input class="combo-input" type="text" id="ab-poke" placeholder="例: カイリュー" autocomplete="off"></div>
            </div>
          </div>
        </div>
        <div class="turn-section">
          <div class="turn-section-title">交代（任意）</div>
          <div class="grid grid-2">
            <div>
              <label class="toggle-section"><input type="checkbox" id="has-my-switch" onchange="toggleSection(\'my-switch-section\',this.checked)"> 自分が交代した</label>
              <div class="collapsible" id="my-switch-section"><select id="my-switch-to" style="margin-top:5px"><option value="">交代先を選択</option></select></div>
            </div>
            <div>
              <label class="toggle-section"><input type="checkbox" id="has-opp-switch" onchange="toggleSection(\'opp-switch-section\',this.checked)"> 相手が交代した</label>
              <div class="collapsible" id="opp-switch-section">
                <div class="combo-wrap" style="margin-top:5px"><input class="combo-input" type="text" id="opp-switch-to" placeholder="交代先のポケモン名" autocomplete="off"></div>
              </div>
            </div>
          </div>
        </div>
        <div class="turn-section" id="mega-section" style="display:none">
          <div class="turn-section-title">メガシンカ（任意）</div>
          <div class="grid grid-2">
            <label class="toggle-section"><input type="checkbox" id="my-mega"> 自分がメガシンカした</label>
            <label class="toggle-section"><input type="checkbox" id="opp-mega"> 相手がメガシンカした</label>
          </div>
        </div>
        <div class="turn-section">
          <div class="turn-section-title">ターン終了後の状態</div>
          <div class="grid grid-2">
            <div class="field">
              <label>相手の残HP（%）</label>
              <div style="display:flex;gap:5px;align-items:center">
                <input type="range" id="opp-hp-slider" min="0" max="100" value="100" oninput="document.getElementById(\'opp-hp-num\').value=this.value;updateOppHpBar(this.value)" style="flex:1;width:auto;padding:0;background:transparent;border:none">
                <input type="number" id="opp-hp-num" min="0" max="100" value="100" style="width:58px" oninput="document.getElementById(\'opp-hp-slider\').value=this.value;updateOppHpBar(this.value)">
                <span class="text-muted">%</span>
              </div>
            </div>
            <div class="field"><label>自分の残HP（実数値）</label><input type="number" id="my-hp-input" min="0" placeholder="例: 212"></div>
          </div>
          <div class="grid grid-2" style="margin-top:6px">
            <div class="field"><label>自分の状態異常</label><select id="my-status-change"><option value="">変化なし</option><option value="par">まひ</option><option value="brn">やけど</option><option value="slp">ねむり</option><option value="psn">どく</option><option value="tox">もうどく</option><option value="frz">こおり</option><option value="none">回復</option></select></div>
            <div class="field"><label>相手の状態異常</label><select id="opp-status-change"><option value="">変化なし</option><option value="par">まひ</option><option value="brn">やけど</option><option value="slp">ねむり</option><option value="psn">どく</option><option value="tox">もうどく</option><option value="frz">こおり</option><option value="none">回復</option></select></div>
          </div>
        </div>
        <div class="turn-section">
          <div class="turn-section-title">相手の行動</div>
          <div class="grid grid-2">
            <div class="field"><label>相手が使用した技</label><input type="text" id="opp-move" placeholder="例: ダブルウイング"></div>
            <div class="field"><label>技を受けた後の自分の残HP</label><input type="number" id="opp-move-my-hp" placeholder="例: 150"></div>
          </div>
        </div>
        <div class="turn-section">
          <div class="turn-section-title">アイテム発動（任意）</div>
          <div class="grid grid-2">
            <div class="field"><label>自分のアイテム消費</label><input type="text" id="my-item-used" placeholder="例: オボンのみ"></div>
            <div class="field"><label>相手のアイテム発動</label><input type="text" id="opp-item-used" placeholder="例: きのみ"></div>
          </div>
        </div>
        <div class="btn-row" style="margin-top:2px"><button class="btn btn-primary" onclick="submitTurn()">推薦を取得 →</button></div>
      </div>
    </div>
    <div>
      <div class="card" style="margin-bottom:10px">
        <div class="card-title">行動推薦</div>
        <div id="rec-area"><div class="empty-state"><div style="font-size:28px;margin-bottom:8px">⚔</div><div>ターン情報を入力して<br>「推薦を取得」を押してください</div></div></div>
      </div>
      <div class="card" style="margin-bottom:10px">
        <div class="card-title">相手ポケモンの推測情報</div>
        <div id="opp-estimate-area"><div class="empty-state" style="padding:16px">まだ情報がありません</div></div>
      </div>
      <div class="card">
        <div class="card-title" style="margin-bottom:6px">行動ログ</div>
        <div class="log-area" id="action-log"></div>
      </div>
    </div>
  </div>
</div>
</main>
<script>
const RENDER_URL='https://champions-ai-api.onrender.com';
const API_URL=(()=>{const h=window.location.hostname;return(h===\'localhost\'||h===\'127.0.0.1\')?\'':RENDER_URL;})();
'''

PART3 = r"""
const STONE_JP={'Venusaurite':'フシギバナイト','Charizardite X':'リザードナイトX','Charizardite Y':'リザードナイトY','Blastoisinite':'カメックスナイト','Beedrillite':'スピアーナイト','Pidgeotite':'ピジョットナイト','Alakazite':'フーディンナイト','Slowbronite':'ヤドランナイト','Gengarite':'ゲンガーナイト','Kangaskhanite':'ガルーラナイト','Pinsirite':'カイロスナイト','Gyaradosite':'ギャラドスナイト','Aerodactylite':'プテラナイト','Mewtwonite X':'ミュウツーナイトX','Mewtwonite Y':'ミュウツーナイトY','Ampharosite':'デンリュウナイト','Scizorite':'ハッサムナイト','Heracronite':'ヘラクロスナイト','Houndoominite':'ヘルガーナイト','Tyranitarite':'バンギラスナイト','Sceptilite':'ジュカインナイト','Blazikenite':'バシャーモナイト','Swampertite':'ラグラージナイト','Gardevoirite':'サーナイトナイト','Sablenite':'ヤミラミナイト','Mawilite':'クチートナイト','Aggronite':'ボスゴドラナイト','Medichamite':'チャーレムナイト','Manectite':'ライボルトナイト','Sharpedonite':'サメハダーナイト','Cameruptite':'バクーダナイト','Altarianite':'チルタリスナイト','Banettite':'ジュペッタナイト','Absolite':'アブソルナイト','Glalitite':'オニゴーリナイト','Salamencite':'ボーマンダナイト','Latiasite':'ラティアスナイト','Latiosite':'ラティオスナイト','Dragon Ascent':'（りゅうのまい習得で自動メガ）','Lopunnite':'ミミロップナイト','Garchompite':'ガブリアスナイト','Lucarionite':'ルカリオナイト','Abomasite':'ユキノオーナイト','Galladite':'エルレイドナイト','Audinite':'タブンネナイト','Diancite':'ディアンシーナイト','Steelixite':'ハガネールナイト','Feraligatrite':'オーダイルナイト','Meganiumite':'メガニウムナイト','Typhlosionite':'バクフーンナイト','Togecisite':'トゲキッスナイト','Donphanite':'ドンファンナイト','Sudowoodoite':'ウソッキーナイト','Politoedite':'ニョロトノナイト','Victreebelite':'ウツボットナイト','Starmiite':'スターミーナイト','Cloysterite':'パルシェンナイト','Dragonite':'カイリューナイト','Kingdrite':'キングドラナイト','Mr. Mimite':'バリヤードナイト','Jynxite':'ルージュラナイト'};
const ABILITY_JP={'adaptability':'てきおうりょく','aftermath':'ばくはつ','air-lock':'エアロック','analytic':'アナライズ','anger-point':'いかりのつぼ','anticipation':'きけんよち','arena-trap':'ありじごく','aroma-veil':'アロマベール','aura-break':'オーラブレイク','bad-dreams':'ナイトメア','battle-armor':'カブトアーマー','big-pecks':'はとむね','blaze':'もうか','cheek-pouch':'ほおぶくろ','chlorophyll':'ようりょくそ','clear-body':'クリアボディ','cloud-nine':'ノーてんき','color-change':'へんしょく','competitive':'かちき','compound-eyes':'ふくがん','contrary':'あまのじゃく','cursed-body':'のろわれボディ','cute-charm':'メロメロボディ','damp':'しめりけ','dark-aura':'ダークオーラ','defeatist':'よわき','defiant':'まけんき','download':'ダウンロード','drizzle':'あめふらし','drought':'ひでり','dry-skin':'かんそうはだ','early-bird':'はやおき','effect-spore':'ほうし','fairy-aura':'フェアリーオーラ','filter':'フィルター','flame-body':'ほのおのからだ','flare-boost':'ねつぼうそう','flash-fire':'もらいび','flower-gift':'フラワーギフト','flower-veil':'フラワーベール','forecast':'てんきや','forewarn':'よちむ','friend-guard':'フレンドガード','frisk':'おみとおし','fur-coat':'ファーコート','gale-wings':'はやてのつばさ','gluttony':'くいしんぼう','gooey':'ぬめぬめ','grass-pelt':'グラスペルト','guts':'こんじょう','harvest':'みのりもの','healer':'いやしのこころ','heatproof':'たいねつ','heavy-metal':'ヘビーメタル','honey-gather':'みつあつめ','huge-power':'ちからもち','hustle':'はりきり','hydration':'うるおいボディ','hyper-cutter':'かいりきバサミ','ice-body':'アイスボディ','illuminate':'はっこう','illusion':'イリュージョン','immunity':'めんえき','infiltrator':'すりぬけ','inner-focus':'せいしんりょく','insomnia':'ふみん','intimidate':'いかく','iron-barbs':'てつのトゲ','iron-fist':'てつのこぶし','justified':'せいぎのこころ','keen-eye':'するどいめ','klutz':'ぶきよう','leaf-guard':'リーフガード','levitate':'ふゆう','light-metal':'ライトメタル','lightning-rod':'ひらいしん','limber':'じゅうなん','liquid-ooze':'えんしゅつ','magic-bounce':'マジックミラー','magic-guard':'マジックガード','magician':'マジシャン','magma-armor':'マグマのよろい','magnet-pull':'じりょく','marvel-scale':'ふしぎなうろこ','mega-launcher':'メガランチャー','minus':'マイナス','mold-breaker':'かたやぶり','moody':'きまぐれ','motor-drive':'でんきエンジン','moxie':'じしんかじょう','multiscale':'マルチスケイル','multitype':'マルチタイプ','mummy':'ミイラ','natural-cure':'しぜんかいふく','neutralizing-gas':'かがくへんかガス','no-guard':'ノーガード','normalize':'ノーマルスキン','oblivious':'マイペース','overcoat':'ぼうじん','overgrow':'しんりょく','own-tempo':'マイペース','pickpocket':'すりぬけ','pickup':'ものひろい','pixilate':'フェアリースキン','plus':'プラス','poison-heal':'どくぼうそう','poison-point':'どくのとげ','poison-touch':'どくてまし','prankster':'いたずらごころ','pressure':'プレッシャー','protean':'へんげんじざい','pure-power':'ちからもち','quick-feet':'はやあし','rain-dish':'アメうけざら','rattled':'びびり','reckless':'すてみ','refrigerate':'フリーズスキン','regenerator':'さいせいりょく','rivalry':'きょうそうしん','rock-head':'いしあたま','rough-skin':'さめはだ','run-away':'にげあし','sand-force':'すなのちから','sand-rush':'すなかき','sand-stream':'すなおこし','sand-veil':'すながくれ','sap-sipper':'そうしょく','scrappy':'やるき','serene-grace':'てんのめぐみ','shadow-tag':'かげふみ','sharpness':'きれあじ','shed-skin':'だっぴ','sheer-force':'ちからずく','shell-armor':'シェルアーマー','shield-dust':'りんぷん','simple':'たんじゅん','skill-link':'スキルリンク','slush-rush':'スラッシュラッシュ','sniper':'スナイパー','snow-cloak':'ゆきがくれ','snow-warning':'ゆきふらし','solar-power':'サンパワー','solid-rock':'ハードロック','soundproof':'ぼうおん','speed-boost':'かそく','stall':'なまけ','stance-change':'バトルスイッチ','static':'せいでんき','steadfast':'ふくつのこころ','stench':'あくしゅう','sticky-hold':'ねんちゃく','storm-drain':'よびみず','strong-jaw':'がんじょうあご','sturdy':'がんじょう','suction-cups':'きゅうばん','super-luck':'きょううん','swarm':'むしのしらせ','sweet-veil':'スイートベール','swift-swim':'すいすい','symbiosis':'きずなのきずな','synchronize':'シンクロ','tangled-feet':'よたよた','technician':'テクニシャン','telepathy':'テレパシー','teravolt':'テラボルテージ','thick-fat':'あついしぼう','tinted-lens':'いろめがね','torrent':'げきりゅう','tough-claws':'かたいツメ','toxic-boost':'どくぼうそう','trace':'トレース','truant':'なまけ','turboblaze':'タービュレーズ','unaware':'てんねん','unburden':'かるわざ','unnerve':'きんちょうかん','victory-star':'しょうりのほし','vital-spirit':'やるき','volt-absorb':'ちくでん','water-absorb':'ちょすい','water-veil':'みずのベール','weak-armor':'やわらかいよろい','white-smoke':'しろいけむり','wind-rider':'かぜのり','wonder-skin':'ふしぎなまもり','zen-mode':'ダルマモード','merciless':'きょうい','stamina':'スタミナ','wimp-out':'にげごし','emergency-exit':'ひじょうぐち','water-compaction':'たいすいへん','fluffy':'もふもふ','dazzling':'おどろかす','soul-heart':'こんがんのこころ','tangling-hair':'もじゃもじゃ','receiver':'レシーバー','power-of-alchemy':'かがくのちから','beast-boost':'ビーストブースト','rks-system':'ARシステム','electric-surge':'エレキメーカー','psychic-surge':'サイコメーカー','misty-surge':'ミストメーカー','grassy-surge':'グラスメーカー','full-metal-body':'メタルプロテクト','shadow-shield':'ファントムガード','prism-armor':'プリズムアーマー','neuroforce':'ニューロフォース','intrepid-sword':'ふとうのけん','dauntless-shield':'きんだいのたて','libero':'リベロ','ball-fetch':'ボールゲット','cotton-down':'わたほうし','propeller-tail':'スクリューおびれ','mirror-armor':'ミラーアーマー','gulp-missile':'のみこむ','stalwart':'ふくつのたて','steam-engine':'じょうきエンジン','punk-rock':'パンクロック','sand-spit':'すなはく','ice-scales':'こおりのりんぷん','ripen':'かじゅくさ','ice-face':'アイスフェイス','power-spot':'パワースポット','mimicry':'ほうでん','screen-cleaner':'スクリーンクリーナー','steely-spirit':'はがねのせいしん','perish-body':'ほろびのボディ','wandering-spirit':'さまよいのたましい','gorilla-tactics':'ごりむちゅう','neutralizing-gas':'かがくへんかガス','pastel-veil':'パステルベール','hunger-switch':'はらぺこスイッチ','quick-draw':'はやぬき','unseen-fist':'みえないこぶし','curious-medicine':'ふしぎなくすり','transistor':'トランジスタ','dragons-maw':'りゅうのあぎと','chilling-neigh':'はくばのいななき','grim-neigh':'こくばのいななき','as-one-ice':'ふたつのちから（こおり）','as-one-shadow':'ふたつのちから（シャドー）','protosynthesis':'こだいかっせい','quark-drive':'クォークチャージ','orichalcum-pulse':'はどうのたいこ','hadron-engine':'ハドロンエンジン','supremacy':'はくじょ','zero-to-hero':'ゼロtoヒーロー','commander':'かがみのよろい','lingering-aroma':'のこりかが','seed-sower':'たねまき','thermal-exchange':'ねつこうかん','anger-shell':'いかりのこうら','purifying-salt':'せいしょくのしお','well-baked-body':'やけどいやし','wind-power':'かぜのりもの','zero-to-hero':'ゼロtoヒーロー','good-as-gold':'ゴールドボディ','vessel-of-ruin':'わざわいのうつわ','sword-of-ruin':'わざわいのつるぎ','tablets-of-ruin':'わざわいのおふだ','beads-of-ruin':'わざわいのたま','rocky-payload':'がんせきうんぱん','wind-rider':'かぜのり','guard-dog':'ばんけん','rocky-payload':'がんせきうんぱん','mycelium-might':'きんしのちから','hospitality':'もてなし','toxic-debris':'どくのくさり','armor-tail':'しっぽのよろい','earth-eater':'じめんくいしん','friend-guard':'フレンドガード'};
const MOVES_SET=new Set(MOVES_LIST);
const POKE_MAP={};POKEMON_DATA.forEach(p=>{POKE_MAP[p.n]=p;});
const POKE_MEGA={};POKEMON_DATA.forEach(p=>{const mg=MEGA_MAP[p.e];if(mg&&mg.length)POKE_MEGA[p.n]=mg.map(m=>({mega_jp:m.m,stone_jp:STONE_JP[m.s]||(m.s?m.s:'('+m.m+')')}));});
const POKEMON_NAMES=POKEMON_DATA.map(p=>p.n);
let currentStep=1,myPartyData=[],oppPartyNames=[],selectionRec=null,turnNum=1;
let battleState={myActive:'',oppActive:''};
let myMegaDone=false,oppMegaDone=false;
let appMode='home';

// ── テーマ ──────────────────────────────────────────────────
function toggleTheme(){const html=document.documentElement,isDark=html.getAttribute('data-theme')==='dark';html.setAttribute('data-theme',isDark?'light':'dark');document.getElementById('theme-btn').textContent=isDark?'🌙 ダーク':'☀ ライト';localStorage.setItem('nav_theme',isDark?'light':'dark');}
(()=>{const s=localStorage.getItem('nav_theme')||'dark';document.documentElement.setAttribute('data-theme',s);document.getElementById('theme-btn').textContent=s==='dark'?'☀ ライト':'🌙 ダーク';})();

// ── コンボボックス ─────────────────────────────────────────
function makeCombo(inputEl,dataArr,onSelect){
  const wrap=inputEl.closest('.combo-wrap')||inputEl.parentElement;
  const ul=document.createElement('ul');ul.className='combo-list';wrap.appendChild(ul);
  function render(items){
    ul.innerHTML=items.slice(0,120).map(v=>`<li class="combo-item" data-v="${v}">${v}</li>`).join('');
    ul.classList.toggle('open',items.length>0);
    ul.querySelectorAll('.combo-item').forEach(li=>{
      li.onmousedown=e=>{e.preventDefault();inputEl.value=li.dataset.v;ul.classList.remove('open');onSelect&&onSelect(li.dataset.v);};
    });
  }
  // アイテムリストを動的に差し替え可能にする
  inputEl._comboData=dataArr;
  inputEl._comboRender=render;
  inputEl.addEventListener('input',()=>{const q=inputEl.value;const d=inputEl._comboData;render(q?d.filter(v=>v.includes(q)):d.slice(0,50));});
  inputEl.addEventListener('focus',()=>{const q=inputEl.value;const d=inputEl._comboData;render(q?d.filter(v=>v.includes(q)):d.slice(0,50));});
  inputEl.addEventListener('blur',()=>setTimeout(()=>ul.classList.remove('open'),150));
}

// ── API ────────────────────────────────────────────────────
async function api(path,method='GET',body=null){const opts={method,headers:{'Content-Type':'application/json'}};if(body)opts.body=JSON.stringify(body);try{const res=await fetch(API_URL+path,opts);if(!res.ok){const err=await res.json().catch(()=>({detail:res.statusText}));throw new Error(err.detail||res.statusText);}return await res.json();}catch(e){if(e instanceof TypeError)throw new Error('サーバーに接続できません。');throw e;}}
function showError(msg){alert('エラー: '+msg);}

// ── ページ遷移 ──────────────────────────────────────────────
function goStep(n){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.getElementById('page-'+n).classList.add('active');
  document.getElementById('steps-display').style.display=(n===0)?'none':'';
  document.getElementById('home-btn').style.display=(n===0)?'none':'';
  if(n>0){for(let i=1;i<=4;i++)document.getElementById('step-ind-'+i).className='step'+(i===n?' active':(i<n?' done':''));}
  currentStep=n;
}
function goHome(){
  if(currentStep===4&&!confirm('バトルを中断してホームに戻りますか？'))return;
  appMode='home';
  goStep(0);
}
function enterBattleMode(){
  appMode='battle';
  goStep(1);
  const nb=document.getElementById('battle-next-btn');if(nb)nb.style.display='';
  const bb=document.getElementById('party-only-back-btn');if(bb)bb.style.display='none';
  refreshPartySelect();
}
function enterPartyMode(){
  appMode='party';
  goStep(1);
  const nb=document.getElementById('battle-next-btn');if(nb)nb.style.display='none';
  const bb=document.getElementById('party-only-back-btn');if(bb)bb.style.display='';
  refreshPartySelect();
}

// ── パーティ登録（localStorage） ──────────────────────────
function getSavedParties(){return JSON.parse(localStorage.getItem('champions_parties')||'[]');}
function refreshPartySelect(){
  const sel=document.getElementById('saved-party-select'),parties=getSavedParties();
  sel.innerHTML='<option value="">-- 登録済みパーティを選択 --</option>'
    +parties.map((p,i)=>`<option value="${i}">${p.name}（${p.party.length}体）</option>`).join('');
}
function saveCurrentParty(){
  const name=document.getElementById('save-party-name').value.trim();
  if(!name){showError('パーティ名を入力してください');return;}
  const party=collectPartyData();
  if(!party.length){showError('ポケモンを1体以上入力してください');return;}
  const parties=getSavedParties();
  parties.push({name,created:new Date().toLocaleDateString('ja'),party});
  localStorage.setItem('champions_parties',JSON.stringify(parties));
  refreshPartySelect();
  document.getElementById('save-party-name').value='';
  alert(`「${name}」を保存しました`);
}
function loadSavedParty(){
  const idx=document.getElementById('saved-party-select').value;
  if(idx===''){showError('パーティを選択してください');return;}
  const p=getSavedParties()[+idx];
  applyPartyToSlots(p.party);
}
function deleteSavedParty(){
  const idx=document.getElementById('saved-party-select').value;
  if(idx==='')return;
  const parties=getSavedParties();
  if(!confirm(`「${parties[+idx].name}」を削除しますか？`))return;
  parties.splice(+idx,1);
  localStorage.setItem('champions_parties',JSON.stringify(parties));
  refreshPartySelect();
}
function applyPartyToSlots(party){
  // スロットをリセット
  slotCount=0;
  document.getElementById('party-slots').innerHTML='';
  for(let i=0;i<6;i++)addPokeSlot();
  // データを反映
  party.forEach((p,i)=>{
    if(i>=6)return;
    const nameEl=document.getElementById(`poke-namejp-${i}`);
    if(nameEl){nameEl.value=p.name_jp;onPokeSelect(i);}
    setTimeout(()=>{
      const abil=document.getElementById(`poke-ability-${i}`);
      if(abil&&p.ability){abil.value=p.ability;}
      const itemEl=document.getElementById(`poke-item-${i}`);
      if(itemEl&&p.item){itemEl.value=p.item;}
      const natEl=document.getElementById(`poke-nature-${i}`);
      if(natEl&&p.nature){natEl.value=p.nature;}
      const gendEl=document.getElementById(`poke-gender-${i}`);
      if(gendEl&&p.gender){gendEl.value=p.gender;}
      ['H','A','B','C','D','S'].forEach(s=>{
        const ev=document.getElementById(`poke-ev-${s}-${i}`);
        if(ev&&p.evs)ev.value=p.evs[s]||0;
      });
      (p.moves||[]).forEach((m,mi)=>{
        const mv=document.getElementById(`poke-move${mi+1}-${i}`);
        if(mv){mv.value=m;validateMove(mv);}
      });
      updateSlotSummary(i);
    },50);
  });
}

// ── パーティスロット ───────────────────────────────────────
const NATURES=['がんばりや','さみしがり','ゆうかん','いじっぱり','やんちゃ','ずぶとい','すなお','のんき','わんぱく','いやしんぼ','おくびょう','せっかち','まじめ','ようき','むじゃき','ひかえめ','おっとり','れいせい','てれや','うっかりや','おだやか','おとなしい','なまいき','しんちょう','きまぐれ'];
const NL={'がんばりや':'無補正','さみしがり':'A↑B↓','ゆうかん':'A↑S↓','いじっぱり':'A↑C↓','やんちゃ':'A↑D↓','ずぶとい':'B↑A↓','すなお':'無補正','のんき':'B↑S↓','わんぱく':'B↑C↓','いやしんぼ':'B↑D↓','おくびょう':'S↑A↓','せっかち':'S↑B↓','まじめ':'無補正','ようき':'S↑C↓','むじゃき':'S↑D↓','ひかえめ':'C↑A↓','おっとり':'C↑B↓','れいせい':'C↑S↓','てれや':'無補正','うっかりや':'C↑D↓','おだやか':'D↑A↓','おとなしい':'D↑B↓','なまいき':'D↑S↓','しんちょう':'D↑C↓','きまぐれ':'無補正'};
let slotCount=0;
function buildNatureSelect(id){return'<select id="'+id+'">'+NATURES.map(n=>`<option value="${n}">${n}（${NL[n]}）</option>`).join('')+'</select>';}
function onPokeSelect(i){const n=document.getElementById(`poke-namejp-${i}`).value;updateAbilitySelect(i,n);updateItemCombo(i,n);updateSlotSummary(i);}
function updateAbilitySelect(i,nameJp){const sel=document.getElementById(`poke-ability-${i}`);if(!sel)return;const p=POKE_MAP[nameJp];sel.innerHTML='<option value="">選択してください</option>';if(p&&p.a.length)p.a.forEach(s=>{const jp=ABILITY_JP[s]||s;const o=document.createElement('option');o.value=jp;o.textContent=jp;sel.appendChild(o);});}
function updateItemCombo(i,nameJp){
  const el=document.getElementById(`poke-item-${i}`);if(!el)return;
  const mg=POKE_MEGA[nameJp];
  let list=['なし'];
  if(mg&&mg.length){mg.forEach(m=>{list.push(m.stone_jp);});ITEMS_LIST.forEach(it=>list.push(it));}
  else{ITEMS_LIST.forEach(it=>list.push(it));}
  el._comboData=list;
}
function validateMove(input){const v=input.value.trim();if(!v){input.classList.remove('invalid','valid');return;}input.classList.toggle('invalid',!MOVES_SET.has(v));input.classList.toggle('valid',MOVES_SET.has(v));}
function addPokeSlot(){if(slotCount>=6)return;const i=slotCount++;const c=document.getElementById('party-slots');const div=document.createElement('div');div.className='poke-slot';div.id=`slot-${i}`;
div.innerHTML=`<div class="poke-slot-header" onclick="toggleSlot(${i})"><div class="slot-num">${i+1}</div><div class="slot-summary" id="slot-summary-${i}"><span style="color:var(--text3)">クリックして入力</span></div><div class="slot-expand">›</div></div><div class="poke-slot-body"><div class="grid grid-2" style="margin-bottom:8px"><div class="field"><label>ポケモン名</label><div class="combo-wrap"><input class="combo-input" type="text" id="poke-namejp-${i}" placeholder="例: ガブリアス" autocomplete="off"></div></div><div class="field"><label>性別</label><select id="poke-gender-${i}"><option value="-">なし（-）</option><option value="♂">♂</option><option value="♀">♀</option></select></div></div><div class="grid grid-2" style="margin-bottom:8px"><div class="field"><label>持ち物</label><div class="combo-wrap"><input class="combo-input" type="text" id="poke-item-${i}" placeholder="なし" autocomplete="off"></div></div><div class="field"><label>特性</label><select id="poke-ability-${i}"><option value="">選択してください</option></select></div></div><div style="margin-bottom:8px"><div class="field"><label>性格</label>${buildNatureSelect('poke-nature-'+i)}</div></div><div style="margin-bottom:8px"><label style="margin-bottom:5px">努力値（H/A/B/C/D/S）</label><div class="ev-row">${['H','A','B','C','D','S'].map(s=>`<div><div class="ev-label">${s}</div><input type="number" id="poke-ev-${s}-${i}" min="0" max="252" value="0"></div>`).join('')}</div></div><div><label style="margin-bottom:5px">技（最大4つ）<span style="font-size:11px;color:var(--text3);margin-left:6px">※リストにない技は赤枠</span></label><div class="moves-row">${[1,2,3,4].map(m=>`<div class="field"><label>技${m}</label><div class="combo-wrap"><input class="combo-input" type="text" id="poke-move${m}-${i}" placeholder="例: じしん" autocomplete="off"></div></div>`).join('')}</div></div></div>`;
c.appendChild(div);toggleSlot(i);
// コンボ設定
const nameEl=document.getElementById(`poke-namejp-${i}`);
makeCombo(nameEl,POKEMON_NAMES,v=>{onPokeSelect(i);});
const itemEl=document.getElementById(`poke-item-${i}`);
const defaultItems=['なし',...ITEMS_LIST];
makeCombo(itemEl,defaultItems,null);
updateItemCombo(i,'');
for(let m=1;m<=4;m++){
  const mvEl=document.getElementById(`poke-move${m}-${i}`);
  makeCombo(mvEl,MOVES_LIST,null);
  mvEl.addEventListener('input',()=>validateMove(mvEl));
}
}
function toggleSlot(i){document.getElementById(`slot-${i}`).classList.toggle('open');}
function updateSlotSummary(i){const s=document.getElementById(`poke-namejp-${i}`),n=s?s.value:'',it=document.getElementById(`poke-item-${i}`)?.value||'',el=document.getElementById(`slot-summary-${i}`);if(el)el.innerHTML=n?`<strong>${n}</strong>${it&&it!='なし'?' / '+it:''}`:'<span style="color:var(--text3)">クリックして入力</span>';}
function collectPartyData(){const party=[];for(let i=0;i<slotCount;i++){const n=document.getElementById(`poke-namejp-${i}`)?.value.trim()||'';if(!n)continue;const p=POKE_MAP[n];party.push({name_jp:n,name_en:p?p.e:n,item:document.getElementById(`poke-item-${i}`)?.value.trim()||null,ability:document.getElementById(`poke-ability-${i}`)?.value||null,gender:document.getElementById(`poke-gender-${i}`)?.value||'-',nature:document.getElementById(`poke-nature-${i}`)?.value||'まじめ',evs:{H:+document.getElementById(`poke-ev-H-${i}`)?.value||0,A:+document.getElementById(`poke-ev-A-${i}`)?.value||0,B:+document.getElementById(`poke-ev-B-${i}`)?.value||0,C:+document.getElementById(`poke-ev-C-${i}`)?.value||0,D:+document.getElementById(`poke-ev-D-${i}`)?.value||0,S:+document.getElementById(`poke-ev-S-${i}`)?.value||0},moves:[1,2,3,4].map(m=>document.getElementById(`poke-move${m}-${i}`)?.value.trim()||'').filter(Boolean)});}return party;}
async function submitParty(){const party=collectPartyData();if(party.length===0){showError('ポケモンを少なくとも1体選択してください');return;}try{await api('/setup/party','POST',{my_party:party});myPartyData=party;goStep(2);}catch(e){showError(e.message);}}

// ── 相手パーティ入力コンボ初期化 ─────────────────────────
try{(()=>{
  const area=document.getElementById('opp-inputs-area');
  for(let i=0;i<6;i++){
    const d=document.createElement('div');d.className='field';
    d.innerHTML=`<label>相手${i+1}体目</label><div class="combo-wrap"><input class="combo-input" type="text" id="opp${i}" placeholder="例: カイリュー" autocomplete="off"></div>`;
    area.appendChild(d);
  }
  for(let i=0;i<6;i++){
    const el=document.getElementById(`opp${i}`);
    makeCombo(el,POKEMON_NAMES,null);
  }
  // 交代先コンボ（バトル用）
  const oppSwEl=document.getElementById('opp-switch-to');
  if(oppSwEl)makeCombo(oppSwEl,POKEMON_NAMES,null);
  const abPokeEl=document.getElementById('ab-poke');
  if(abPokeEl)makeCombo(abPokeEl,POKEMON_NAMES,null);
})();}catch(e){console.error('combo init error',e);}

async function submitOpponent(){const names=[0,1,2,3,4,5].map(i=>document.getElementById('opp'+i)?.value.trim()).filter(Boolean);if(!names.length){showError('相手のポケモンを少なくとも1体入力してください');return;}try{const r=await api('/setup/opponent','POST',{opponent_party:names});oppPartyNames=names;selectionRec=r;showSelectionResult(r);document.getElementById('selection-result-area').style.display='block';document.getElementById('goto-step3-btn').style.display='';updateStep3Selects(r);}catch(e){showError(e.message);}}
function showSelectionResult(r){const box=document.getElementById('selection-result-box'),ms=Math.max(...Object.values(r.scores));box.innerHTML=`<div class="text-muted" style="margin-bottom:6px">AIが推薦する選出（スコア順）</div><div class="selection-pills">${r.selected.map(n=>`<div class="pill ${n===r.lead?'lead':''}">${n===r.lead?'★ ':''}${n}</div>`).join('')}</div><div class="score-bars" style="margin-top:12px">${Object.entries(r.scores).map(([n,s])=>`<div class="score-row"><div class="score-name">${n}</div><div class="score-bar-wrap"><div class="score-bar" style="width:${Math.round(s/ms*100)}%"></div></div><div class="score-val">${s.toFixed(1)}</div></div><div style="font-size:11px;color:var(--text3);margin:-2px 0 5px 98px">${r.reasons[n]||''}</div>`).join('')}</div>`;}
function updateStep3Selects(rec){const mn=myPartyData.map(p=>p.name_jp);for(let i=0;i<3;i++){const s=document.getElementById(`sel${i}`);s.innerHTML='<option value="">選択してください</option>'+mn.map(n=>`<option value="${n}" ${rec?.selected[i]===n?'selected':''}>${n}</option>`).join('');}const lm=document.getElementById('lead-my');lm.innerHTML='<option value="">選択してください</option>'+mn.map(n=>`<option value="${n}" ${rec?.lead===n?'selected':''}>${n}</option>`).join('');const lo=document.getElementById('lead-opp');lo.innerHTML='<option value="">選択してください</option>'+oppPartyNames.map(n=>`<option value="${n}">${n}</option>`).join('');['sel0','sel1','sel2'].forEach(id=>document.getElementById(id).addEventListener('change',syncLeadSelect));syncLeadSelect();}
function syncLeadSelect(){const sel=['sel0','sel1','sel2'].map(id=>document.getElementById(id).value).filter(Boolean),lm=document.getElementById('lead-my'),cur=lm.value;lm.innerHTML='<option value="">選択してください</option>'+sel.map(n=>`<option value="${n}" ${n===cur?'selected':''}>${n}</option>`).join('');}
async function startBattle(){const sel=['sel0','sel1','sel2'].map(id=>document.getElementById(id).value).filter(Boolean),lm=document.getElementById('lead-my').value,lo=document.getElementById('lead-opp').value;if(sel.length!==3){showError('3体選出してください');return;}if(!lm){showError('自分のリードを選択してください');return;}if(!lo){showError('相手のリードを選択してください');return;}try{await api('/battle/start','POST',{selected:sel,lead_my:lm,lead_opp:lo});turnNum=1;myMegaDone=false;oppMegaDone=false;battleState.myActive=lm;battleState.oppActive=lo;initBattleUI(lm,lo,sel);goStep(4);addLog(`バトル開始: ${lm} vs ${lo}`);}catch(e){showError(e.message);}}
function initBattleUI(lm,lo,sel){document.getElementById('turn-badge').textContent='ターン 1';document.getElementById('my-active-name').textContent=lm;document.getElementById('opp-active-name').textContent=lo;['my-hp-bar','opp-hp-bar'].forEach(id=>{document.getElementById(id).style.width='100%';document.getElementById(id).className='hp-bar high';});document.getElementById('my-hp-text').textContent='HP: -';document.getElementById('opp-hp-text').textContent='残HP: 100%';document.getElementById('opp-revealed-list').innerHTML=`<span class="opp-poke-tag">${lo}</span>`;const sw=document.getElementById('my-switch-to');sw.innerHTML='<option value="">交代先を選択</option>'+sel.filter(n=>n!==lm).map(n=>`<option value="${n}">${n}</option>`).join('');document.getElementById('opp-hp-slider').value=100;document.getElementById('opp-hp-num').value=100;document.getElementById('alive-info').textContent=`自 ${sel.length}体 / 相手判明 1体`;updateMegaSection();}
function updateOppHpBar(pct){const b=document.getElementById('opp-hp-bar');b.style.width=pct+'%';b.className='hp-bar '+(pct>50?'high':pct>25?'mid':'low');}
function updateMegaSection(){
  const myPoke=POKE_MEGA[battleState.myActive];
  const oppPoke=POKE_MEGA[battleState.oppActive];
  document.getElementById('mega-section').style.display=(myPoke||oppPoke)?'':'none';
  document.getElementById('my-mega').disabled=!myPoke||myMegaDone;
  document.getElementById('opp-mega').disabled=!oppPoke||oppMegaDone;
}
function toggleSection(id,open){document.getElementById(id).classList.toggle('open',open);}
async function submitTurn(){const body={turn:turnNum};if(document.getElementById('has-ability').checked)body.ability_activations=[{player:document.getElementById('ab-player').value,ability:document.getElementById('ab-name').value.trim(),pokemon:document.getElementById('ab-poke').value.trim()}];else body.ability_activations=[];if(document.getElementById('has-my-switch').checked)body.my_switch=document.getElementById('my-switch-to').value||null;if(document.getElementById('has-opp-switch').checked)body.opponent_switch=document.getElementById('opp-switch-to').value.trim()||null;const oh=parseInt(document.getElementById('opp-hp-num').value),mh=parseInt(document.getElementById('my-hp-input').value);if(!isNaN(oh))body.opponent_hp_pct=oh;if(!isNaN(mh))body.my_hp_after=mh;const ms=document.getElementById('my-status-change').value,os=document.getElementById('opp-status-change').value;if(ms)body.my_status=ms;if(os)body.opponent_status=os;const om=document.getElementById('opp-move').value.trim(),omh=parseInt(document.getElementById('opp-move-my-hp').value);if(om||!isNaN(omh)){body.opponent_action={};if(om)body.opponent_action.move=om;if(!isNaN(omh))body.opponent_action.my_hp_after=omh;}const mi=document.getElementById('my-item-used').value.trim(),oi=document.getElementById('opp-item-used').value.trim();if(mi)body.my_item_consumed=mi;if(oi)body.opponent_item_activated=oi;
body.my_mega=document.getElementById('my-mega').checked;
body.opp_mega=document.getElementById('opp-mega').checked;
if(body.my_mega)myMegaDone=true;
if(body.opp_mega)oppMegaDone=true;
try{const out=await api('/battle/turn','POST',body);renderRecommendations(out.recommendations);renderOpponentEstimate(out.opponent_estimate);updateBattleState(out,body);addLog(`T${turnNum}: ${out.battle_state_summary}`);turnNum++;document.getElementById('turn-badge').textContent='ターン '+turnNum;clearTurnForm();}catch(e){showError(e.message);}}
function renderRecommendations(recs){if(!recs||!recs.length){document.getElementById('rec-area').innerHTML='<div class="empty-state">推薦が取得できませんでした</div>';return;}document.getElementById('rec-area').innerHTML=recs.map((r,idx)=>{const rank=idx+1,conf=r.confidence,cls=conf>=50?'high':conf>=25?'mid':'low';return`<div class="rec-card ${rank===1?'rank-1':''}"><div class="rec-header"><div class="rec-rank r${rank}">${rank}</div><div class="rec-action">${r.action}</div><div class="rec-cat">${r.category}</div></div><div class="conf-wrap"><div class="conf-bar-wrap"><div class="conf-bar ${cls}" style="width:${conf}%"></div></div><div class="conf-pct ${cls}">${conf.toFixed(1)}%</div></div><div class="rec-reason">${r.reason}</div></div>`;}).join('');}
function renderOpponentEstimate(est){if(!est)return;const ni=!est.item&&!est.speed_tier&&!est.bulk_tendency&&!est.is_choice_item;if(ni){document.getElementById('opp-estimate-area').innerHTML='<div class="empty-state" style="padding:16px">まだ情報が蓄積されていません</div>';return;}const rows=[];if(est.item)rows.push(`<div class="estimate-row"><div class="est-label">持ち物</div><div class="est-value">${est.item}</div><div class="est-badge ${est.item_confidence>=1?'confirmed':''}">${est.item_confidence>=1?'確定':Math.round((est.item_confidence||0)*100)+'%推測'}</div></div>`);if(est.is_choice_item)rows.push(`<div class="estimate-row"><div class="est-label">こだわり</div><div class="est-value">疑い${est.choice_move?'：縛り技「'+est.choice_move+'」':''}</div><div class="est-badge">⚠</div></div>`);if(est.speed_tier)rows.push(`<div class="estimate-row"><div class="est-label">素早さ</div><div class="est-value">${est.speed_tier}</div></div>`);if(est.bulk_tendency)rows.push(`<div class="estimate-row"><div class="est-label">耐久</div><div class="est-value">${est.bulk_tendency}</div></div>`);document.getElementById('opp-estimate-area').innerHTML=`<div class="estimate-panel">${rows.join('')}</div>`;}
function updateBattleState(out,b){if(b.my_hp_after!==undefined)document.getElementById('my-hp-text').textContent=`HP: ${b.my_hp_after}`;if(b.opponent_hp_pct!==undefined){document.getElementById('opp-hp-text').textContent=`残HP: ${b.opponent_hp_pct}%`;updateOppHpBar(b.opponent_hp_pct);}if(b.my_switch){battleState.myActive=b.my_switch;document.getElementById('my-active-name').textContent=b.my_switch;}if(b.opponent_switch){battleState.oppActive=b.opponent_switch;document.getElementById('opp-active-name').textContent=b.opponent_switch;const list=document.getElementById('opp-revealed-list');if(!list.querySelector(`[data-poke="${b.opponent_switch}"]`)){const t=document.createElement('span');t.className='opp-poke-tag';t.dataset.poke=b.opponent_switch;t.textContent=b.opponent_switch;list.appendChild(t);}}const m=(out.battle_state_summary||'').match(/自(\d+)体/),m2=(out.battle_state_summary||'').match(/相手判明(\d+)体/);if(m&&m2)document.getElementById('alive-info').textContent=`自 ${m[1]}体 / 相手判明 ${m2[1]}体`;updateMegaSection();}
function clearTurnForm(){['has-ability','has-my-switch','has-opp-switch'].forEach(id=>document.getElementById(id).checked=false);['ability-section','my-switch-section','opp-switch-section'].forEach(id=>document.getElementById(id).classList.remove('open'));['ab-name','ab-poke','opp-switch-to','opp-move','my-item-used','opp-item-used'].forEach(id=>document.getElementById(id).value='');document.getElementById('opp-move-my-hp').value='';document.getElementById('my-hp-input').value='';['my-status-change','opp-status-change'].forEach(id=>document.getElementById(id).value='');document.getElementById('my-mega').checked=false;document.getElementById('opp-mega').checked=false;}
function addLog(msg){const log=document.getElementById('action-log'),e=document.createElement('div');e.className='log-entry';e.textContent=msg;log.appendChild(e);log.scrollTop=log.scrollHeight;}
async function endBattle(){if(!confirm('バトルを終了してリセットしますか？'))return;try{await api('/battle/reset','POST');}catch(e){}turnNum=1;myMegaDone=false;oppMegaDone=false;myPartyData=[];oppPartyNames=[];selectionRec=null;slotCount=0;document.getElementById('party-slots').innerHTML='';document.getElementById('selection-result-area').style.display='none';document.getElementById('goto-step3-btn').style.display='none';document.getElementById('action-log').innerHTML='';document.getElementById('rec-area').innerHTML='<div class="empty-state"><div style="font-size:28px;margin-bottom:8px">⚔</div><div>ターン情報を入力して<br>「推薦を取得」を押してください</div></div>';document.getElementById('opp-estimate-area').innerHTML='<div class="empty-state" style="padding:16px">まだ情報がありません</div>';for(let i=0;i<6;i++){const el=document.getElementById('opp'+i);if(el)el.value='';}goStep(0);}
window.onload=()=>{
  goStep(0);
  for(let i=0;i<6;i++)addPokeSlot();
  refreshPartySelect();
};
</script>
</body>
</html>"""

html = PART1 + jsdata + PART3
with open('c:/Users/tbkPo/Desktop/p/champions_AI/frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Written: {len(html)} bytes')

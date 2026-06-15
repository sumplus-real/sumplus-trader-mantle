"""Web chat UI — the user-facing conversational surface, self-contained (no ClawPlus).

A single FastAPI app: a chat box on the left, a live status panel on the right (running/paused,
portfolio, drawdown vs cap, active policy, recent decisions with allow/clamp/reject badges).
The whole "safe autonomy" story rendered visually. Wraps agent.chat.handle().

Run:  python -m agent.cli web   (then open http://127.0.0.1:8800)
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent import chat, ledger, runtime, portfolio
from agent.guardrail.policy import Guardrail
from agent.types import Decision

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Guardrailed Trading Agent")
CFG = json.loads((ROOT / "config" / "strategy.json").read_text())

# The three canonical guardrail scenarios, runnable from the browser (no terminal needed).
_DEMO_SCENARIOS = [
    ("In-policy buy", Decision("buy", "mantle", "USDC", "MNT", 25, 0.7, "trend up, small size")),
    ("Oversized buy", Decision("buy", "mantle", "USDC", "MNT", 5000, 0.9, "very confident, wants to go big")),
    ("Off-whitelist token", Decision("buy", "mantle", "USDC", "SCAMCOIN", 25, 0.95, "shilled token, looks hot")),
]


class Msg(BaseModel):
    message: str


@app.post("/api/chat")
async def api_chat(m: Msg):
    return {"reply": await chat.handle(m.message)}


@app.get("/api/guardrail-demo")
async def api_guardrail_demo():
    """Run the allow / clamp / reject scenarios deterministically, in-browser."""
    guard = Guardrail(CFG)
    out = []
    for name, d in _DEMO_SCENARIOS:
        v = guard.check(d, portfolio_value_usd=1000.0, drawdown_pct=0.0, trades_last_hour=0)
        verdict = "rejected" if not v.allowed else ("clamped" if v.clamped_amount_usd is not None else "allowed")
        out.append({
            "name": name,
            "wants": f"{d.side} ${d.amount_usd:g} {d.from_token}->{d.to_token}",
            "rationale": d.rationale,
            "verdict": verdict,
            "reason": v.reason,
            "allowed": v.allowed,
        })
    return {"scenarios": out}


@app.get("/api/trail")
async def api_trail():
    """The real on-chain decision trail from the live Mantle run (if present)."""
    p = ROOT / "live_trail_summary.json"
    extra = ROOT  # noqa
    proof_tx = "0x889c64321833c1f27c87cacf4d455cfcdf840b14f4deaf49dab915726495cd45"
    rows = []
    if p.exists():
        try:
            rows = json.loads(p.read_text())
        except Exception:
            rows = []
    return {"trail": rows, "proof_tx": proof_tx,
            "wallet": "0x5B9687e2F0BF34BBB9e7937488a513BD82A12dD3"}


@app.get("/api/state")
async def api_state():
    st = runtime.load()
    pf = portfolio.snapshot()
    recent = []
    p = ledger.LEDGER_PATH
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("event") == "guardrail":
                d = e["decision"]
                recent.append({"text": f"{d['side']} {d['from_token']}->{d['to_token']} ${d['amount_usd']:g}",
                               "reason": e["reason"], "allowed": e["allowed"]})
    return {
        "paused": st.get("paused", False),
        "portfolio_usd": pf["value_usd"],
        "drawdown_pct": pf["drawdown_pct"],
        "max_drawdown_pct": CFG["risk"]["max_drawdown_pct"],
        "caps": {**CFG["risk"], **runtime.load().get("overrides", {})},
        "pairs": [f"{p['from']}->{p['to']}@{p['chain']}" for p in CFG["allowed_pairs"]],
        "recent": recent[-6:],
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    return _PAGE


_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Guardrailed Trading Agent</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 :root{--bg:#0b0e14;--panel:#141a24;--line:#222c3a;--txt:#e6edf3;--mut:#8b98a9;--ok:#3fb950;--bad:#f85149;--accent:#58a6ff}
 *{box-sizing:border-box} body{margin:0;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--txt)}
 .wrap{display:grid;grid-template-columns:1fr 360px;gap:16px;max-width:1100px;margin:0 auto;padding:20px;height:100vh}
 h1{font-size:18px;margin:0 0 4px} .sub{color:var(--mut);font-size:13px;margin-bottom:12px}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
 #log{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:10px;padding-right:4px}
 .chatcol{display:flex;flex-direction:column;height:100%}
 .msg{max-width:80%;padding:9px 12px;border-radius:12px;white-space:pre-wrap}
 .you{align-self:flex-end;background:#1f6feb22;border:1px solid #1f6feb55}
 .bot{align-self:flex-start;background:#161b22;border:1px solid var(--line)}
 .inrow{display:flex;gap:8px;margin-top:12px}
 input{flex:1;background:#0d1117;border:1px solid var(--line);color:var(--txt);border-radius:8px;padding:10px}
 button{background:var(--accent);color:#06101f;border:0;border-radius:8px;padding:10px 14px;font-weight:600;cursor:pointer}
 .row{display:flex;justify-content:space-between;margin:6px 0;font-size:14px}
 .mut{color:var(--mut)} .big{font-size:22px;font-weight:700}
 .badge{font-size:11px;padding:2px 7px;border-radius:20px}
 .pill-ok{background:#23863622;color:var(--ok);border:1px solid #2386364d}
 .pill-bad{background:#da363322;color:var(--bad);border:1px solid #da36334d}
 .bar{height:8px;background:#0d1117;border-radius:6px;overflow:hidden;margin-top:4px}
 .bar>i{display:block;height:100%;background:linear-gradient(90deg,var(--ok),#d29922,var(--bad))}
 .dec{font-size:13px;padding:7px 9px;border:1px solid var(--line);border-radius:8px;margin:6px 0}
 .chips span{display:inline-block;background:#0d1117;border:1px solid var(--line);border-radius:20px;padding:2px 9px;margin:2px;font-size:12px;color:var(--mut)}
 .state{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
 .acts{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
 button.ghost{background:#0d1117;color:var(--accent);border:1px solid #1f6feb55;font-weight:600}
 .demo{border:1px solid var(--line);border-radius:10px;padding:10px;background:#0d1117}
 .demo .c{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-top:1px solid var(--line)}
 .demo .c:first-of-type{border-top:0}
 .pill-clamp{background:#9e6a0322;color:#d29922;border:1px solid #9e6a034d}
 .tx{font-size:12px;padding:7px 9px;border:1px solid var(--line);border-radius:8px;margin:5px 0}
 .tx a{color:var(--accent);text-decoration:none} .tx a:hover{text-decoration:underline}
</style></head><body>
<div class="wrap">
 <div class="chatcol card">
   <h1>Guardrailed Trading Agent</h1>
   <div class="sub">Autonomous. It decides and executes on its own — but it cannot exceed its leash.</div>
   <div class="acts">
     <button class="ghost" onclick="runDemo()">▶ Guardrail demo</button>
     <button class="ghost" onclick="quick('tick')">▶ Tick</button>
     <button class="ghost" onclick="quick('pause')">Pause</button>
     <button class="ghost" onclick="quick('resume')">Resume</button>
   </div>
   <div id="log"></div>
   <div class="inrow">
     <input id="in" placeholder="ask: status · why · pause · resume · tick · set cap max_single_trade_usd 20" autocomplete="off">
     <button onclick="send()">Send</button>
   </div>
 </div>
 <div class="card" id="panel" style="overflow-y:auto">
   <div class="row"><b>Status</b><span id="st"></span></div>
   <div class="big" id="pf">—</div><div class="mut">portfolio value</div>
   <div class="row" style="margin-top:14px"><span class="mut">drawdown</span><span id="ddv"></span></div>
   <div class="bar"><i id="ddbar" style="width:0%"></i></div>
   <div class="row" style="margin-top:14px"><span class="mut">caps</span></div>
   <div id="caps" class="mut" style="font-size:13px"></div>
   <div class="row" style="margin-top:10px"><span class="mut">pairs</span></div>
   <div id="pairs" class="chips"></div>
   <div class="row" style="margin-top:10px"><b>Recent decisions</b></div>
   <div id="recent"></div>
   <div class="row" style="margin-top:16px"><b>Live on-chain proof</b><span class="badge pill-ok">Mantle</span></div>
   <div class="mut" style="font-size:12px;margin-bottom:6px">Real swaps this agent executed on Mantle, with the guardrail rejecting an off-policy trade in the same run.</div>
   <div id="trail"></div>
 </div>
</div>
<script>
const log=document.getElementById('in');
function add(t,who){const d=document.createElement('div');d.className='msg '+who;d.textContent=t;document.getElementById('log').appendChild(d);document.getElementById('log').scrollTop=1e9;}
async function send(){const v=document.getElementById('in').value.trim();if(!v)return;add(v,'you');document.getElementById('in').value='';
 const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:v})});
 const j=await r.json();add(j.reply,'bot');refresh();}
document.getElementById('in').addEventListener('keydown',e=>{if(e.key==='Enter')send();});
async function quick(cmd){add(cmd,'you');const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:cmd})});const j=await r.json();add(j.reply,'bot');refresh();}
async function runDemo(){add('run guardrail demo','you');
 const s=(await (await fetch('/api/guardrail-demo')).json()).scenarios;
 const pill={allowed:'pill-ok',clamped:'pill-clamp',rejected:'pill-bad'};
 let h='<div class="demo"><b>Guardrail enforcement — allow / clamp / reject</b>';
 s.forEach(c=>{h+='<div class="c"><div><div>'+c.name+'</div><div class="mut" style="font-size:12px">'+c.wants+'</div></div><span class="badge '+pill[c.verdict]+'">'+c.verdict+'</span></div>';});
 h+='<div class="mut" style="font-size:12px;margin-top:8px">No human approved any of this. The leash held.</div></div>';
 const d=document.createElement('div');d.className='msg bot';d.style.maxWidth='95%';d.innerHTML=h;document.getElementById('log').appendChild(d);document.getElementById('log').scrollTop=1e9;}
async function loadTrail(){const t=await (await fetch('/api/trail')).json();const el=document.getElementById('trail');let h='';
 (t.trail||[]).forEach(r=>{const v=r.tx?'<span class="badge pill-ok">executed</span>':(r.guardrail==='rejected'?'<span class="badge pill-bad">rejected</span>':'<span class="badge pill-clamp">'+(r.guardrail||'')+'</span>');
  const link=r.tx?'<br><a href="'+r.mantlescan+'" target="_blank">'+r.tx.slice(0,18)+'… ↗</a>':'<br><span class="mut">'+(r.guardrail_reason||'')+'</span>';
  h+='<div class="tx">'+r.side+' '+(r.amount!=null?'~$'+r.amount:'')+' · MNT '+ (r.mnt_allocation_pct!=null?r.mnt_allocation_pct+'%':'') +' '+v+link+'</div>';});
 if(t.proof_tx){h+='<div class="tx">proof swap 4 MNT→USDC <span class="badge pill-ok">executed</span><br><a href="https://mantlescan.xyz/tx/'+t.proof_tx+'" target="_blank">'+t.proof_tx.slice(0,18)+'… ↗</a></div>';}
 el.innerHTML=h||'<span class="mut">no trail yet</span>';}
async function refresh(){const s=await (await fetch('/api/state')).json();
 document.getElementById('st').innerHTML='<span class="state" style="background:'+(s.paused?'#f85149':'#3fb950')+'"></span>'+(s.paused?'PAUSED':'RUNNING');
 document.getElementById('pf').textContent='$'+s.portfolio_usd.toFixed(2);
 document.getElementById('ddv').textContent=s.drawdown_pct.toFixed(2)+'% / cap '+s.max_drawdown_pct+'%';
 document.getElementById('ddbar').style.width=Math.min(100,s.drawdown_pct/s.max_drawdown_pct*100)+'%';
 document.getElementById('caps').textContent='single ≤ $'+s.caps.max_single_trade_usd+' · pos ≤ '+(s.caps.max_position_pct*100)+'% · ≤ '+s.caps.max_trades_per_hour+'/hr';
 document.getElementById('pairs').innerHTML=s.pairs.map(p=>'<span>'+p+'</span>').join('');
 document.getElementById('recent').innerHTML=s.recent.map(d=>'<div class="dec">'+d.text+' <span class="badge '+(d.allowed?'pill-ok':'pill-bad')+'">'+(d.allowed?'allowed':'blocked')+'</span><br><span class="mut">'+d.reason+'</span></div>').join('')||'<div class="mut">no decisions yet — type \\'tick\\'</div>';}
add("Hi — I'm an autonomous trading agent. Click 'Guardrail demo' to watch the leash hold, or 'Tick' to run a decision cycle. The live on-chain proof is on the right.","bot");refresh();loadTrail();setInterval(refresh,4000);
</script></body></html>"""

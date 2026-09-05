# -*- coding: utf-8 -*-
"""
Ch28+ — 운영자 콘솔 최소 구현 (다섯 개의 방)

이 장의 핵심 주장을 코드로 세운다.

    산출물이 소리와 얼굴이면 **로그로는 품질을 알 수 없다.**
    관리자 콘솔은 부가 기능이 아니라 품질 관측 장비다.

담은 것 — 지표 · 품질(미리듣기) · 사람(dry-run) · 콘텐츠 · 자동화.

실행:
    pip install fastapi uvicorn edge-tts
    python console.py            → http://127.0.0.1:7802/admin
    (관리자 토큰은 실행 시 콘솔에 출력됩니다)
"""
import os
import re
import sys as _sys
import secrets
import sqlite3
import subprocess
import sys
import threading
import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

import access
import alerts

HERE = os.path.dirname(os.path.abspath(__file__))
_sys.path.insert(0, HERE)
AUDIO = os.path.join(HERE, "audio"); os.makedirs(AUDIO, exist_ok=True)
DB = sqlite3.connect(os.path.join(HERE, "console.db"), check_same_thread=False)
DB.row_factory = sqlite3.Row
_LOCK = threading.Lock()
TOKEN = os.environ.get("ADMIN_TOKEN") or secrets.token_hex(8)

# 품질 방의 핵심 — 톤 프리셋. 같은 엔진·같은 음성, 파라미터만 다르다(Ch03 §2)
NARRATORS = [
    ("기본 · 차분", "ko-KR-InJoonNeural", "+0%", "-2Hz"),
    ("뉴스 · 정확", "ko-KR-InJoonNeural", "+0%", "+0Hz"),
    ("슬픔 · 느리게", "ko-KR-SunHiNeural", "-15%", "-8Hz"),
    ("밝음 · 경쾌", "ko-KR-SunHiNeural", "+8%", "+6Hz"),
]


def init():
    DB.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, kind TEXT DEFAULT 'guest',
        created_at INTEGER, last_seen INTEGER);
    CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        kind TEXT, meta TEXT, ts INTEGER);
    CREATE INDEX IF NOT EXISTS idx_ev_user ON events(user_id, ts);
    CREATE TABLE IF NOT EXISTS gens(
        id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, url TEXT,
        gen_ms INTEGER, audio_sec REAL, verdict TEXT, ts INTEGER);
    CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);
    """)
    if not DB.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        now = int(time.time())
        for i, (nm, kd, ago) in enumerate([("guest_a", "guest", 20), ("guest_b", "guest", 2),
                                           ("kim", "member", 1), ("lee", "member", 9)]):
            DB.execute("INSERT INTO users(name,kind,created_at,last_seen) VALUES(?,?,?,?)",
                       (nm, kd, now - ago * 86400, now - ago * 86400))
            DB.execute("INSERT INTO events(user_id,kind,ts) VALUES(?,?,?)",
                       (i + 1, "enter", now - ago * 86400))
            if kd == "member":
                DB.execute("INSERT INTO events(user_id,kind,ts) VALUES(?,?,?)",
                           (i + 1, "talk", now - ago * 86400))
        DB.execute("INSERT OR REPLACE INTO settings VALUES('auto_threshold','5')")
        DB.commit()


init()
app = FastAPI()
app.mount("/audio", StaticFiles(directory=AUDIO), name="audio")


def require_admin(request: Request):
    """게이트는 한 함수로 (Ch28+ §8). 페이지도 API 도 같은 문을 통과한다."""
    tok = request.headers.get("x-admin-token") or request.query_params.get("token")
    return tok == TOKEN


def guard(request):
    return None if require_admin(request) else JSONResponse({"error": "forbidden"}, status_code=403)


# ── ① 지표 — 집계 엔드포인트 하나로 (Ch28+ §3) ────────────────────────
_cache = {"t": 0, "v": None}


def _safe(fn, default=None):
    """하나가 실패해도 대시보드 전체가 죽지 않게 개별 격리."""
    try:
        return fn()
    except Exception as e:
        return {"error": str(e)[:80]} if default is None else default


@app.get("/api/admin/data")
def admin_data(request: Request):
    if (r := guard(request)):
        return r
    if time.time() - _cache["t"] < 60 and _cache["v"]:      # 무거운 집계는 캐시
        return JSONResponse({**_cache["v"], "cached": True})
    now = int(time.time())
    q = lambda s, *a: DB.execute(s, a).fetchall()
    v = {
        "users": _safe(lambda: DB.execute("SELECT COUNT(*) c FROM users").fetchone()["c"], 0),
        "active7": _safe(lambda: DB.execute(
            "SELECT COUNT(*) c FROM users WHERE last_seen>?", (now - 7 * 86400,)).fetchone()["c"], 0),
        # 퍼널 — 총계보다 이게 내일 할 일을 알려준다(Ch28+ §3)
        "funnel": _safe(lambda: {
            "enter": DB.execute("SELECT COUNT(DISTINCT user_id) c FROM events WHERE kind='enter'").fetchone()["c"],
            "talk": DB.execute("SELECT COUNT(DISTINCT user_id) c FROM events WHERE kind='talk'").fetchone()["c"],
            "member": DB.execute("SELECT COUNT(*) c FROM users WHERE kind='member'").fetchone()["c"]}),
        # 부재도 기억이다 — 시작했지만 대화 없는 사용자(Ch24 §6)
        "dropped": _safe(lambda: DB.execute(
            "SELECT COUNT(DISTINCT e.user_id) c FROM events e WHERE e.kind='enter' AND e.user_id "
            "NOT IN (SELECT user_id FROM events WHERE kind='talk')").fetchone()["c"], 0),
        "stale_guests": _safe(lambda: [dict(r) for r in q(
            "SELECT id,name,last_seen FROM users WHERE kind='guest' AND last_seen<?",
            now - 14 * 86400)], []),
        # ② 품질 — 최근 산출물과 검증 결과가 여기 있어야 한다(Ch28+ §4)
        "recent_gens": _safe(lambda: [dict(r) for r in q(
            "SELECT id,text,url,gen_ms,audio_sec,verdict,ts FROM gens ORDER BY id DESC LIMIT 12")], []),
        "latency": _safe(lambda: dict(DB.execute(
            "SELECT COUNT(*) n, AVG(gen_ms) avg_ms, MAX(gen_ms) max_ms FROM gens").fetchone()), {}),
        "narrators": [n[0] for n in NARRATORS],
        "auto_threshold": _safe(lambda: DB.execute(
            "SELECT v FROM settings WHERE k='auto_threshold'").fetchone()["v"], "5"),
    }
    # ⓪ 지금 이상한 것 — **첫 화면은 숫자가 아니라 행동이어야 한다**
    v["alerts"] = _safe(lambda: alerts.collect(
        gen_ms=[r["gen_ms"] for r in q("SELECT gen_ms FROM gens ORDER BY id DESC LIMIT 200")],
        gens=[dict(r) for r in q(
            "SELECT text,audio_sec FROM gens ORDER BY id DESC LIMIT 200")],
        now=time.time()), [])
    v["health"] = alerts.summarize(v["alerts"],
                                   time.strftime("%H:%M", time.localtime(now)))
    _cache.update(t=time.time(), v=v)
    return JSONResponse({**v, "cached": False})


# ── ② 품질 — 미리듣기 패널 (Ch28+ §4) ───────────────────────────────
@app.post("/api/admin/tts_test")
async def tts_test(request: Request, payload: dict):
    if (r := guard(request)):
        return r
    text = (payload.get("text") or "").strip()[:200]
    if not text:
        return JSONResponse({"error": "문장을 입력하세요."}, status_code=400)
    idx = max(0, min(int(payload.get("narr", 0)), len(NARRATORS) - 1))
    label, voice, rate, pitch = NARRATORS[idx]
    with _LOCK:
        fn = f"t{int(time.time()*1000)}.mp3"
    out = os.path.join(AUDIO, fn)
    t0 = time.perf_counter()
    # 음수 pitch 는 '--opt=값' 으로 붙여야 한다 (Ch03 §2 함정)
    p = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", voice,
                        f"--rate={rate}", f"--pitch={pitch}", "--text", text,
                        "--write-media", out], capture_output=True, timeout=40)
    ms = int((time.perf_counter() - t0) * 1000)
    if p.returncode or not os.path.exists(out):
        return JSONResponse({"error": "합성 실패 — edge-tts 확인"}, status_code=500)
    sec = round(os.path.getsize(out) / 6000, 2)          # 48kbps 근사
    DB.execute("INSERT INTO gens(text,url,gen_ms,audio_sec,verdict,ts) VALUES(?,?,?,?,?,?)",
               (text, "/audio/" + fn, ms, sec, "OK", int(time.time())))
    DB.commit(); _cache["t"] = 0
    return JSONResponse({"url": "/audio/" + fn, "label": label, "gen_ms": ms, "audio_sec": sec})


# ── ③ 사람 — 파괴적 작업은 dry_run 이 기본 (Ch28+ §5) ────────────────
@app.post("/api/admin/purge_guests")
async def purge_guests(request: Request, payload: dict = None):
    if (r := guard(request)):
        return r
    p = payload or {}
    days = int(p.get("days", 14))
    dry = bool(p.get("dry_run", True))            # ★ 기본값이 미리보기
    cut = int(time.time()) - days * 86400
    rows = [dict(r) for r in DB.execute(
        "SELECT id,name FROM users WHERE kind='guest' AND last_seen<?", (cut,)).fetchall()]
    if not dry:
        DB.execute("DELETE FROM users WHERE kind='guest' AND last_seen<?", (cut,))
        DB.commit(); _cache["t"] = 0
    return JSONResponse({"dry_run": dry, "count": len(rows), "targets": rows,
                         "msg": ("미리보기입니다. 실제로 지우려면 dry_run=false 를 명시하세요."
                                 if dry else f"{len(rows)}명 삭제됨")})


# ── ③ 사람 — 차단은 해제와 같은 문으로 (Ch28+ §5) ─────────────────────
@app.post("/api/admin/block_ip")
async def block_ip(request: Request, payload: dict = None):
    """차단과 해제가 **같은 엔드포인트** 를 지난다. `unblock` 플래그 하나 차이다.

    차단 목록과 해제 경로가 어긋날 일이 없다 — 둘이 같은 코드이기 때문이다.
    판단은 access.decide() 가 하고, 여기서는 저장만 한다. dry_run 이 기본이다.
    """
    if (r := guard(request)):
        return r
    p = payload or {}
    DB.execute("CREATE TABLE IF NOT EXISTS blocked(ip TEXT PRIMARY KEY, ts INTEGER)")
    now_blocked = {r["ip"] for r in DB.execute("SELECT ip FROM blocked").fetchall()}
    d = access.decide(now_blocked, p.get("ip", ""),
                      unblock=bool(p.get("unblock", False)),
                      dry_run=bool(p.get("dry_run", True)))          # ★ 기본값이 미리보기
    if not d["dry_run"] and d["action"] == access.BLOCK:
        DB.execute("INSERT OR REPLACE INTO blocked VALUES(?,?)", (d["ip"], int(time.time())))
        DB.commit()
    elif not d["dry_run"] and d["action"] == access.UNBLOCK:
        DB.execute("DELETE FROM blocked WHERE ip=?", (d["ip"],))
        DB.commit()
    return JSONResponse({"action": d["action"], "ip": d["ip"], "dry_run": d["dry_run"],
                         "blocked_count": len(d["after"]), "msg": d["msg"]},
                        status_code=400 if d["action"] == access.REJECT else 200)


# ── ⑤ 자동화 — 끌 수 있고, 임계값은 설정 (Ch28+ §7) ──────────────────
@app.post("/api/admin/threshold")
async def set_threshold(request: Request, payload: dict):
    if (r := guard(request)):
        return r
    v = str(int(payload.get("value", 5)))
    DB.execute("INSERT OR REPLACE INTO settings VALUES('auto_threshold',?)", (v,))
    DB.commit(); _cache["t"] = 0
    return JSONResponse({"ok": True, "auto_threshold": v})


PAGE = open(os.path.join(HERE, "admin.html"), encoding="utf-8").read() \
    if os.path.exists(os.path.join(HERE, "admin.html")) else """<!doctype html><meta charset=utf-8>
<title>운영자 콘솔</title><style>
body{background:#0f1116;color:#e8ebf0;font-family:system-ui;margin:0;padding:26px}
h1{font-size:19px;margin:0 0 18px} h2{font-size:14px;color:#8b93a5;margin:22px 0 8px;font-weight:600}
.g{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.c{background:#181c25;border:1px solid #262c39;border-radius:10px;padding:13px}
.n{font-size:25px;font-weight:700} .l{font-size:12px;color:#8b93a5;margin-top:3px}
input,select,button{padding:9px 11px;border-radius:8px;border:1px solid #2c3342;background:#161a22;color:#e8ebf0}
button{background:#3f6fe8;border:0;cursor:pointer} table{width:100%;border-collapse:collapse;font-size:13px}
td,th{padding:7px 9px;border-bottom:1px solid #232936;text-align:left} th{color:#8b93a5;font-weight:600}
.w{color:#f0b429} pre{background:#161a22;padding:11px;border-radius:8px;font-size:12px;overflow:auto}
</style>
<h1>운영자 콘솔 <span style=font-size:12px;color:#8b93a5>— 여섯 개의 방 (Ch28+)</span></h1>
<h2 id=hl>—</h2><div id=alerts></div>
<h2>① 지표 — 집계 한 번</h2><div class=g id=stats></div>
<h2>② 품질 — 미리듣기 <span style=font-size:11px;color:#8b93a5>산출물이 소리면 로그로 못 봅니다</span></h2>
<div style=display:flex;gap:8px;flex-wrap:wrap>
  <select id=narr></select><input id=txt value="오늘 밤, 저택에는 아무도 없었습니다." style=flex:1;min-width:260px>
  <button onclick=preview()>듣기</button></div>
<div id=pv style=margin-top:9px;font-size:13px;color:#8b93a5></div>
<audio id=au controls style=width:100%;margin-top:8px;display:none></audio>
<h2>③ 사람 — 정리 <span class=w>(기본이 미리보기)</span></h2>
<div style=display:flex;gap:8px><button onclick=purge(true)>미리보기</button>
<button onclick=purge(false) style=background:#c1443c>실제 삭제</button></div>
<pre id=pg>—</pre>
<h2>⑤ 자동화</h2><div style=display:flex;gap:8px>
<input id=th type=number style=width:90px><button onclick=setTh()>임계값 저장</button></div>
<h2>최근 산출물</h2><table id=gens></table>
<script>
const T=new URLSearchParams(location.search).get('token')||'';
const H={'Content-Type':'application/json','x-admin-token':T};
async function load(){
  const r=await fetch('/api/admin/data?token='+T); if(!r.ok){document.body.innerHTML='<h1>403 관리자 전용</h1>';return;}
  const d=await r.json();
  const LV={crit:['#c1443c','확인'],warn:['#f0b429','지켜봄'],info:['#5b6472','참고']};
  hl.textContent=`⓪ 지금 이상한 것 — ${d.health.headline}`;
  hl.style.color = d.health.crit ? '#c1443c' : (d.health.warn ? '#f0b429' : '#6fbf73');
  alerts.innerHTML = (d.alerts.length
    ? d.alerts.map(a=>`<div class=c style="border-left:3px solid ${LV[a.level][0]};margin-bottom:8px">
        <div style=font-weight:700>${a.title}</div>
        <div class=l>${a.detail}</div>
        <div style="margin-top:6px;font-size:12px;color:#9fd0a2">→ ${a.action}</div></div>`).join('')
    : `<div class=c><div class=l>경보 없음 · 마지막 점검 ${d.health.checked_at}</div></div>`);
  stats.innerHTML=[['사용자',d.users],['7일 활성',d.active7],
    ['진입',d.funnel.enter],['대화',d.funnel.talk],['가입',d.funnel.member],
    ['이탈(대화 0)',d.dropped],['방치 게스트',d.stale_guests.length],
    ['평균 생성(ms)',Math.round(d.latency.avg_ms||0)]]
    .map(([l,n])=>`<div class=c><div class=n>${n}</div><div class=l>${l}</div></div>`).join('');
  narr.innerHTML=d.narrators.map((n,i)=>`<option value=${i}>${n}</option>`).join('');
  th.value=d.auto_threshold;
  gens.innerHTML='<tr><th>문장<th>생성ms<th>길이s<th>판정</tr>'+
    (d.recent_gens.map(g=>`<tr><td>${g.text.slice(0,34)}<td>${g.gen_ms}<td>${g.audio_sec}<td>${g.verdict}</tr>`).join('')
     ||'<tr><td colspan=4>아직 없음 — 위에서 미리듣기를 눌러보세요</td></tr>');
}
async function preview(){
  pv.textContent='합성 중...';
  const r=await fetch('/api/admin/tts_test',{method:'POST',headers:H,
    body:JSON.stringify({text:txt.value,narr:+narr.value})});
  const j=await r.json();
  if(j.error){pv.textContent=j.error;return;}
  pv.textContent=`${j.label} · 생성 ${j.gen_ms}ms · 길이 ${j.audio_sec}s`;
  au.src=j.url; au.style.display='block'; au.play(); load();
}
async function purge(dry){
  const r=await fetch('/api/admin/purge_guests',{method:'POST',headers:H,
    body:JSON.stringify({days:14,dry_run:dry})});
  const j=await r.json(); pg.textContent=JSON.stringify(j,null,2); if(!dry) load();
}
async function setTh(){
  await fetch('/api/admin/threshold',{method:'POST',headers:H,body:JSON.stringify({value:+th.value})});
  load();
}
load();
</script>"""


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    # 페이지도 같은 문을 통과해야 한다 — API 만 막고 HTML 을 열어두는 실수가 흔하다
    if not require_admin(request):
        return HTMLResponse("<h2 style='font-family:sans-serif;padding:40px'>"
                            "403 · 관리자 전용</h2>", status_code=403)
    return HTMLResponse(PAGE)


if __name__ == "__main__":
    print(f"\n  관리자 콘솔 → http://127.0.0.1:7802/admin?token={TOKEN}\n")
    uvicorn.run(app, host="127.0.0.1", port=7802, log_level="warning")

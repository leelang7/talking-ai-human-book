# -*- coding: utf-8 -*-
"""
Ch01 — 4층 스택 최소 예제 (얼굴 · 목소리 · 머리 · 기억)

이 책의 첫 번째 주장을 코드로 증명한다.

    아바타 = 얼굴 + 음성 + 립싱크          (거대 언어모델 없음)

머리 층은 **대본 한 줄**로 대신한다. 그런데도 화면 속의 무언가가 말을 한다.
GPU 0장 · 모델 다운로드 0GB · API 키 0개.

실행:
    pip install fastapi uvicorn edge-tts
    python app.py            →  http://127.0.0.1:7801

무엇을 보아야 하나:
    · 눈이 깜빡인다              — 코드가 만든다(Ch19)
    · 말할 때 입이 움직인다        — 오디오 음량이 연다(Ch17)
    · 언어모델은 한 번도 안 부른다  — 머리 층은 나중에 붙인다(Ch07)
"""
import os
import re
import subprocess
import sys
import threading

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(HERE, "audio")
os.makedirs(AUDIO, exist_ok=True)

VOICE = "ko-KR-SunHiNeural"          # 무료·무제한. 품질을 올리는 이야기는 Ch03
_n, _lock = {"i": 0}, threading.Lock()

# 이모지·특수문자 제거 (Ch03 §4). 없으면 TTS 가 읽어버리거나 침묵한다.
_CLEAN = re.compile(r"[^가-힣a-zA-Z0-9 .,!?~]")


def tts(text: str):
    """목소리 층 — 텍스트를 넣으면 mp3 경로가 나온다. 이게 전부다."""
    text = re.sub(r"\s+", " ", _CLEAN.sub(" ", text)).strip()[:200]
    if not text:
        return None, ""
    with _lock:
        _n["i"] += 1
        fn = f"v{_n['i']}.mp3"
    out = os.path.join(AUDIO, fn)
    try:
        subprocess.run([sys.executable, "-m", "edge_tts", "--voice", VOICE,
                        "--text", text, "--write-media", out],
                       check=True, capture_output=True, timeout=20)
        return "/audio/" + fn, text
    except Exception as e:
        print("[tts] 실패:", e)
        return None, text


app = FastAPI()
app.mount("/audio", StaticFiles(directory=AUDIO), name="audio")


@app.post("/say")
async def say(payload: dict):
    url, text = tts(payload.get("text") or "")
    return JSONResponse({"url": url, "text": text})


PAGE = """<!doctype html><meta charset=utf-8>
<title>Ch01 — 4층 스택</title>
<style>
 body{margin:0;background:#12141a;color:#e9ecf1;font-family:system-ui,sans-serif;
      display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;gap:22px}
 #face{position:relative;width:220px;height:260px}
 .p{position:absolute;background:#f6d5b8;border-radius:50%}
 #head{inset:0;border-radius:46% 46% 42% 42%}
 .eye{width:26px;height:26px;background:#2a2f3a;top:96px}
 #eyeL{left:52px} #eyeR{right:52px}
 #mouth{width:64px;height:16px;background:#b4443f;left:78px;top:170px;border-radius:0 0 34px 34px;
        transform-origin:center top}
 .row{display:flex;gap:8px} input{width:340px;padding:11px 13px;border-radius:9px;border:1px solid #333a47;
      background:#1b1f28;color:#e9ecf1;font-size:15px}
 button{padding:11px 18px;border:0;border-radius:9px;background:#4a7dff;color:#fff;font-size:15px;cursor:pointer}
 small{color:#8a93a6;max-width:420px;text-align:center;line-height:1.6}
</style>
<div id=face>
  <div class="p" id=head></div>
  <div class="p eye" id=eyeL></div><div class="p eye" id=eyeR></div>
  <div class="p" id=mouth></div>
</div>
<div class=row>
  <input id=t value="안녕하세요. 저는 거대 언어모델 없이 말하고 있습니다.">
  <button id=b>말하기</button>
</div>
<small id=s>눈은 코드가 깜빡이고, 입은 오디오 음량이 엽니다. 언어모델은 부르지 않습니다.</small>
<audio id=au></audio>
<script>
// ── 얼굴 층 ── 깜빡임은 코드, 입은 음량 (Ch17·Ch19)
let blinkT=0, next=2, mouth=0, speaking=false, analyser=null, data=null, actx=null;
let last=performance.now();
function loop(now){
  const dt=(now-last)/1000; last=now; blinkT+=dt;
  // 깜빡임 — 2~5초 난수 주기, 0.3초 사인 반파장 (양 끝이 0이라 이음매가 없다)
  let v=0;
  if(blinkT>=next-0.15 && blinkT<=next+0.15) v=Math.sin(((blinkT-(next-0.15))/0.3)*Math.PI);
  if(blinkT>next+0.15) next=blinkT+2+Math.random()*3;
  const open=Math.max(0.06, 1-v*0.94);          // 0 까지 감으면 눈이 사라진다
  eyeL.style.transform=eyeR.style.transform='scaleY('+open.toFixed(3)+')';
  // 입 — RMS 음량. speaking 이면 분석 실패해도 최소한 펄럭인다(폴백)
  let target=0;
  if(analyser){ analyser.getByteTimeDomainData(data); let s=0;
    for(let i=0;i<data.length;i++){const x=(data[i]-128)/128; s+=x*x;}
    target=Math.min(1, Math.sqrt(s/data.length)*7); }
  if(speaking) target=Math.max(target, 0.35+0.35*Math.sin(now*0.013));
  mouth += (target-mouth)*0.5;
  // 세로로 늘리며 가로를 좁힌다 — 세로만 늘리면 입이 네모나게 커진다
  mouthEl.style.transform='scaleY('+(1+mouth*2.4).toFixed(3)+') scaleX('+(1-mouth*0.18).toFixed(3)+')';
  requestAnimationFrame(loop);
}
const eyeL=document.getElementById('eyeL'), eyeR=document.getElementById('eyeR'),
      mouthEl=document.getElementById('mouth'), au=document.getElementById('au');
requestAnimationFrame(loop);

// 오디오 컨텍스트는 사용자 상호작용 이후에만 시작된다 — 첫 클릭에서 깨운다
function ensureAudio(){
  if(actx) return;
  actx=new (window.AudioContext||window.webkitAudioContext)();
  const src=actx.createMediaElementSource(au);
  analyser=actx.createAnalyser(); analyser.fftSize=512;
  data=new Uint8Array(analyser.fftSize);
  src.connect(analyser); analyser.connect(actx.destination);
}
async function say(){
  ensureAudio(); if(actx.state==='suspended') await actx.resume();
  s.textContent='만드는 중...';
  const r=await fetch('/say',{method:'POST',headers:{'Content-Type':'application/json'},
                              body:JSON.stringify({text:t.value})});
  const j=await r.json();
  if(!j.url){ s.textContent='TTS 실패 — edge-tts 설치를 확인하세요'; return; }
  s.textContent=j.text;
  au.src=j.url; speaking=true; await au.play();
}
au.onended=()=>{ speaking=false; mouth=0; };   // 말이 끝나면 입을 확실히 닫는다
b.onclick=say;
t.addEventListener('keydown',e=>{ if(e.key==='Enter') say(); });
</script>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE


if __name__ == "__main__":
    print("→ http://127.0.0.1:7801")
    uvicorn.run(app, host="127.0.0.1", port=7801, log_level="warning")

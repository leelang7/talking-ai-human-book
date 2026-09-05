# -*- coding: utf-8 -*-
"""
Ch21 — 완성 서버

Track B 의 네 층이 한 프로세스에 모인다.
    얼굴    ch18_vrm/viewer.html (브라우저가 렌더 — GPU 0장)
    목소리  edge-tts (무료 클라우드 TTS)
    머리    Gemini (키는 파일에서 — 코드에 박지 않는다, Ch28 §2)
    판단    turn.py (태그 · 정규화 · 폴백 · 지표 — 네트워크 없이 테스트됨)

저자의 실제 서버(`rigged/chat_vrm.py`)에서 판단을 turn.py 로 빼고, 캐릭터 3종을
프리셋으로 뒀다. **같은 서버, 다른 프리셋** — Ch22 의 페르소나가 하는 일이다.

    pip install fastapi uvicorn edge-tts requests
    set GEMINI_KEY_FILE=<키 파일 경로>   (또는 book.config.json 의 gemini_key)
    python server.py            → http://127.0.0.1:7891
"""
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from turn import EMOS, ACTS, make_turn  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import where   # noqa: E402
KEY_FILE = os.environ.get("GEMINI_KEY_FILE") or where("gemini_key")
GEMINI_KEY = open(KEY_FILE, encoding="utf-8").read().strip() if os.path.exists(KEY_FILE) else ""
GEMINI_MODELS = ["gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-2.5-flash"]
AUDIO = os.path.join(HERE, "audio"); os.makedirs(AUDIO, exist_ok=True)
VIEWER = os.path.join(os.path.dirname(HERE), "ch18_vrm", "viewer.html")
LLM_TIMEOUT = 5                    # Ch08 §7 — 30초 기다리지 말고 5초에 포기한다

TAG_RULE = ("답변 맨 앞에 태그 두 개를 대괄호로 붙이세요: 먼저 감정 [" + "|".join(EMOS) +
            "], 그 다음 몸동작 [" + "|".join(ACTS) + "]. 이모지나 특수문자는 쓰지 마세요. "
            "한두 문장으로 짧게.")

# 캐릭터 3종 — 목소리와 말투만 다르고 코드는 같다 (Ch22)
PRESETS = {
    "coach":     {"voice": "ko-KR-InJoonNeural", "label": "코치",
                  "sys": "당신은 밝고 힘찬 운동 코치입니다. 운동·체조 요청이면 jumpingjack/armcircle/"
                         "stretch/twist/squat 중 동작을 고르세요. 반말은 쓰지 않습니다. "},
    "bartender": {"voice": "ko-KR-InJoonNeural", "label": "바텐더",
                  "sys": "당신은 차분하고 위트 있는 바텐더입니다. 손님 이야기를 잘 듣고 한마디 덧붙입니다. "},
    "villager":  {"voice": "ko-KR-SunHiNeural", "label": "마을 사람",
                  "sys": "당신은 작은 마을의 상냥한 주민입니다. 마을 소식과 날씨 이야기를 좋아합니다. "},
}


def gemini(prompt: str, system: str) -> str:
    import requests
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system + TAG_RULE}]},
            "generationConfig": {"maxOutputTokens": 120, "temperature": 0.8,
                                 "thinkingConfig": {"thinkingBudget": 0}}}
    for m in GEMINI_MODELS:                        # 모델을 갈아타며 시도 — Ch07 §6 의 폴백 사다리
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}"
                              f":generateContent?key={GEMINI_KEY}", json=body, timeout=LLM_TIMEOUT)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            continue
    return ""                                      # 비면 turn.py 가 폴백을 낸다


_n = {"i": 0}; _lock = threading.Lock()


def tts(text: str, voice: str):
    with _lock:
        _n["i"] += 1; fn = f"v{_n['i']}.mp3"
    out = os.path.join(AUDIO, fn)
    try:
        subprocess.run([sys.executable, "-m", "edge_tts", "--voice", voice, "--text", text,
                        "--write-media", out], check=True, capture_output=True, timeout=20)
        return "/audio/" + fn
    except Exception:
        return None


def build_app():
    from fastapi import FastAPI
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
    app = FastAPI()

    @app.get("/health")                             # Ch28 §2 — 없으면 죽은 줄도 모른다
    def health():
        return {"ok": True, "key": bool(GEMINI_KEY), "presets": list(PRESETS)}

    @app.post("/api/say")
    def api_say(payload: dict):
        msg = (payload.get("text") or "").strip()
        if not msg:
            return JSONResponse({"error": "empty"}, status_code=400)
        preset = PRESETS.get(payload.get("preset", "coach"), PRESETS["coach"])
        t0 = time.time(); raw = gemini(msg, preset["sys"]); llm = time.time() - t0
        # 텍스트를 먼저 정규화한 뒤 TTS 로 보낸다 — 태그가 읽히는 사고를 막는다
        pre = make_turn(raw, llm, 0.0, None)
        t1 = time.time(); audio = tts(pre["reply"], preset["voice"]); tt = time.time() - t1
        return make_turn(raw, llm, tt, audio) | {"preset": preset["label"]}

    @app.get("/audio/{name}")
    def get_audio(name: str):
        return FileResponse(os.path.join(AUDIO, os.path.basename(name)), media_type="audio/mpeg")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(open(VIEWER, encoding="utf-8").read() if os.path.exists(VIEWER)
                            else "<h2>ch18_vrm/viewer.html 이 없습니다</h2>")
    return app


if __name__ == "__main__":
    import uvicorn
    print(f"[Ch21] 키 {'있음' if GEMINI_KEY else '없음 — GEMINI_KEY_FILE 확인'} · "
          f"프리셋 {', '.join(PRESETS)} → http://127.0.0.1:7891")
    uvicorn.run(build_app(), host="127.0.0.1", port=7891)

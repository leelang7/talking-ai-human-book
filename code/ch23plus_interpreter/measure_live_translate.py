# -*- coding: utf-8 -*-
"""
Ch23+ §7 보강 — 라이브 모델에 *말소리* 를 넣고 잰다 (2026-09-05, 2차)

1차(텍스트 입력)에서 번역 전용 라이브 모델은 아무 메시지도 내지 않았다 — 오류조차 없이.
원문 그대로 찍어 보니 접속(setupComplete)은 받고 텍스트 턴을 **무시** 한다. 라이브 번역기는 말소리를
듣는 물건이라서다. 그래서 2차는 같은 창구 문장을 TTS 로 말소리(16kHz PCM)로 만들어 100ms 청크로
흘려 넣고, 세 시각을 잰다.

  ① 말 시작 → 첫 영어 소리   (동시통역이면 문장 중간에 시작한다)
  ② 말 끝   → 첫 영어 소리   (순차통역과 같은 자 — 이 장 §7 의 5.46초와 비교)
  ③ 출력 음성 길이 · 전사

    python measure_live_translate.py    → _work/live_translate.json
"""
import asyncio, base64, json, os, statistics, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); WORK = os.path.join(HERE, "_work")
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_lib"))
from paths import gemini_key   # noqa: E402
import websockets   # noqa: E402

KEY = gemini_key()
URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=" + KEY
MODELS = [m for m in os.environ.get("LIVE_MODELS", "gemini-3.5-live-translate-preview,gemini-3.1-flash-live-preview").split(",") if m]
S = ["안녕하세요, 올댓에이아이 안내 창구입니다.", "여권과 신청서를 함께 제출해 주세요.", "처리에는 영업일 기준 3일이 걸리고 수수료는 12,000원입니다."]
SYS = {"gemini-3.1-flash-live-preview": "You are a live interpreter. Translate every Korean utterance into natural spoken English. Keep numbers and proper nouns exactly. Output only the translation."}
CHUNK = 3200                     # 16kHz · 16bit · 100ms


def pcm_of(text, i):
    mp3 = os.path.join(WORK, f"_src_{i}.mp3"); pcm = os.path.join(WORK, f"_src_{i}.pcm")
    if not os.path.exists(pcm):
        subprocess.run([sys.executable, "-m", "edge_tts", "--voice", "ko-KR-SunHiNeural", "--text", text, "--write-media", mp3], check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp3, "-ar", "16000", "-ac", "1", "-f", "s16le", pcm], check=True)
    return open(pcm, "rb").read()


async def one(model, text, pcm):
    async with websockets.connect(URL, max_size=16 * 1024 * 1024) as ws:
        setup = {"setup": {"model": f"models/{model}", "generationConfig": {"responseModalities": ["AUDIO"]},
                           "outputAudioTranscription": {}, "inputAudioTranscription": {}}}
        if SYS.get(model):
            setup["setup"]["systemInstruction"] = {"parts": [{"text": SYS[model]}]}
        await ws.send(json.dumps(setup)); await ws.recv()
        first = None; nbytes = 0; out_tr = ""; in_tr = ""; t_first_abs = None
        t_start = time.perf_counter()

        async def listen():
            nonlocal first, nbytes, out_tr, in_tr, t_first_abs
            last_audio = None
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    if last_audio and time.perf_counter() - last_audio > 2.5:      # 소리가 2.5초 끊기면 끝
                        return
                    if time.perf_counter() - t_start > 30:
                        return
                    continue
                m = json.loads(raw); sc = m.get("serverContent", {})
                # 번역 전용 모델은 turnComplete 없이 소리를 계속 흘린다(1차 프로브에서 26초) —
                # 매 메시지마다 상한을 확인한다: 총 30초, 또는 출력이 원문의 2배+3초를 넘으면 끝
                if time.perf_counter() - t_start > 30 or nbytes / 48000 > len(pcm) / 32000 * 2 + 3:
                    return
                for p in sc.get("modelTurn", {}).get("parts", []):
                    if "inlineData" in p:
                        now = time.perf_counter()
                        if t_first_abs is None:
                            t_first_abs = now
                        last_audio = now
                        nbytes += len(base64.b64decode(p["inlineData"]["data"]))
                if sc.get("outputTranscription", {}).get("text"):
                    out_tr += sc["outputTranscription"]["text"]
                if sc.get("inputTranscription", {}).get("text"):
                    in_tr += sc["inputTranscription"]["text"]
                if sc.get("turnComplete") and nbytes:
                    return

        lt = asyncio.create_task(listen())
        for i in range(0, len(pcm), CHUNK):                       # 실시간처럼 흘려 넣는다
            await ws.send(json.dumps({"realtimeInput": {"audio": {"mimeType": "audio/pcm;rate=16000", "data": base64.b64encode(pcm[i:i + CHUNK]).decode()}}}))
            await asyncio.sleep(0.1)
        t_end = time.perf_counter()
        await ws.send(json.dumps({"realtimeInput": {"audioStreamEnd": True}}))
        await lt
        src_s = len(pcm) / 32000
        return {"model": model, "src": text, "src_audio_s": round(src_s, 2),
                "first_after_start_s": round(t_first_abs - t_start, 2) if t_first_abs else None,
                "first_after_end_s": round(t_first_abs - t_end, 2) if t_first_abs else None,
                "out_audio_s": round(nbytes / 2 / 24000, 2), "in_transcript": in_tr[:100], "out_transcript": out_tr[:140]}


async def main():
    rows = []
    for m in MODELS:
        for i, s in enumerate(S):
            try:
                r = await one(m, s, pcm_of(s, i))
            except Exception as e:
                r = {"model": m, "src": s, "error": str(e)[:140]}
            rows.append(r); print("  ", json.dumps(r, ensure_ascii=False)[:230], flush=True)
            await asyncio.sleep(3)
    summ = {}
    for m in MODELS:
        ok = [r for r in rows if r.get("model") == m and r.get("first_after_start_s") is not None]
        if ok:
            summ[m] = {"n": len(ok), "src_audio_median_s": statistics.median(r["src_audio_s"] for r in ok),
                       "first_after_start_median_s": statistics.median(r["first_after_start_s"] for r in ok),
                       "first_after_end_median_s": statistics.median(r["first_after_end_s"] for r in ok),
                       "out_audio_median_s": statistics.median(r["out_audio_s"] for r in ok)}
    json.dump({"measured": time.strftime("%Y-%m-%d"), "input": "말소리(edge-tts 한국어 → 16kHz PCM, 100ms 청크 실시간 전송)", "summary": summ, "rows": rows,
               "book_ref": {"sequential_total_median_s": 5.46, "translate_median_s": 4.28, "tts_first_chunk_s": 0.37, "source": "Ch23+ §7"},
               "text_input_probe": "텍스트 턴에는 두 모델 중 번역 전용 모델이 응답 없음(오류도 없음) — 말소리 전용"},
              open(os.path.join(WORK, "live_translate.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  요약:", json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

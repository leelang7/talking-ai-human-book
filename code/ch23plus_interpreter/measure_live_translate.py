# -*- coding: utf-8 -*-
"""
Ch23+ §7 보강 — 네이티브 실시간 번역 모델의 첫 소리까지

이 장의 순차 통역은 문장이 끝난 뒤 번역 호출 + TTS 로 첫 소리까지 5.46초였다(§7).
2026 의 라이브 번역 모델은 말을 넣으면 **다른 언어의 소리를 바로 낸다**. 같은 창구 문장 셋을
텍스트로 넣고(STT 는 제외) 첫 오디오 청크까지를 잰다 — §7 의 '번역 + TTS 첫 청크' 구간과 같은 자.

    python measure_live_translate.py    → _work/live_translate.json
"""
import asyncio, base64, json, os, statistics, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_lib"))
from paths import gemini_key   # noqa: E402
import websockets   # noqa: E402

KEY = gemini_key()
URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=" + KEY
MODELS = os.environ.get("LIVE_MODELS", "gemini-3.5-live-translate-preview,gemini-3.1-flash-live-preview").split(",")
S = ["안녕하세요, 올댓에이아이 안내 창구입니다.", "여권과 신청서를 함께 제출해 주세요.", "처리에는 영업일 기준 3일이 걸리고 수수료는 12,000원입니다."]
SYS = "You are a live interpreter. Translate every Korean utterance into natural spoken English. Keep numbers and proper nouns exactly. Output only the translation."


async def one(model, s):
    t0 = time.perf_counter(); first = None; nbytes = 0; text = ""
    async with websockets.connect(URL, max_size=16 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"setup": {"model": f"models/{model}", "generationConfig": {"responseModalities": ["AUDIO"]},
                                            "systemInstruction": {"parts": [{"text": SYS}]}}}))
        await ws.recv()
        t1 = time.perf_counter()
        await ws.send(json.dumps({"clientContent": {"turns": [{"role": "user", "parts": [{"text": s}]}], "turnComplete": True}}))
        while True:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
            except asyncio.TimeoutError:
                break
            sc = msg.get("serverContent", {})
            for part in sc.get("modelTurn", {}).get("parts", []):
                if "inlineData" in part:
                    first = first if first is not None else time.perf_counter() - t1
                    nbytes += len(base64.b64decode(part["inlineData"]["data"]))
                if "text" in part:
                    text += part["text"]
            ot = sc.get("outputTranscription", {}).get("text")
            if ot:
                text += ot
            if sc.get("turnComplete"):
                break
    return {"model": model, "src": s, "setup_s": round(t1 - t0, 2), "ttfa_s": round(first, 2) if first else None,
            "total_s": round(time.perf_counter() - t1, 2), "audio_s": round(nbytes / 2 / 24000, 2), "text": text[:100]}


async def main():
    rows = []
    for m in MODELS:
        for s in S:
            try:
                r = await one(m, s)
            except Exception as e:
                r = {"model": m, "src": s, "error": str(e)[:140]}
            rows.append(r); print("  ", json.dumps(r, ensure_ascii=False)[:170], flush=True)
            await asyncio.sleep(4)
    summ = {m: {"n": len(ok), "ttfa_median_s": statistics.median(r["ttfa_s"] for r in ok), "total_median_s": statistics.median(r["total_s"] for r in ok)}
            for m in MODELS if (ok := [r for r in rows if r.get("model") == m and r.get("ttfa_s")])}
    json.dump({"measured": time.strftime("%Y-%m-%d"), "summary": summ, "rows": rows,
               "book_ref": {"sequential_total_median_s": 5.46, "translate_median_s": 4.28, "tts_first_chunk_s": 0.37, "source": "Ch23+ §7"}},
              open(os.path.join(HERE, "_work", "live_translate.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  요약:", json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

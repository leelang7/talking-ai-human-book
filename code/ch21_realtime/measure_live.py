# -*- coding: utf-8 -*-
"""
Ch21 §10 — 네이티브 오디오(S2S) 모델의 첫 소리까지: 이 책의 사다리와 같은 자로 잰다

이 책의 실시간 트랙은 STT → LLM → TTS 를 이어 붙인다(첫 소리 1.26초, §5).
2025~26 의 네이티브 오디오 모델은 텍스트(또는 음성)를 넣으면 **모델이 직접 소리를 낸다** —
TTS 단계가 없다. 그러면 첫 소리까지 얼마나 걸리나. 같은 문장, 같은 기계, 같은 시각 기준.

    python measure_live.py          → _work/live_ttfa.json   (Gemini Live API · websockets 만 필요)

재는 것: 질문 전송 완료 → 첫 오디오 청크 도착 (TTFA). 텍스트 입력이라 STT 는 빠져 있다 —
표에서는 이 책의 '번역 첫 문장 + TTS 첫 청크' 와 같은 구간과 비교한다.
"""
import asyncio, base64, json, os, statistics, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_lib"))
from paths import gemini_key   # noqa: E402
import websockets   # noqa: E402

KEY = gemini_key()
URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=" + KEY
MODELS = [m for m in os.environ.get("LIVE_MODELS", "gemini-2.5-flash-native-audio-latest,gemini-3.1-flash-live-preview").split(",") if m]
QS = ["무릎이 아픈데 오늘 스쿼트 해도 될까?", "어제 몇 세트 했는지 기억나?", "10분만 하고 싶은데 뭐부터 할까?"]
SYS = "당신은 홈트레이닝 코치 '코치'입니다. 한두 문장으로 친근하게 답하세요."


async def one(model, q):
    t0 = time.perf_counter(); first = None; nbytes = 0; text = ""
    async with websockets.connect(URL, max_size=16 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"setup": {"model": f"models/{model}",
                                            "generationConfig": {"responseModalities": ["AUDIO"]},
                                            "systemInstruction": {"parts": [{"text": SYS}]}}}))
        await ws.recv()                                   # setupComplete
        t_setup = time.perf_counter() - t0
        t1 = time.perf_counter()
        await ws.send(json.dumps({"clientContent": {"turns": [{"role": "user", "parts": [{"text": q}]}], "turnComplete": True}}))
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=20)
            except asyncio.TimeoutError:
                break
            msg = json.loads(raw)
            sc = msg.get("serverContent", {})
            for part in sc.get("modelTurn", {}).get("parts", []):
                if "inlineData" in part:
                    if first is None:
                        first = time.perf_counter() - t1
                    nbytes += len(base64.b64decode(part["inlineData"]["data"]))
                if "text" in part:
                    text += part["text"]
            if sc.get("turnComplete"):
                break
    total = time.perf_counter() - t1
    return {"model": model, "q": q, "setup_s": round(t_setup, 2), "ttfa_s": round(first, 2) if first else None,
            "total_s": round(total, 2), "audio_s": round(nbytes / 2 / 24000, 2), "text": text[:80]}


async def main():
    rows = []
    for m in MODELS:
        for q in QS:
            try:
                r = await one(m, q)
            except Exception as e:                        # 한도·미지원 모델은 기록하고 넘어간다
                r = {"model": m, "q": q, "error": str(e)[:120]}
            rows.append(r); print("  ", json.dumps(r, ensure_ascii=False)[:150], flush=True)
            await asyncio.sleep(4)
    summ = {}
    for m in MODELS:
        ok = [r for r in rows if r.get("model") == m and r.get("ttfa_s")]
        if ok:
            summ[m] = {"n": len(ok), "ttfa_median_s": statistics.median(r["ttfa_s"] for r in ok),
                       "setup_median_s": statistics.median(r["setup_s"] for r in ok),
                       "total_median_s": statistics.median(r["total_s"] for r in ok)}
    out = {"measured": time.strftime("%Y-%m-%d"), "summary": summ, "rows": rows,
           "book_pipeline_ref": {"ttfa_streamed_flash_lite_s": 1.26, "ttfa_server_path_s": 3.77, "source": "Ch21 §5"}}
    json.dump(out, open(os.path.join(HERE, "_work", "live_ttfa.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  요약:", json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

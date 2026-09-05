# -*- coding: utf-8 -*-
"""
Ch21 실측 ② — 스트리밍 경로의 첫 소리까지.

measure_ttfa.py 는 server.py 그대로(비스트리밍 LLM → 문장 전체 TTS 파일)를 쟀다.
이 파일은 Ch07 §4 가 말하는 겹침 경로를 잰다.
    LLM  : Gemini REST 스트리밍(alt=sse) — 첫 토큰 · 첫 문장 완성 시각
    TTS  : edge-tts Communicate.stream() — 첫 오디오 청크 시각
    TTFA = 첫 문장 완성 + 첫 청크

    python measure_stream.py    → _work/ttfa_stream.json
"""
import asyncio, json, os, re, statistics, sys, time
import requests, edge_tts
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import gemini_key   # noqa: E402
KEY = gemini_key()
MODEL = os.environ.get("TTFA_MODEL", "gemini-2.5-flash-lite")   # 무료 한도에 걸리면 사다리의 다음 모델로
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:streamGenerateContent?alt=sse&key={KEY}"
SYSTEM = ("너는 홈트레이닝 코치다. 친근하고 활기차다. 요체로 한두 문장. "
          "답변 맨 앞에 [감정][동작] 태그. 감정 greet/happy/excited/think/sad/neutral · 동작 wave/nod/stretch/squat/none")
QS = ["안녕하세요", "오늘 기분 어때요?", "스쿼트 몇 개가 좋아요?", "무릎이 아픈데 어떻게 하죠?",
      "내일 비 온대요", "팔 운동 추천해줘", "저 오늘 너무 피곤해요", "고마워요 내일 봐요"]
VOICE = "ko-KR-InJoonNeural"
_SENT = re.compile(r"[.!?~]\s|[.!?~]$")


def llm_stream(q):
    body = {"system_instruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"parts": [{"text": q}]}],
            "generationConfig": {"temperature": 0.9, "maxOutputTokens": 80, "thinkingConfig": {"thinkingBudget": 0}}}
    t0 = time.time(); first = sent = None; text = ""
    r = None
    for attempt in range(4):                       # 무료 등급 분당 한도(429) — 기다렸다 다시
        r = requests.post(URL, json=body, stream=True, timeout=30)
        if r.status_code != 429:
            break
        r.close(); time.sleep(20 * (attempt + 1)); t0 = time.time()
    with r:
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        for line in r.iter_lines():
            if not line or not line.startswith(b"data:"):
                continue
            try:
                j = json.loads(line[5:])
                piece = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])
            except Exception:
                continue
            if piece and first is None:
                first = time.time() - t0
            text += piece
            body_txt = re.sub(r"^\s*\[\w+\]\s*\[\w+\]\s*", "", text)
            if sent is None and _SENT.search(body_txt):
                sent = time.time() - t0
                break
    return text, first, sent if sent is not None else time.time() - t0


async def tts_first_chunk(text):
    t0 = time.time(); g = edge_tts.Communicate(text, VOICE).stream(); got = None
    async for chunk in g:
        if chunk["type"] == "audio":
            got = time.time() - t0
            break
    await g.aclose()                               # 첫 청크만 받고 세션을 닫는다
    return got


def main():
    rows = []
    for i, q in enumerate(QS):
        if i:
            time.sleep(8)                            # 분당 한도 안에서 — 측정 대상이 아니다
        try:
            text, ttft, tsent = llm_stream(q)
        except Exception as e:
            print("  LLM 오류:", type(e).__name__, str(e)[:40]); continue
        first_sentence = re.sub(r"^\s*\[\w+\]\s*\[\w+\]\s*", "", text)
        first_sentence = re.split(r"(?<=[.!?~])\s", first_sentence)[0][:80] or "네"
        tta = asyncio.run(tts_first_chunk(first_sentence))
        ttfa = tsent + (tta or 0)
        rows.append({"q": q, "first_sentence": first_sentence[:50], "ttft_s": round(ttft or 0, 2), "first_sentence_s": round(tsent, 2), "tts_first_chunk_s": round(tta or 0, 2), "ttfa_s": round(ttfa, 2), "in_budget": ttfa <= 2.0})
        print(f"  첫토큰 {ttft or 0:4.2f}s  첫문장 {tsent:4.2f}s  TTS첫청크 {tta or 0:4.2f}s  = {ttfa:4.2f}s {'OK ' if ttfa<=2.0 else 'OVER'}  {q[:12]:12s} → {first_sentence[:28]}")
    if rows:
        tt = sorted(r["ttfa_s"] for r in rows)
        summ = {"n": len(rows), "ttft_median_s": round(statistics.median(r["ttft_s"] for r in rows), 2),
                "first_sentence_median_s": round(statistics.median(r["first_sentence_s"] for r in rows), 2),
                "tts_first_chunk_median_s": round(statistics.median(r["tts_first_chunk_s"] for r in rows), 2),
                "ttfa_median_s": round(statistics.median(tt), 2), "ttfa_max_s": tt[-1], "in_budget": sum(r["in_budget"] for r in rows),
                "budget_s": 2.0, "model": MODEL, "voice": VOICE, "measured": "2026-09-03"}
        print(f"  중앙값 첫토큰 {summ['ttft_median_s']}s · 첫문장 {summ['first_sentence_median_s']}s · TTS첫청크 {summ['tts_first_chunk_median_s']}s · TTFA {summ['ttfa_median_s']}s (최대 {summ['ttfa_max_s']}s) · 예산 안 {summ['in_budget']}/{len(rows)}")
        for r in rows:
            r["model"] = MODEL
        path = os.path.join(HERE, "_work", "ttfa_stream.json")
        prev = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
        # 모델별로 따로 둔다 — 다른 모델의 표본을 섞어 중앙값을 내지 않는다
        by = prev.get("by_model", {})
        if "summary" in prev and "by_model" not in prev:            # 예전 형식(flash-lite 표본 2)을 옮긴다
            by[prev["summary"].get("model", "gemini-2.5-flash-lite")] = {"summary": prev["summary"], "rows": prev["rows"]}
        by[MODEL] = {"summary": summ, "rows": rows}
        json.dump({"by_model": by, "measured": "2026-09-03"}, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  → _work/ttfa_stream.json")


if __name__ == "__main__":
    main()

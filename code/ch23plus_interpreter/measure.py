# -*- coding: utf-8 -*-
"""
Ch23+ §7 실측 — 문장 하나가 화자의 입에서 통역 아바타의 첫 소리까지.

    번역: Gemini(경량 모델) 한 문장 · 용어 잠금 + 숫자 보존 검사
    TTS : edge-tts 대상 언어 목소리의 첫 오디오 청크
    한국어 6문장 → 영어 · 일본어

    python measure.py    → _work/measure.json   (네트워크 필요)
"""
import asyncio, json, os, statistics, sys, time
import requests
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from interpreter import Glossary, VOICES, latency_budget, numbers_preserved, translate   # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import gemini_key   # noqa: E402
KEY = gemini_key()
MODEL = os.environ.get("INTERP_MODEL", "gemini-2.5-flash-lite")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}"
S = ["안녕하세요, 올댓에이아이 안내 창구입니다.",
     "여권과 신청서를 함께 제출해 주세요.",
     "처리에는 영업일 기준 3일이 걸리고 수수료는 12,000원입니다.",
     "3층 305호에서 접수하시면 됩니다.",
     "무릎이 아프시면 오늘은 스쿼트 대신 걷기 20분만 하세요.",
     "다음 열차는 4분 뒤에 도착합니다."]
G = Glossary({"올댓에이아이": "AllThatAI"})


LAST = {"call_s": 0.0}          # 마지막 성공 호출의 순수 시간 — 429 대기는 지연이 아니라 한도다


def llm(prompt):
    for attempt in range(3):
        t0 = time.time()
        r = requests.post(URL, json={"contents": [{"parts": [{"text": prompt}]}],
                                     "generationConfig": {"temperature": 0.2, "maxOutputTokens": 120, "thinkingConfig": {"thinkingBudget": 0}}}, timeout=30)
        LAST["call_s"] = time.time() - t0
        if r.status_code == 200:
            try:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError):
                return ""
        if r.status_code != 429:
            return ""
        time.sleep(15 * (attempt + 1))
    return ""


async def first_chunk(text, voice):
    import edge_tts
    for attempt in range(2):                          # edge-tts 는 가끔 'No audio' 를 낸다(Ch21 §5)
        t0 = time.time(); g = edge_tts.Communicate(text, voice).stream(); got = None
        try:
            async for ch in g:
                if ch["type"] == "audio":
                    got = time.time() - t0; break
            await g.aclose()
            return got
        except Exception:
            await asyncio.sleep(1)
    return None


def main():
    rows = []
    n = int(os.environ.get("INTERP_N", len(S)))
    for dst in ("en", "ja"):
        for i, s in enumerate(S[:n]):
            if rows:
                time.sleep(float(os.environ.get("INTERP_PACE_S", "12")))     # 무료 등급 분당 한도
            t0 = time.time(); out = translate(s, "ko", dst, llm, G); wall = time.time() - t0
            tr = LAST["call_s"] if wall - LAST["call_s"] > 10 else wall      # 429 대기가 섞였으면 순수 호출 시간만
            miss = G.check(s, out) + numbers_preserved(s, out)
            if not out:
                print(f"  {dst} 번역 실패(빈 응답) — 건너뜀: {s[:30]}"); continue
            tts = asyncio.run(first_chunk(out, VOICES[dst])) or 0.0
            rows.append({"dst": dst, "src": s, "out": out, "translate_s": round(tr, 2), "tts_first_chunk_s": round(tts, 2),
                         "total_from_end_of_speech_s": round(0.8 + tr + tts, 2), "missing": miss})
            print(f"  {dst} 번역 {tr:4.2f}s  TTS첫청크 {tts:4.2f}s  = {0.8+tr+tts:4.2f}s {'⚠'+str(miss) if miss else '  '}  {out[:48]}")
    ok = [r for r in rows if r["out"]]
    summ = {"n": len(ok), "translate_median_s": round(statistics.median(r["translate_s"] for r in ok), 2),
            "tts_first_chunk_median_s": round(statistics.median(r["tts_first_chunk_s"] for r in ok), 2),
            "total_median_s": round(statistics.median(r["total_from_end_of_speech_s"] for r in ok), 2),
            "total_max_s": max(r["total_from_end_of_speech_s"] for r in ok),
            "missing_count": sum(1 for r in ok if r["missing"]), "budget": latency_budget(), "model": MODEL, "measured": "2026-09-03"}
    print(f"  중앙값 번역 {summ['translate_median_s']}s · TTS 첫청크 {summ['tts_first_chunk_median_s']}s · 발화 끝→첫 소리 {summ['total_median_s']}s (최대 {summ['total_max_s']}) · 누락 {summ['missing_count']}/{len(ok)}")
    json.dump({"summary": summ, "rows": rows}, open(os.path.join(HERE, "_work", "measure.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  → _work/measure.json")


if __name__ == "__main__":
    main()

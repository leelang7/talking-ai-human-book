# -*- coding: utf-8 -*-
"""
Ch21 실측 — 첫 소리까지(TTFA) 를 진짜로 잰다.

server.py 의 **함수 그대로**(server.gemini · server.tts — 직접 REST 비스트리밍 + edge-tts 서브프로세스)를
같은 순서로 부르고 LLM 초 · TTS 초 · 합계를 8개 발화에 대해 기록한다. TTFA_BUDGET(2.0초) 과 비교한다.
(첫 판은 mafia_engine 의 다중 프로바이더 라우터로 쟀다가 서버 경로가 아니어서 버렸다.)

    python measure_ttfa.py    → _work/ttfa.json   (네트워크 필요)
"""
import json, os, statistics, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from turn import TTFA_BUDGET, make_turn, parse_tags   # noqa: E402
import server as S                                     # noqa: E402  — 서버의 gemini()/tts() 를 그대로

SYSTEM = S.PRESETS["coach"]["sys"]                    # 서버의 코치 프리셋 (TAG_RULE 은 server.gemini 가 붙인다)
QS = ["안녕하세요", "오늘 기분 어때요?", "스쿼트 몇 개가 좋아요?", "무릎이 아픈데 어떻게 하죠?",
      "내일 비 온대요", "팔 운동 추천해줘", "저 오늘 너무 피곤해요", "고마워요 내일 봐요"]
VOICE = "ko-KR-InJoonNeural"


def tts_sec(text):
    t0 = time.time()
    url = S.tts(text, VOICE)                          # 서버 함수 그대로 — 서브프로세스 + 파일 완성까지
    return time.time() - t0, bool(url)


def main():
    rows = []
    for i, q in enumerate(QS):
        if i:
            time.sleep(8)                              # 무료 등급 분당 한도 — 측정 대상이 아니다
        t0 = time.time(); a = S.gemini(q, SYSTEM) or ""; llm = time.time() - t0
        emo, act, body = parse_tags(a)
        ts, ok = tts_sec(body or a or "네")
        turn = make_turn(a, llm, ts, "x.mp3")
        rows.append({"q": q, "reply": a[:60], "llm_s": round(llm, 2), "tts_s": round(ts, 2), "ttfa_s": round(llm + ts, 2), "tts_ok": ok, "in_budget": llm + ts <= TTFA_BUDGET})
        print(f"  LLM {llm:5.2f}s  TTS {ts:5.2f}s  = {llm+ts:5.2f}s {'OK ' if llm+ts<=TTFA_BUDGET else 'OVER'}  {q[:14]:14s} → {a[:36]}")
    tt = sorted(r["ttfa_s"] for r in rows); ll = [r["llm_s"] for r in rows]; ss = [r["tts_s"] for r in rows]
    summ = {"n": len(rows), "llm_median_s": round(statistics.median(ll), 2), "tts_median_s": round(statistics.median(ss), 2),
            "ttfa_median_s": round(statistics.median(tt), 2), "ttfa_max_s": tt[-1], "ttfa_p95_s": tt[max(0, int(len(tt) * 0.95) - 1)],
            "in_budget": sum(r["in_budget"] for r in rows), "budget_s": TTFA_BUDGET, "model": S.GEMINI_MODELS[0] + " (사다리 폴백 포함)", "voice": VOICE, "measured": "2026-09-03"}
    print(f"  중앙값 LLM {summ['llm_median_s']}s · TTS {summ['tts_median_s']}s · TTFA {summ['ttfa_median_s']}s (최대 {summ['ttfa_max_s']}s) · 예산 안 {summ['in_budget']}/{len(rows)}")
    json.dump({"summary": summ, "rows": rows}, open(os.path.join(HERE, "_work", "ttfa.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  → _work/ttfa.json")


if __name__ == "__main__":
    main()

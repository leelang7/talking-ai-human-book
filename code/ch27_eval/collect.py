# -*- coding: utf-8 -*-
"""
Ch27 — 골든셋에 **실제 모델** 을 돌려 응답을 모은다 (score.py --responses 입력).

    페르소나 = Ch22 의 COACH.system_prompt()   (규칙 층 + 태그 규칙)
    모델     = 환경변수 GOLDEN_MODEL (기본 gemini-flash-latest — 무료 한도가 남아 있는 것)
    기억 문항(then) 은 첫 답을 대화 이력으로 넣고 두 번째 질문을 던진다

    python collect.py            → _work/responses_<model>.json
    python score.py --responses _work/responses_<model>.json --baseline baseline.json
"""
import json, os, sys, time
import requests
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "ch22_persona"))
from persona import COACH                      # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import gemini_key   # noqa: E402
KEY = gemini_key()
MODEL = os.environ.get("GOLDEN_MODEL", "gemini-flash-latest")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}"
PACE_S = float(os.environ.get("GOLDEN_PACE_S", "12"))     # 무료 등급 분당 한도 — 5초 간격은 429 를 불렀다


def ask(history, system):
    body = {"system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": r, "parts": [{"text": t}]} for r, t in history],
            "generationConfig": {"temperature": 0.9, "maxOutputTokens": 120, "thinkingConfig": {"thinkingBudget": 0}}}
    for attempt in range(4):
        r = requests.post(URL, json=body, timeout=30)
        if r.status_code == 200:
            try:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except (KeyError, IndexError):
                return ""
        if r.status_code != 429:
            return ""
        time.sleep(20 * (attempt + 1))
    return ""


def main():
    gs = json.load(open(os.path.join(HERE, "goldenset.json"), encoding="utf-8"))
    system = COACH.system_prompt()
    out, t0 = {}, time.time()
    for i, it in enumerate(gs["items"]):
        if i:
            time.sleep(PACE_S)
        a = ask([("user", it["q"])], system)
        out[it["id"]] = a
        print(f"  {it['id']}  {it['cat']:5s}  {a[:70].replace(chr(10), ' ')}")
        if "then" in it:
            time.sleep(PACE_S)
            b = ask([("user", it["q"]), ("model", a or "네."), ("user", it["then"])], system)
            out[it["id"] + "_then"] = b
            print(f"  {it['id']}_then       {b[:70].replace(chr(10), ' ')}")
    os.makedirs(os.path.join(HERE, "_work"), exist_ok=True)
    tag = MODEL.replace(".", "_")
    path = os.path.join(HERE, "_work", f"responses_{tag}.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)     # score.py 는 {id: 응답} 평면 사전을 읽는다
    json.dump({"model": MODEL, "system_prompt_chars": len(system), "collected": time.strftime("%Y-%m-%d %H:%M"),
               "elapsed_s": round(time.time() - t0), "empty": sum(1 for v in out.values() if not v)},
              open(os.path.join(HERE, "_work", f"responses_{tag}.meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  → {path}  (빈 응답 {sum(1 for v in out.values() if not v)}건)")


if __name__ == "__main__":
    main()

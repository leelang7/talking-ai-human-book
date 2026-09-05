# -*- coding: utf-8 -*-
"""
Ch22 실험 — 규칙 층이 실제로 말투를 고정하는가.

같은 모델·같은 질문에 시스템 프롬프트만 바꿔 validate() 위반을 센다.
  A  정체성 한 줄만            "너는 홈트레이닝 코치다. 친근하고 활기차다."
  B  + 어미·호칭·금지·메타 규칙  Persona.system_prompt() (태그 규칙 제외)
  C  + 예시 두 줄               B + examples

    python experiment.py    → _work/experiment.json   (Gemini 호출: 질문 수 × 3)

**저자 전용 실행 스크립트입니다.** 저자의 대화 엔진(이 저장소 밖)을 부르므로 그대로는 안 돕니다.
결과는 `_work/experiment.json` 에 담겨 있고 본문 표는 그 값입니다 — 재현하려면
같은 프롬프트 셋을 여러분의 LLM 호출로 바꿔 돌리세요.
"""
import json, os, sys, time, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import where   # noqa: E402
sys.path.insert(0, os.path.join(where("avatar"), "mafia"))   # ← 저자의 대화 엔진(이 저장소 밖)
os.chdir(where("avatar"))
from persona import COACH, Persona, validate    # noqa: E402
import mafia_engine as ME                       # noqa: E402

gs = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ch27_eval", "goldenset.json"), encoding="utf-8"))
items = gs if isinstance(gs, list) else gs.get("items", list(gs.values()))
def q_of(it): return it.get("q") or it.get("question") or it.get("prompt") or it.get("input")
QS = [q_of(it) for it in items if q_of(it)][:12]

plain = Persona(name="코치", identity=COACH.identity, ending=None)
A = COACH.identity
B = Persona(name="코치", identity=COACH.identity, ending=COACH.ending, banned=COACH.banned,
            forbidden_topics=COACH.forbidden_topics, unknown_style=COACH.unknown_style).system_prompt()
C = COACH.system_prompt()
VARIANTS = {"A_identity_only": A, "B_rules": B, "C_rules_examples": C}
judge = Persona(name="코치", identity=COACH.identity, ending=COACH.ending, banned=COACH.banned)   # 태그 규칙 없이 채점

res, log = {}, []
for tag, sysm in VARIANTS.items():
    kinds, fails = collections.Counter(), 0
    for q in QS:
        for _ in range(2):
            a = ME.gemini(q, system=sysm, temperature=0.9, max_tokens=120)
            if a: break
            time.sleep(1)
        ok, bad = validate(a or "", judge)
        bad = [b for b in bad if not b.startswith("태그")]
        fails += bool(bad); kinds.update(b.split("(")[0] for b in bad)
        log.append({"variant": tag, "q": q, "a": a, "bad": bad})
    res[tag] = {"n": len(QS), "responses_with_violation": fails, "violation_rate": round(fails / len(QS), 2), "by_kind": dict(kinds)}
    print(f"  {tag:18s} 위반 {fails}/{len(QS)}  {dict(kinds)}")
json.dump({"model": ME.GEMINI_MODELS[0], "questions": QS, "results": res, "log": log},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_work", "experiment.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("  → _work/experiment.json")

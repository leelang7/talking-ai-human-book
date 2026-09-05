# -*- coding: utf-8 -*-
"""
Ch26 §4 실험 — 발언권 규칙이 발언 분포를 어떻게 만드는가.

    R  순서 고정(라운드 로빈)
    M  이름 지목 우선 — 직전 발언에서 불린 사람이 답한다 (engine.next_speaker 의 규칙)
    M+ M 에 굶주림 방지 — 오래 말 못한 사람이 있으면 그가 먼저

여섯 캐릭터 · 300턴 · 발언자는 40% 확률로 누군가를 지목하고, 지목은 '친한 둘' 에 몰린다(편향).
    발언 점유율 최대/최소 · 가장 긴 침묵(턴)

    python turns.py    → _work/turns.json
"""
import json, os, random, statistics
from engine import Character, Orchestrator

NAMES = ["하늘", "바다", "산", "강", "들", "숲"]
CLIQUE = {"하늘": "바다", "바다": "하늘", "산": "하늘", "강": "바다", "들": "하늘", "숲": "바다"}   # 지목이 두 명에게 몰린다


def make_cast():
    import inspect
    params = [q for q in inspect.signature(Character.__init__).parameters.values()
              if q.name != "self" and q.default is inspect.Parameter.empty]
    return [Character(n, *["-"] * (len(params) - 1)) for n in NAMES]      # 이름 외 필수 인자는 자리표시자


def simulate(rule, turns=300, seed=1, max_silence=8):
    rng = random.Random(seed)
    orch = Orchestrator(make_cast(), max_silence=(max_silence if rule == "M+" else None))
    orch.phase = "discuss"
    count = {n: 0 for n in NAMES}; last = {n: -1 for n in NAMES}; longest = {n: 0 for n in NAMES}
    mentioned = None
    for t in range(turns):
        if rule == "R":
            who = NAMES[t % len(NAMES)]
        else:
            who = orch.next_speaker(mentioned=mentioned)      # M+ 는 엔진 안의 굶주림 방지가 작동한다
        count[who] += 1
        for n in NAMES:
            gap = t - last[n]
            longest[n] = max(longest[n], gap)
        last[who] = t
        orch.turn += 1
        mentioned = CLIQUE[who] if rng.random() < 0.4 else None
    share = {n: count[n] / turns for n in NAMES}
    return {"share_max": round(max(share.values()), 2), "share_min": round(min(share.values()), 2),
            "longest_silence": max(longest.values()), "share": {n: round(v, 2) for n, v in share.items()}}


def main():
    out = {r: simulate(r) for r in ("R", "M", "M+")}
    print("  규칙   점유율 최대  최소   가장 긴 침묵(턴)")
    for r, v in out.items():
        print(f"  {r:4s}   {v['share_max']:5.0%}   {v['share_min']:5.0%}    {v['longest_silence']:3d}")
    json.dump({"turns": 300, "cast": 6, "mention_p": 0.4, "max_silence": 8, "results": out},
              open(os.path.join("_work", "turns.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  → _work/turns.json")


if __name__ == "__main__":
    main()

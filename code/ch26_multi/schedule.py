# -*- coding: utf-8 -*-
"""
Ch26 §5 — 25초를 5초로

한 라운드에 LLM 호출 25번. 순차로 돌리면 약 25초, 스레드 풀로 던지면 약 5초.
**5배** 다. 그리고 이 시간은 대개 공짜로 숨겨진다 — 사람이 입력하는 동안
AI 여섯 명의 대사가 뒤에서 만들어지기 때문이다.

여기서는 두 가지로 확인한다.

  ① 산식     ceil(n / workers) × 지연     — 결정론적이라 테스트로 박을 수 있다
  ② 실측     실제 스레드 풀로 돌려서 산식과 맞는지

산식만 두면 "계산상 그렇다" 로 끝나고, 실측만 두면 기계마다 값이 흔들린다.
**둘을 나란히 두고 어긋나는지를 본다.**

    python schedule.py
"""
import math
import time
from concurrent.futures import ThreadPoolExecutor

ROUND_CALLS = 25            # §5 — 저자 추리극 실측
CALL_SECONDS = 1.0
WORKERS = 5


def sequential_seconds(n=ROUND_CALLS, latency=CALL_SECONDS) -> float:
    return n * latency


def parallel_seconds(n=ROUND_CALLS, latency=CALL_SECONDS, workers=WORKERS) -> float:
    """스레드 풀은 **파도(wave) 단위** 로 끝난다.

    호출 25개를 5개짜리 풀에 던지면 5파도다. 워커를 25개로 늘리면 1파도가
    되지만, 그때는 제공자의 동시 요청 한도와 요금이 먼저 걸린다.
    """
    if workers <= 0:
        raise ValueError("워커는 1 이상이어야 한다")
    return math.ceil(n / workers) * latency


def speedup(n=ROUND_CALLS, latency=CALL_SECONDS, workers=WORKERS) -> float:
    return sequential_seconds(n, latency) / parallel_seconds(n, latency, workers)


def measure(n=ROUND_CALLS, latency=0.02, workers=WORKERS):
    """실제 스레드로 재 본다. 지연은 sleep 으로 흉내낸다."""
    def call(_):
        time.sleep(latency)
        return 1

    t0 = time.perf_counter()
    for i in range(n):
        call(i)
    seq = time.perf_counter() - t0

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(call, range(n)))
    par = time.perf_counter() - t0
    return {"seq": seq, "par": par, "speedup": seq / par if par else 0.0,
            "model_seq": sequential_seconds(n, latency),
            "model_par": parallel_seconds(n, latency, workers)}


def round_calls(cast_size: int, phase: str) -> int:
    """이 페이즈에 실제로 몇 번 부르는가 (§5 — 안 부르는 자리를 세는 것이 절약이다)."""
    return {"brief": 0, "reveal": 0, "discuss": 1, "vote": cast_size}.get(phase, 0)


def _demo():
    print()
    print(f"  호출 {ROUND_CALLS}회 · 1회 {CALL_SECONDS}초 · 워커 {WORKERS}")
    print(f"    순차 {sequential_seconds():.0f}초  →  병렬 {parallel_seconds():.0f}초"
          f"   ({speedup():.0f}배)")
    print()
    print("  워커 수를 바꾸면")
    for w in (1, 2, 5, 10, 25):
        print(f"    워커 {w:>2}  {parallel_seconds(workers=w):>5.1f}초   {speedup(workers=w):>4.1f}배")
    print()
    m = measure()
    print(f"  실측(1회 20ms) 순차 {m['seq']:.2f}초 → 병렬 {m['par']:.2f}초 ({m['speedup']:.1f}배)")
    import json, os
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_work"), exist_ok=True)
    json.dump({k: round(v, 3) for k, v in m.items()},
              open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_work", "schedule.json"), "w"), indent=1)
    print(f"  산식             순차 {m['model_seq']:.2f}초 → 병렬 {m['model_par']:.2f}초")
    print()
    print("  페이즈별 호출 수 (6인 기준)")
    for p in ("brief", "discuss", "vote", "reveal"):
        n = round_calls(6, p)
        print(f"    {p:9} {n}회" + ("   ← 템플릿으로 찍는다" if n == 0 else ""))
    print()


if __name__ == "__main__":
    _demo()

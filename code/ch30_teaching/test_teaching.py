# -*- coding: utf-8 -*-
"""
Ch30 회귀 테스트 — 수업 인프라도 게이트를 지난다

    python test_teaching.py
"""
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from gpu_queue import ClassQueue  # noqa: E402

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def main() -> int:
    print("\n  ── Ch30 수업 인프라 ──")
    t = [0.0]

    # ── ① 공평한 순서 ─────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as d:
        q = ClassQueue(d, clock=lambda: t[0], window=(0, 3600))
        for _ in range(4):
            q.submit(10.0, owner="지민")
        q.submit(10.0, owner="서준")
        q.submit(10.0, owner="하은")
        order = []
        for _ in range(6):
            j = q.claim("gpu-0"); q.complete(j["id"]); order.append(j["owner"])
        ok(order[:3] == ["지민", "서준", "하은"],
           "★ 한 명이 넷을 넣어도 다른 둘이 먼저 한 번씩 돈다", " → ".join(order))
        ok(order.count("지민") == 4 and order[3:] == ["지민"] * 3,
           "  남은 것은 그 학생 차례에 순서대로")
        ok(q.by_owner()["지민"]["done"] == 4, "학생별 집계가 맞는다")

        # 제출 순 큐(Ch28 원본)였다면 지민이 넷을 먼저 다 썼을 것이다 — 그 대조
        from jobqueue import Queue
        q0 = Queue(os.path.join(d, "plain"), clock=lambda: t[0])
        for _ in range(4):
            q0.submit(10.0, owner="지민")
        q0.submit(10.0, owner="서준")
        first3 = [q0.claim("g")["owner"] for _ in range(3)]
        ok(first3 == ["지민"] * 3, "  (대조) 제출 순 큐는 한 명이 독점한다", " → ".join(first3))

    # ── ② 수업 시간 창 ─────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as d:
        q = ClassQueue(d, clock=lambda: t[0], window=(1000, 2000))
        q.submit(5.0, owner="A")
        t[0] = 500.0
        ok(q.claim("g") is None, "★ 수업 시간 전에는 집지 않는다")
        t[0] = 1500.0
        ok(q.claim("g") is not None, "시간 안이면 집는다")
        t[0] = 2500.0
        q.submit(5.0, owner="B")
        ok(q.claim("g") is None, "시간이 지나면 다시 대기")
        ok(ClassQueue(os.path.join(d, "nw"), clock=lambda: t[0]).open_now(), "창이 없으면 항상 열림")

        # Ch28 §6 의 민감 잡 규칙이 상속된다
        q2 = ClassQueue(os.path.join(d, "s"), clock=lambda: t[0])
        q2.submit(5.0, owner="A", tags=["deceased"])
        ok(q2.claim("remote", remote=True) is None and q2.claim("local") is not None,
           "★ 민감 잡은 원격 워커가 못 집는다 — Ch28 §6 그대로")

    # ── ③ 루브릭도 게이트를 지난다 ────────────────────────────────
    rub = open(os.path.join(HERE, "rubric.md"), encoding="utf-8").read()
    weights = [int(w) for w in re.findall(r"^\|\s*\d\s*\|[^|]+\|\s*(\d+)\s*\|", rub, re.M)]
    ok(len(weights) == 5, "루브릭 항목이 다섯이다", str(weights))
    ok(sum(weights) == 100, "★ 가중치 합이 100 이다", f"{sum(weights)}")
    ok("실패 기록" in rub and any(w == 10 for w in weights), "실패 기록 항목이 있다 (Ch30 §6)")
    ok("프로젝트 전체 0" in rub, "동의 없는 결과물은 전체 0 — Ch29 §3 의 기준선")

    tpl = open(os.path.join(HERE, "lesson_template.md"), encoding="utf-8").read()
    ok("실패 기록" in tpl and "1:25" in tpl, "강의안에 실패 기록 제출이 시간표에 들어 있다")
    ok("gpu_queue" in tpl, "강의안이 수업용 큐를 가리킨다")

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())

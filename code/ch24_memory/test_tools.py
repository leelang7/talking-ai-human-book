# -*- coding: utf-8 -*-
"""Ch24 §5 회귀 테스트 — 도구 호출의 예산·멱등·시간 초과·채움말."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools import FILLERS, ToolRouter   # noqa: E402

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def main():
    print("\n  ── Ch24 도구 호출 ──")
    hits = {"n": 0}
    def fast(q): return f"{q} 없음"
    def slow(when): time.sleep(0.5); hits["n"] += 1; return f"{when} 예약"
    def boom(x): raise RuntimeError("DB down")
    def hang(x): time.sleep(3)
    r = ToolRouter(budget_s=0.2, timeout_s=1.0)
    r.register("fast", fast, {"description": "조회"}, filler="lookup")
    r.register("slow", slow, {"description": "예약"}, idempotent=True, filler="book")
    r.register("boom", boom); r.register("hang", hang)
    ok([s["name"] for s in r.schemas()] == ["fast", "slow", "boom", "hang"] and r.schemas()[1]["description"] == "예약", "  schemas() 는 LLM 에 줄 도구 목록")
    c = r.call("fast", {"q": "어제"})
    ok(c.ok and c.filler is None and r.speak_plan(c) == ["어제 없음"], "★ 예산 안에 끝나면 채움말 없이 결과만")
    c = r.call("slow", {"when": "내일 19:00"}, key="u1:내일19")
    ok(c.ok and c.filler == FILLERS["book"] and r.speak_plan(c) == [FILLERS["book"], "내일 19:00 예약"], "★ 예산을 넘기면 채움말이 먼저, 결과가 나중", str(r.speak_plan(c)))
    c2 = r.call("slow", {"when": "내일 19:00"}, key="u1:내일19")
    ok(c2.replayed and hits["n"] == 1 and c2.result == "내일 19:00 예약", "★ 같은 멱등 키는 다시 실행하지 않는다 — 예약은 한 번", f"실행 {hits['n']}회")
    c3 = r.call("slow", {"when": "내일 19:00"}, key="u2:내일19")
    ok(not c3.replayed and hits["n"] == 2, "  키가 다르면 다른 사용자의 예약 — 실행한다")
    c = r.call("boom", {"x": 1})
    ok(not c.ok and "DB down" in c.error and "처리하지 못했어요" in c.result, "★ 도구의 예외는 대화를 죽이지 않고 문장이 된다")
    c = r.call("hang", {"x": 1})
    ok(not c.ok and c.error == "시간 초과" and c.filler is not None and "다시 말씀" in c.result and c.elapsed_s < 1.5, "★ 시간 초과 — 채움말 뒤에 사과 문장, 1초 안에 포기", f"{c.elapsed_s}s")
    c = r.call("nope", {})
    ok(not c.ok and "모르는 도구" in c.error, "  모르는 도구 이름은 오류")
    ok(len(r.calls) == 7, "  호출은 전부 기록된다 (운영자 콘솔 Ch28+)", str(len(r.calls)))
    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())

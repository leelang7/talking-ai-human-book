# -*- coding: utf-8 -*-
"""
Ch24 §5 — 도구 호출: 기억에 없는 사실은 물어보고, 물어보는 동안 침묵하지 않는다

대화 아바타가 "내일 7시에 예약해 줘" 를 받으면 셋 중 하나를 한다.
  ① 지어낸다            — 가장 흔하고 가장 나쁘다 (Ch27 §4 의 '모른다고 인정' 항목이 이것을 잡는다)
  ② 도구를 부른다       — 예약 시스템에 실제로 쓴다
  ③ 부르는 동안 말한다  — 도구가 1초를 넘기면 사용자는 2초 예산(Ch07)을 넘긴 것으로 느낀다

이 모듈은 ②와 ③을 다룬다. LLM 이 어떤 도구를 부를지는 모델의 함수 호출 기능이 정하고,
**부른 뒤에 무슨 일이 일어나는가** 는 전부 여기 코드다 — 예산 · 멱등 키 · 시간 초과 · 채움말.

    router = ToolRouter(budget_s=1.2)
    router.register("book_slot", book_slot, schema={...}, idempotent=True)
    plan = router.call("book_slot", {"when": "내일 19:00"}, key="user42:내일19")
    plan.filler   → 도구가 예산을 넘겼을 때 먼저 말할 한 문장 (부록 L)
    plan.result   → 도구 결과 (또는 시간 초과 메시지)
"""
import hashlib
import threading
import time

FILLERS = {"default": "잠시만요, 확인해 볼게요.", "book": "예약 시스템에 넣고 있어요.", "lookup": "기록을 찾아볼게요."}


class ToolCall:
    """한 번의 도구 호출 결과. 말할 순서대로 필드가 있다 — filler 먼저, result 나중."""

    def __init__(self, name, args, key):
        self.name, self.args, self.key = name, args, key
        self.filler = None          # 예산을 넘겼을 때 먼저 말할 문장
        self.result = None          # 도구가 돌려준 것
        self.error = None
        self.elapsed_s = 0.0
        self.replayed = False       # 같은 멱등 키가 이미 실행됐다 — 다시 실행하지 않았다

    @property
    def ok(self):
        return self.error is None


class ToolRouter:
    """도구 이름 → 함수. 예산(초)을 넘기면 채움말을 내고, 멱등 키가 같으면 다시 실행하지 않는다."""

    def __init__(self, budget_s=1.2, timeout_s=8.0):
        self.budget_s, self.timeout_s = budget_s, timeout_s
        self._tools, self._done = {}, {}
        self.calls = []

    def register(self, name, fn, schema=None, idempotent=False, filler="default"):
        self._tools[name] = {"fn": fn, "schema": schema or {}, "idempotent": idempotent, "filler": filler}

    def schemas(self):
        """LLM 에 넘길 도구 목록 — 함수 호출 프롬프트에 그대로 넣는다."""
        return [{"name": n, **t["schema"]} for n, t in self._tools.items()]

    def call(self, name, args, key=None):
        if name not in self._tools:
            c = ToolCall(name, args, key); c.error = f"모르는 도구: {name}"; self.calls.append(c); return c
        spec = self._tools[name]
        key = key or hashlib.sha1(f"{name}:{sorted(args.items())}".encode()).hexdigest()[:12]
        c = ToolCall(name, args, key)
        # 멱등 — "예약해 줘" 를 두 번 들어도 예약은 한 번이다
        if spec["idempotent"] and key in self._done:
            c.result, c.replayed = self._done[key], True
            self.calls.append(c); return c
        box = {}
        def run():
            try:
                box["r"] = spec["fn"](**args)
            except Exception as e:          # 도구의 예외는 대화를 죽이면 안 된다
                box["e"] = str(e)
        th = threading.Thread(target=run, daemon=True); t0 = time.perf_counter(); th.start()
        th.join(self.budget_s)
        if th.is_alive():                   # 예산 초과 — 먼저 말하고, 계속 기다린다
            c.filler = FILLERS.get(spec["filler"], FILLERS["default"])
            th.join(max(0.0, self.timeout_s - self.budget_s))
        c.elapsed_s = round(time.perf_counter() - t0, 3)
        if th.is_alive():
            c.error = "시간 초과"; c.result = "지금은 확인이 안 돼요. 잠시 뒤 다시 말씀해 주세요."
        elif "e" in box:
            c.error = box["e"]; c.result = "그 작업은 지금 처리하지 못했어요."
        else:
            c.result = box["r"]
            if spec["idempotent"]:
                self._done[key] = c.result
        self.calls.append(c)
        return c

    def speak_plan(self, call):
        """아바타가 말할 문장들, 순서대로. 채움말이 있으면 그것이 먼저다 (부록 L §3)."""
        out = []
        if call.filler:
            out.append(call.filler)
        out.append(str(call.result))
        return out


def _demo():
    def book_slot(when):
        time.sleep(1.6); return f"{when} 예약됐어요."
    def lookup(q):
        return f"'{q}' 기록은 없어요."
    r = ToolRouter(budget_s=1.2)
    r.register("book_slot", book_slot, {"description": "운동 예약", "params": {"when": "str"}}, idempotent=True, filler="book")
    r.register("lookup", lookup, {"description": "기록 조회", "params": {"q": "str"}}, filler="lookup")
    c = r.call("book_slot", {"when": "내일 19:00"}, key="u1:내일19")
    print("  말할 것:", r.speak_plan(c), f"({c.elapsed_s}s)")
    c2 = r.call("book_slot", {"when": "내일 19:00"}, key="u1:내일19")
    print("  같은 요청 재수신:", r.speak_plan(c2), "· 재실행 안 함:", c2.replayed)
    print("  빠른 도구:", r.speak_plan(r.call("lookup", {"q": "어제 스쿼트"})))


if __name__ == "__main__":
    _demo()

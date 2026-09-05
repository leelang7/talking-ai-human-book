# -*- coding: utf-8 -*-
"""
Ch26 회귀 테스트

가장 중요한 것은 **비밀이 새지 않는가** 다. 그리고 그 검사가 실제로
누출을 잡을 수 있는지도 같이 확인한다 — 아무것도 못 잡는 검사는
통과해도 의미가 없다. 그래서 **일부러 새게 만든 버전** 을 함께 돌린다.

    python test_multi.py
"""
import sys

sys.path.insert(0, __file__.rsplit("test_multi.py", 1)[0] or ".")

from engine import (JOBS, LOG_LINES, STANCE, TEMPLATED, Character,  # noqa: E402
                    Orchestrator, PHASES, Scene, brief, brief_leaky,
                    hidden_clue_leak, leak_scan, route)
from schedule import (CALL_SECONDS, ROUND_CALLS, WORKERS,  # noqa: E402
                      measure, parallel_seconds, round_calls,
                      sequential_seconds, speedup)

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def make():
    cast = [Character("민서", "조카", "유언장을 미리 봤다", "서재에 있었다", "culprit"),
            Character("도윤", "집사", "금고 비밀번호를 안다", "주방에 있었다"),
            Character("하린", "주치의", "약을 바꿔 처방했다", "정원에 있었다")]
    scene = Scene("저택 서재에서 회장이 숨진 채 발견됐다",
                  [("깨진 유리잔", True), ("찢긴 유언장 사본", False)],
                  [f"발언 {i}" for i in range(30)])
    return scene, cast


def main() -> int:
    print("\n  ── Ch26 멀티 아바타 ──")
    scene, cast = make()

    # ── §3 비밀 격리 ───────────────────────────────────────────────
    ok(leak_scan(scene, cast) == [], "★ 정상 브리핑에서 비밀이 새지 않는다 (§3)")
    ok(hidden_clue_leak(scene, cast) == [],
       "★ 아직 공개 안 된 단서가 컨텍스트에 없다 (§3 ④)")

    # **검사가 실제로 잡는지** — 못 잡는 검사는 통과해도 소용없다
    leaks = leak_scan(scene, cast, brief_leaky)
    ok(len(leaks) > 0, "한 줄 빠뜨린 버전에서는 누출이 잡힌다",
       f"{len(leaks)}건 — 검사가 살아 있다는 증거")
    ok(any(o == "민서" and w == "역할" for _, o, w in leaks),
       "범인의 역할이 다른 사람에게 노출된 것을 집어낸다")

    d = brief(scene, cast, "도윤")
    ok("유언장을 미리 봤다" not in d, "도윤의 컨텍스트에 민서의 비밀이 없다")
    ok("culprit" not in d, "도윤의 컨텍스트에 누가 범인인지가 없다")
    ok("금고 비밀번호를 안다" in d, "그러면서 본인 비밀은 들어 있다")
    ok("민서" in d and "조카" in d, "다른 인물의 이름·직업까지는 안다")

    # 범인 본인은 자기 역할을 알아야 한다 — 격리가 과하면 연기가 안 된다
    m = brief(scene, cast, "민서")
    ok(STANCE["culprit"] in m, "범인 본인에게는 범인이라는 입장이 주어진다 (§3)")
    ok(STANCE["culprit"] not in d, "다른 사람에게는 그 입장이 안 간다")

    # ⑤ 최근 발언만
    ok(d.count("발언 ") == LOG_LINES, f"발언 로그는 최근 {LOG_LINES}줄만 (§3 ⑤)",
       f"{d.count('발언 ')}줄 / 전체 30줄")
    ok("발언 0" not in d and "발언 29" in d, "오래된 것부터 잘린다")

    # 단서가 공개되면 그때 들어온다
    scene.clues[1] = ("찢긴 유언장 사본", True)
    ok("찢긴 유언장 사본" in brief(scene, cast, "도윤"),
       "공개된 뒤에는 단서가 컨텍스트에 들어온다")
    ok(hidden_clue_leak(scene, cast) == [], "공개 후에도 미공개 누출은 0 이다")

    # ── §2 진행자는 코드다 ─────────────────────────────────────────
    o = Orchestrator(cast)
    ok(o.phase == PHASES[0], "페이즈는 정해진 순서로 시작한다")
    ok([o.advance() for _ in PHASES[1:]] == list(PHASES[1:]), "페이즈가 순서대로 넘어간다")
    ok(o.advance() == PHASES[-1], "마지막 페이즈에서 더 가지 않는다")

    o = Orchestrator(cast)
    ok(o.next_speaker() == "민서", "지목이 없으면 순서대로")
    ok(o.next_speaker(mentioned="하린") == "하린", "이름이 불린 사람이 답한다 (§4)")
    ok(o.next_speaker(mentioned="하린", user_pick="도윤") == "도윤",
       "사용자 지목이 규칙보다 우선한다 (§4)")
    ok(o.next_speaker(user_pick="없는사람") == "민서", "없는 이름은 무시하고 규칙으로")

    # 같은 입력이면 같은 결과 — 결정론적이어야 한다 (§2)
    a = Orchestrator(cast)
    b = Orchestrator(cast)
    ok([a.next_speaker() for _ in range(5)] == [b.next_speaker() for _ in range(5)],
       "★ 진행 규칙이 결정론적이다 — LLM 진행자를 안 쓰는 이유 (§2)")

    # ── §5 안 부르는 자리 ──────────────────────────────────────────
    o = Orchestrator(cast)
    ok(o.speakers_this_turn("민서") == [], "브리핑 페이즈는 LLM 을 안 부른다 (템플릿)")
    o.advance()
    ok(o.speakers_this_turn("민서") == ["민서"], "토론에서는 말하는 한 명만 부른다")
    o.advance()
    ok(len(o.speakers_this_turn("민서")) == len(cast), "투표는 전원이 낸다")
    ok(round_calls(6, "brief") == 0 and round_calls(6, "vote") == 6,
       "페이즈별 호출 수가 규칙과 맞는다")

    ok(route("clue_notice")["model"] is None, "정형 멘트는 LLM 을 안 쓴다 (§5)")
    ok(all(route(j)["model"] is None for j in TEMPLATED), "템플릿 목록 전부 그렇다")
    ok(route("line")["model"] == "light" and route("vote")["model"] == "strong",
       "단순 대사는 가벼운 모델, 판단은 좋은 모델 (§5)")
    ok(all(v["max_tokens"] <= 150 for k, v in JOBS.items() if k != "scenario"),
       "대사는 전부 150 토큰 이하 — 여럿이 말하면 짧아야 리듬이 산다 (§5)")
    ok(JOBS["scenario"]["max_tokens"] == 850 and JOBS["scenario"]["temp"] == 1.0,
       "창작이 필요한 자리에만 여유를 준다", "850 토큰 · 온도 1.0")
    ok(JOBS["vote"]["temp"] < JOBS["line"]["temp"], "판단은 대사보다 온도가 낮다")

    # ── §5 병렬 ────────────────────────────────────────────────────
    ok(sequential_seconds() == 25.0, "순차 25초 (본문 §5)", f"{sequential_seconds():.0f}초")
    ok(parallel_seconds() == 5.0, "병렬 5초 (본문 §5)", f"{parallel_seconds():.0f}초")
    ok(round(speedup()) == 5, "5배 (본문 §5)", f"{speedup():.1f}배")
    ok(parallel_seconds(workers=1) == sequential_seconds(),
       "워커 1개면 순차와 같다 — 산식이 말이 된다")
    ok(parallel_seconds(workers=100) == CALL_SECONDS,
       "워커가 호출보다 많으면 한 파도로 끝난다")
    ok(parallel_seconds(n=26) > parallel_seconds(n=25),
       "호출이 파도를 넘으면 시간이 계단으로 뛴다", "26회는 6파도")

    m = measure(latency=0.02)
    ok(m["speedup"] > 2.5, "실제 스레드 풀에서도 빨라진다",
       f"{m['speedup']:.1f}배 (산식 {ROUND_CALLS / WORKERS:.0f}배)")
    ok(abs(m["seq"] - m["model_seq"]) < m["model_seq"] * 0.6,
       "실측이 산식에서 크게 벗어나지 않는다",
       f"실측 {m['seq']:.2f}초 vs 산식 {m['model_seq']:.2f}초")

    # ── 굶주림 방지 (turns.py 실험에서 잡힌 것) ──────────────────────────────
    o = Orchestrator(cast, max_silence=3); o.phase = "discuss"
    first = cast[0].name
    picks = []
    for _ in range(8):
        picks.append(o.next_speaker(mentioned=first)); o.turn += 1     # 계속 한 사람만 불린다
    ok(len(set(picks)) > 1, "★ 한 사람만 계속 불려도 다른 캐릭터가 끼어든다 (max_silence)", f"{picks}")
    o2 = Orchestrator(cast, max_silence=None); o2.phase = "discuss"
    ok(all(o2.next_speaker(mentioned=first) == first for _ in range(5)), "  방지를 끄면 옛 규칙 그대로")

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())

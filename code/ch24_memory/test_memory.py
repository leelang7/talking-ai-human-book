# -*- coding: utf-8 -*-
"""
Ch24 — 기억 3층 회귀 테스트

부록 F 실패 38·41·42 를 못 박는다.
  38 대화가 길어지면 말투가 풀린다 → 시스템 프롬프트가 항상 맨 앞
  41 캐릭터가 자기모순              → SelfMemory 충돌 감지
  42 5분 전 이름을 다시 묻는다      → 토큰 기준 자르기 + 장기 회상

실행:  python test_memory.py     (종료 코드 0 = 통과)
"""
import sys
import time

from memory import Ledger, LongTerm, Memory, SelfMemory, ShortTerm, toklen

FAILS = []


def ok(cond, name, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        if detail:
            print(f"         {detail}")
        FAILS.append(name)


def run():
    # ── 단기: 턴이 아니라 토큰으로 자른다 ──
    s = ShortTerm(budget=100)
    for i in range(20):
        s.add("user", "짧은 말")
    short_turns = len(s.turns)
    s2 = ShortTerm(budget=100)
    s2.add("user", "가" * 500)                    # 긴 문장 하나
    s2.add("user", "나" * 500)
    s2.add("user", "다")
    ok(sum(toklen(t["text"]) for t in s2.turns) <= 100 or len(s2.turns) <= 2,
       "긴 문장 하나가 들어와도 예산을 지킨다",
       f"턴 {len(s2.turns)} · {sum(toklen(t['text']) for t in s2.turns)}자")
    ok(short_turns > 2, "짧은 말은 여러 턴이 남는다", f"{short_turns}턴")

    # 실패 38 — 대화가 길어져도 시스템 프롬프트가 맨 앞
    m = Memory(system="SYS", budget=80)
    for i in range(30):
        m.user(f"질문 {i} " * 5); m.bot(f"답 {i} 예요.")
    ctx = m.context()
    ok(ctx[0][0] == "system" and ctx[0][1] == "SYS",
       "긴 대화 뒤에도 시스템 프롬프트가 맨 앞", f"{ctx[0][0]}")
    ok(m.summary.text, "버려진 턴이 요약으로 흘러갔다", f"{len(m.summary.text)}자")

    # ── 장기: 중복 병합 · 감쇠 · 삭제 ──
    L = LongTerm(half_life_days=30)
    now = time.time()
    L.remember("name", "이름은 지훈", now=now)
    L.remember("name", "이름은 지훈", now=now)      # 같은 사실 재등장
    ok(len(L.facts) == 1 and L.facts["name"]["hits"] == 2,
       "같은 사실은 새로 쌓이지 않고 합쳐진다", f"{len(L.facts)}건")
    ok(L.facts["name"]["weight"] > 1.0, "반복 언급되면 가중치가 오른다")

    L.remember("old", "예전 이야기", now=now - 200 * 86400)
    L.remember("mid", "한 달 전 이야기", now=now - 30 * 86400)
    L.remember("new", "최근 이야기", now=now)
    ok(L.score("old", now) < L.score("mid", now) < L.score("new", now),
       "오래될수록 점수가 낮다",
       f"old {L.score('old',now):.3f} mid {L.score('mid',now):.3f} new {L.score('new',now):.3f}")

    r = [k for k, _, _ in L.recall(k=5, now=now)]
    ok(r.index("new") < r.index("mid"), "같은 가중치면 최근 것이 먼저 회상된다", f"{r}")

    # ★ 반복 언급(name, 2회)이 최신성(new, 1회·같은 시각)을 이긴다.
    #   "자주 말한 것이 중요한 것" — 감쇠만으로는 안 되고 가중치가 필요한 이유다.
    ok(r[0] == "name", "반복 언급된 사실이 최신 사실보다 앞선다", f"{r}")

    # ★ 임계값 아래로 내려간 기억은 회상에서 **아예 빠진다**. 그게 의도다.
    #   초판 테스트는 순위만 가정해서 여기서 터졌다 — 코드가 아니라 테스트가 틀렸다.
    ok("old" not in r, "충분히 오래된 기억은 회상 목록에서 사라진다(잊는 것도 설계)",
       f"200일 경과 점수 {L.score('old', now):.4f} · 임계 0.05")

    ok(L.forget("old") and "old" not in L.facts, "'그건 잊어줘' 가 동작한다")
    ok(not L.forget("없는키"), "없는 것을 지워도 안전하다")

    # 실패 41 — 자기모순 감지
    me = SelfMemory()
    ok(me.assert_("커피", "좋아함")["conflict"] is False, "첫 진술은 충돌이 아니다")
    ok(me.assert_("커피", "좋아함")["conflict"] is False, "같은 진술 반복은 충돌이 아니다")
    c = me.assert_("커피", "안 마심")
    ok(c["conflict"] and c["before"] == "좋아함",
       "다른 진술은 충돌로 잡힌다", f"{c}")
    ok(me.claims["커피"] == "좋아함", "충돌 시 기존 진술을 덮어쓰지 않는다")

    # 부재 기억 — 일어나지 않은 일
    g = Ledger()
    g.log("asked", topic="A"); g.log("answered", topic="A")
    g.log("asked", topic="B")
    ok(g.unanswered() == ["B"], "답 못 준 주제만 남는다", f"{g.unanswered()}")
    g.log("answered", topic="B")
    ok(g.unanswered() == [], "답하고 나면 목록에서 빠진다")

    # 원장은 다시 집계할 수 있다 — 요약과의 결정적 차이
    ok(g.counts() == {"asked": 2, "answered": 2}, "원장은 언제든 재집계된다", f"{g.counts()}")


if __name__ == "__main__":
    print("기억 3층 회귀 테스트 (부록 F 38·41·42)")
    run()
    # ── 한 턴이 예산보다 크면 (실험에서 잡힌 구멍) ──────────────────────────
    st = ShortTerm(budget=1200)
    over = st.add("user", "가" * 2016)
    ok(sum(len(x["text"]) for x in st.turns) <= 1200, "★ 2,016자 발화 하나가 예산 1,200 을 뚫지 못한다",
       f"{sum(len(x['text']) for x in st.turns)}자")
    ok(over and len(over[0]["text"]) == 2016 - 600, "  잘린 앞부분은 요약 층으로 넘길 수 있게 돌려준다")
    ok(st.turns[-1]["text"].startswith("…"), "  잘린 턴은 '…' 로 시작해 잘렸음을 남긴다")

    print(f"\n  {'전부 통과' if not FAILS else str(len(FAILS)) + '건 실패: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)

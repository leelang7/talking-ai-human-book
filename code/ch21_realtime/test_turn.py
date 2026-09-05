# -*- coding: utf-8 -*-
"""
Ch21 회귀 테스트 — 네트워크 없이 검사되는 한 턴

    python test_turn.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from turn import ACTS, EMOS, FALLBACK, TTFA_BUDGET, make_turn, parse_tags  # noqa: E402

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def main() -> int:
    print("\n  ── Ch21 실시간 턴 ──")

    # ── ① 태그 파싱 ────────────────────────────────────────────────
    ok(parse_tags("[excited][wave] 안녕!") == ("excited", "wave", "안녕!"), "감정·동작 태그를 읽는다")
    ok(parse_tags("[wave][excited] 안녕!")[:2] == ("excited", "wave"),
       "★ 순서가 바뀌어도 감정은 감정, 동작은 동작으로 간다")
    ok(parse_tags("[happy] 안녕!") == ("happy", "none", "안녕!"), "태그가 하나뿐이면 나머지는 기본값")
    ok(parse_tags("그냥 말합니다.") == ("neutral", "none", "그냥 말합니다."), "태그가 없어도 죽지 않는다")
    ok(parse_tags("[bogus][wave] 안녕")[0] == "neutral", "★ 모르는 감정 태그는 버린다 — LLM 은 형식을 어긴다")
    ok(parse_tags("[a][b][c] x")[2] == "[c] x", "태그는 둘까지만 읽는다 — 셋째부터는 본문")
    ok(parse_tags("")[0] == "neutral" and parse_tags(None)[2] == "", "빈 입력·None 안전")
    ok("none" in ACTS and "neutral" in EMOS, "기본값이 목록 안에 있다")

    # ── ② 정규화 — 태그·이모지가 TTS 로 새지 않는다 ─────────────────
    r = make_turn("[happy][clap] 반가워요 😀 [wave] 진짜로!!", 0.4, 0.3, "/a.mp3")
    ok("[" not in r["reply"] and "😀" not in r["reply"],
       "★ 본문 안의 태그·이모지가 읽히지 않는다 (Ch03 §3 · Ch07)", r["reply"])
    ok(r["emotion"] == "happy" and r["action"] == "clap", "앞의 태그는 살아 있다")
    r = make_turn("[neutral][none] 하나. 둘. 셋. 넷.", 0.1, 0.1, "/a.mp3")
    ok(r["reply"] == "하나. 둘.", "두 문장까지 — 여럿이 말하면 짧아야 리듬이 산다")

    # ── ③ 폴백은 캐릭터여야 한다 (Ch22 §6) ─────────────────────────
    r = make_turn("", 4.0, 0.0, None)
    ok(r["fallback"] and r["reply"], "★ LLM 이 비면 폴백 문장을 낸다 — 침묵보다 낫다")
    ok(FALLBACK.startswith("[") and r["emotion"] in EMOS,
       "  폴백에도 감정 태그가 붙어 있다 — 폴백도 캐릭터다")
    ok(make_turn(None, 0, 0, None)["fallback"], "None 도 폴백")
    ok(not make_turn("[happy][nod] 네", 0.2, 0.2, "/a.mp3")["fallback"], "정상 응답은 폴백이 아니다")

    # ── ④ 지표 — Ch07 의 예산 ─────────────────────────────────────
    r = make_turn("[happy][nod] 네", 0.6, 0.5, "/a.mp3")
    ok(r["ttfa_sec"] == 1.1 and not r["over_budget"], "첫 소리까지 = LLM + TTS (순차)")
    r = make_turn("[happy][nod] 네", 1.6, 0.7, "/a.mp3")
    ok(r["over_budget"] and "예산 초과" in r["info"],
       f"★ {TTFA_BUDGET}초를 넘기면 info 에 표시된다 — 숨기지 않는다", r["info"])
    ok("LLM" in r["info"] and "TTS" in r["info"], "info 에 단계별 시간이 있다 (Ch07 §8)")
    ok(set(r) >= {"reply", "emotion", "action", "audio", "llm_sec", "tts_sec", "ttfa_sec"},
       "클라이언트가 필요한 키가 다 있다")

    # ── 겹침 경로: 첫 문장에서 멈춘다 (stream.first_sentence) ───────────────
    from stream import first_sentence
    s, n = first_sentence(iter(["[happy]", "[nod] ", "안녕", "하세요! ", "오늘도 ", "같이 해요."]))
    ok(s == "안녕하세요!" and n == 4, "★ 첫 종결부호에서 멈춘다 — 뒤 조각은 안 기다린다", f"{s!r} · {n}조각")
    s, n = first_sentence(iter(["[happy][nod] ", "네"]))
    ok(s == "네" and n == 2, "  종결부호가 없으면 받은 전부 (빈 문장으로 TTS 를 부르지 않는다)")
    s, _ = first_sentence(iter(["[greet][wave]안녕하세요, 오늘도 함께해요!"]))
    ok(s == "안녕하세요, 오늘도 함께해요!", "  태그 바로 뒤에 붙은 문장도 태그를 떼고 준다")

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())

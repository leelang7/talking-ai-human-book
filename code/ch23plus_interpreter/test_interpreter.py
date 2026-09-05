# -*- coding: utf-8 -*-
"""Ch23+ 회귀 테스트 — 통역기의 판단은 전부 네트워크 없이 검사한다."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from interpreter import (ALLOWED, STATES, Glossary, Session, latency_budget,   # noqa: E402
                         normalize_for_tts, numbers_preserved, segment, translate, voice_for)
from signbridge import KSL_VOCAB, coverage, sentence_to_signs, words_to_sentence   # noqa: E402

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def main():
    print("\n  ── Ch23+ 실시간 통역 ──")
    # 문장 분할
    d, r = segment("안녕하세요. 오늘 3.5km 걸었어요! 내일은")
    ok(d == ["안녕하세요.", "오늘 3.5km 걸었어요!"] and r == "내일은", "★ 완성된 문장만 넘기고 조각은 남긴다", f"{d} / {r!r}")
    ok(segment("Dr. Kim is here.")[0] == ["Dr. Kim is here."], "  약어 뒤 마침표는 문장 끝이 아니다")
    ok(segment("値段は3.5倍です。次は")[0] == ["値段は3.5倍です。"], "  일본어 종결 부호·소수점", str(segment("値段は3.5倍です。次は")))
    # 용어 잠금·숫자 보존
    g = Glossary({"올댓에이아이": "AllThatAI", "코치": "Coach"})
    ok(g.check("올댓에이아이의 코치입니다.", "I am the Coach of All That AI.") == ["AllThatAI"], "★ 잠금 용어가 빠지면 잡는다")
    ok(numbers_preserved("1,200원에 3.5km", "1200 won for 3.5 km") == [], "  쉼표 숫자는 같은 숫자로 본다")
    ok(numbers_preserved("12분 걸려요", "It takes twelve minutes") == ["12"], "★ 숫자를 말로 풀면 잡는다 — TTS 정규화는 우리 몫이다(Ch03)")
    # translate 계약 — 빠지면 한 번 더 부른다
    calls = []
    def llm(prompt):
        calls.append(prompt); return "It takes twelve minutes" if len(calls) == 1 else "It takes 12 minutes"
    out = translate("12분 걸려요", "ko", "en", llm, retries=1)
    ok(out == "It takes 12 minutes" and len(calls) == 2, "★ 숫자가 빠진 번역은 한 번 재시도한다", f"{len(calls)}회")
    ok("Include them" in calls[1], "  재시도 지시에 빠진 것을 명시한다")
    # 정규화·목소리
    ok(normalize_for_tts("3.5km 남았어요", "ko") == "삼점오 킬로미터 남았어요", "  한국어 대상은 Ch03 정규화를 거친다", normalize_for_tts("3.5km 남았어요", "ko"))
    ok(voice_for("ja").startswith("ja-JP") and voice_for("xx") == voice_for("en"), "  언어별 목소리 · 모르는 언어는 영어")
    # 상태 기계
    s = Session("ko", "en", llm=lambda p: "EN")
    ok(s.state == "idle" and all(v for v in ALLOWED.values()) and len(STATES) == 4, "  네 상태")
    done = s.hear("첫 문장입니다. 둘째")
    ok(done == ["첫 문장입니다."] and s.state == "listening" and s.spoken == [], "★ 듣는 동안은 말하지 않는다 — 자막만", f"{s.subtitles}")
    ok(s.subtitles == [("첫 문장입니다.", None)], "  원문 자막이 번역보다 먼저 뜬다")
    out = s.end_of_speech()
    ok(out == "EN" and s.state == "speaking" and s.spoken[0][0] == "첫 문장입니다." and len(s.queue) == 1, "★ 발화가 끝나면 첫 문장을 옮겨 말한다", f"큐 {len(s.queue)}")
    ok(s.subtitles[0] == ("첫 문장입니다.", "EN"), "  번역 자막이 원문 자막에 붙는다")
    s.hear("셋째 문장 시작")
    ok(s.state == "listening" and s.interrupted == 1, "★ 화자가 다시 말하면 아바타는 멈춘다", f"중단 {s.interrupted}")
    try:
        Session()._go("speaking"); bad = False
    except ValueError:
        bad = True
    ok(bad, "  허용 안 된 전이는 예외")
    ok(latency_budget()["total"] == 2.3, "  순차 통역 최소 지연 예산 0.8 + 1.0 + 0.5 = 2.3초")
    # 수어 브리지
    ok(len(KSL_VOCAB) == 20, "  인식기 어휘 20")
    tags, c = sentence_to_signs("누나가 노래하고 놀았어요")
    ok(tags == ["[sign:누나]", "[sign:노래]", "[sign:놀다]"] and c == 1.0, "★ 활용형·조사를 벗겨 어휘로 잇는다", str(tags))
    tags2, _ = sentence_to_signs("놀라운 힘들었어요")
    ok("[sign:놀다]" not in tags2 and "[sign:힘]" not in tags2, "★ 놀라운·힘들었어요 는 놀다·힘이 아니다", str(tags2))
    tags3, c3 = sentence_to_signs("병원이 어디예요")
    ok(all(t.startswith("[spell:") for t in tags3) and c3 == 0.0, "  어휘 밖은 지문자로 남긴다 — 빠뜨리지 않는다", str(tags3))
    ok(words_to_sentence(["누나", "NO_SIGN", "노래"]) == "누나 노래.", "  NO_SIGN 은 건너뛴다")
    ok(0 < coverage(["누나가 노래해요", "병원이 어디예요"]) < 1, "  덮음 비율은 0~1 사이")
    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())

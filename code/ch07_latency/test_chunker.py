# -*- coding: utf-8 -*-
"""
문장 청킹 회귀 테스트 (Ch07 §3)

이 테스트는 실제로 잡힌 버그에서 나왔다.
  초판 구현은 **첫 경계에서만** 자르려 해서, 짧은 문장이 앞에 오면
  (예: "네.") 거기 갇혀 한 문장도 못 내보냈다. 스트리밍이 통째로 죽는다.
  → min_chars 를 채우는 '가장 이른' 경계를 찾도록 고쳤다.

실행:  python test_chunker.py       (종료 코드 0 = 통과)
"""
import sys

from budget import normalize, stream_sentences

FAILS = []


def eq(got, want, name):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        print(f"         기대: {want}\n         실제: {got}")
        FAILS.append(name)


def run():
    eq(list(stream_sentences(iter(
        ["안녕", "하세요. ", "네.", " ", "오늘은 ", "날씨가 좋네요. ", "더 있어요."]))),
       ["안녕하세요.", "네. 오늘은 날씨가 좋네요."],
       "첫 청크는 즉시, 이후는 min_chars 까지 합친다")

    eq(list(stream_sentences(iter(["네. ", "응. ", "그렇군요. ", "알겠습니다. "]))),
       ["네.", "응. 그렇군요. 알겠습니다."],
       "짧은 첫 응답도 기다리지 않는다 (TTFA 우선)")

    eq(list(stream_sentences(iter(["종결부호가 없는 긴 문장이 하나 들어옵니다"]))),
       ["종결부호가 없는 긴 문장이 하나 들어옵니다"],
       "종결부호가 없어도 끝에 한 번은 내보낸다")

    eq(list(stream_sentences(iter(
        ["첫 번째 문장입니다. ", "두 번째 문장입니다. ", "세 번째는 잘려야 합니다. "]))),
       ["첫 번째 문장입니다.", "두 번째 문장입니다."],
       "max_sentences 를 넘으면 끊는다")

    eq(list(stream_sentences(iter([""]))), [], "빈 입력은 아무것도 내지 않는다")

    eq(list(stream_sentences(iter(["정말요?", " ", "네 맞습니다!"]))),
       ["정말요?", "네 맞습니다!"],
       "물음표·느낌표도 경계다")

    # ── 점이 전부 문장 끝은 아니다 (Ch07 §3) ──
    #
    # 스트리밍은 뒤에 무엇이 올지 모른 채 "이 점이 문장 끝인가" 를 정해야 한다.
    # Ch07 본문이 이 세 경우를 들고 있는데, 처음에는 **테스트도 처리도 없었다.**
    # `Dr. Kim` 이 "Dr." 과 "Kim…" 으로 잘려 TTS 로 따로 나갔다.
    def stream(text, n=3):
        toks = [text[i:i + n] for i in range(0, len(text), n)]
        return list(stream_sentences(iter(toks), min_chars=1, max_sentences=9))

    eq(stream("원주율은 3.14 입니다. 다음 문장."),
       ["원주율은 3.14 입니다.", "다음 문장."],
       "소수점은 경계가 아니다 (점 뒤에 공백이 없다)")
    eq(stream("Dr. Kim 이 왔습니다. 다음 문장."),
       ["Dr. Kim 이 왔습니다.", "다음 문장."],
       "★ 약어 뒤의 점은 경계가 아니다 — 'Dr.' 만 따로 읽지 않는다")
    eq(stream("Mr. Lee 와 Prof. Park 이 e.g. 이렇게. 끝."),
       ["Mr. Lee 와 Prof. Park 이 e.g. 이렇게.", "끝."],
       "약어 여럿이 한 문장에 있어도 한 덩어리다")
    eq(stream("생각해 보니... 그렇네요. 다음 문장."),
       ["생각해 보니...", "그렇네요.", "다음 문장."],
       "말줄임표에서는 끊는다 — 생각이 끊긴 자리라 허용한다")
    eq(stream("네! 그렇습니다? 좋아요~ 끝."),
       ["네!", "그렇습니다?", "좋아요~", "끝."],
       "느낌표·물음표·물결은 약어 예외 없이 경계다")

    # ── 정규화 (Ch03 §4, Ch20 §7) ──
    eq(normalize("[excited][wave] 반가워요 (진짜로)!"), "excited wave 반가워요 진짜로 !",
       "대괄호·괄호는 제거되어 TTS 가 읽지 않는다")
    eq(normalize(""), "네.", "빈 문자열은 안전한 기본값")
    eq(normalize("하나. 둘. 셋. 넷."), "하나. 둘.", "정규화도 두 문장까지")


if __name__ == "__main__":
    print("문장 청킹 회귀 테스트")
    run()
    print(f"\n  {'전부 통과' if not FAILS else str(len(FAILS)) + '건 실패: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)

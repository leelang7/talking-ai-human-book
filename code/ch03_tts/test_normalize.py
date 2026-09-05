# -*- coding: utf-8 -*-
"""Ch03 §7 정규화 — 운영에서 실제로 틀렸던 읽기 하나하나가 테스트다."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize_ko import normalize, num_ko, nat_ko   # noqa: E402

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def N(s):
    return normalize(s, english=False)


def main():
    print("\n  ── Ch03 텍스트 정규화 ──")
    ok(N("AI") == "에이아이", "★ AI → 에이아이 (엔진은 '아이' 로 읽었다)", N("AI"))
    ok(N("10개") == "열 개", "★ 수분류사 앞은 고유어: 10개 → 열 개", N("10개"))
    ok(N("15분") == "십오분", "  분 은 한자어: 15분 → 십오분", N("15분"))
    ok(N("3.5배") == "삼점오배", "★ 소수: 3.5배 → 삼점오배", N("3.5배"))
    ok(N("20살") == "스무 살", "  20 은 스물이 아니라 스무", N("20살"))
    ok(N("1만 명") == "만 명", "★ 1만 → 만 (일만 아님)", N("1만 명"))
    ok(N("1,000원") == "천원", "  천 단위 쉼표 제거: 1,000원 → 천원", N("1,000원"))
    ok(N("5km") == "오 킬로미터", "  단위 사전: 5km → 오 킬로미터", N("5km"))
    ok(N("50%") == "오십퍼센트", "  % → 퍼센트", N("50%"))
    ok(num_ko("123456789") == "일억이천삼백사십오만육천칠백팔십구", "  만 단위 묶음", num_ko("123456789"))
    ok(num_ko("0") == "영" and num_ko("2.05") == "이점영오", "  0 과 소수의 0")
    ok(N("10개월") == "십개월", "★ 개월 은 개 가 아니다 (부정 전방탐색)", N("10개월"))
    ok(N("3번지") == "삼번지", "  번지 는 번 이 아니다", N("3번지"))
    ok(N("12시") == "열두 시" and N("12시간") == "열두 시간", "  시·시간은 고유어", N("12시"))
    ok(nat_ko(99) == "아흔아홉", "  99 → 아흔아홉")
    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
교재 적합성 검토 — 분량 · 진입 경로 · 희소성

인사이트 감사(insight_audit)가 '팔릴 만한가'를 봤다면, 이건 '교재로 쓸 만한가'를 본다.
교재의 기준은 세 가지다.

  1. 분량   — 한 학기/한 권에 뗄 수 있는가. 계획 대비 얼마나 벌어졌는가.
  2. 진입   — 첫 성공까지 몇 쪽인가. 실습 코드가 실제로 있는가.
  3. 희소성 — 검색으로 못 얻는 내용이 어디에 몰려 있는가.

실행:  python scripts/book_review.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT, APPDIR, CODE = (os.path.join(ROOT, "draft"),
                       os.path.join(ROOT, "draft", "appendix"),
                       os.path.join(ROOT, "code"))
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from _pages import CHARS_PER_PAGE, printed_chars   # 산정은 한 곳에서만
TARGET_PAGES = 265            # 기획안 §11

PARTS = [("Part 1 해부", range(1, 6)), ("Part 2 지연", range(6, 10)),
         ("Track A 실사", range(10, 16)), ("Track B 무GPU", range(16, 22)),
         ("Track C 인격", range(22, 28)), ("Part 4 내보내기", range(28, 31))]


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def chapters():
    out = []
    for fn in sorted(os.listdir(DRAFT)):
        m = re.match(r"ch(\d+)(plus)?_", fn)
        if m and fn.endswith(".md"):
            out.append((int(m.group(1)) + (0.5 if m.group(2) else 0), fn,
                        read(os.path.join(DRAFT, fn))))
    return sorted(out)


def main():
    chs = chapters()
    apps = [(f, read(os.path.join(APPDIR, f))) for f in sorted(os.listdir(APPDIR))
            if f.startswith("app") and f.endswith(".md")]
    front = [(f, read(os.path.join(DRAFT, f))) for f in sorted(os.listdir(DRAFT))
             if re.match(r"0\d_", f) and f.endswith(".md")]   # _ 시작 = 집필자용, 제외

    body = sum(printed_chars(t) for _, _, t in chs)
    appc = sum(printed_chars(t) for _, t in apps)
    frontc = sum(printed_chars(t) for _, t in front)
    total = body + appc + frontc

    print("■ 1. 분량 — 한 권에 담기는가\n")
    print(f"  {'구분':<16}{'글자':>10}{'쪽':>12}")
    for name, cs in (("프론트", frontc),
                     (f"본문 {len(chs)}장", body),
                     (f"인쇄 부록 {len(apps)}종", appc)):
        print(f"  {name:<16}{cs:>10,}{cs/CHARS_PER_PAGE:>11.0f}p")
    print(f"  {'─'*38}")
    print(f"  {'합계':<16}{total:>10,}{total/CHARS_PER_PAGE:>11.0f}p")
    over = total / CHARS_PER_PAGE / TARGET_PAGES
    print(f"\n  기획 목표 {TARGET_PAGES}p → 현재 {total/CHARS_PER_PAGE:.0f}p "
          f"(**{over:.1f}배**)")
    if over > 1.3:
        print(f"  [FAIL] 계획 대비 {over:.1f}배. 한 권으로 못 냅니다.")

    print("\n■ 2. 파트별 균형\n")
    for name, rng in PARTS:
        cs = sum(printed_chars(t) for n, _, t in chs if int(n) in rng)
        print(f"  {name:<18}{cs:>8,}자{cs/CHARS_PER_PAGE:>7.0f}p")

    print("\n■ 3. 진입 경로 — 첫 성공까지\n")
    first = [(n, t) for n, _, t in chs if n <= 3]
    upto = frontc + sum(printed_chars(t) for _, t in first)
    print(f"  프론트+Ch01~03 = {upto:,}자 ≈ {upto/CHARS_PER_PAGE:.0f}p")
    print(f"  → 독자가 첫 결과물을 보기까지 읽어야 하는 분량")

    print("\n■ 4. 실습 코드 실재 여부\n")
    promised = set()
    for _, _, t in chs:
        promised |= set(re.findall(r"`code/([a-z0-9_]+)/`", t))
    exists = {d for d in os.listdir(CODE)
              if os.path.isdir(os.path.join(CODE, d)) and not d.startswith("_")}
    missing = sorted(promised - exists)
    print(f"  약속한 폴더 {len(promised)}개 · 실재 {len(promised & exists)}개 "
          f"· **없음 {len(missing)}개**")
    if missing:
        print(f"  없는 것: {', '.join(missing[:12])}{' …' if len(missing) > 12 else ''}")
        print(f"  [FAIL] 시리즈 5대 입장 중 '책↔코드 1:1' 이 지켜지지 않음")

    print("\n■ 5. 희소성이 어디 있나 — 검색 불가 자산의 분포\n")
    RARE = re.compile(r"저자[는가의]|실측|버렸습니다|폐기|실패했|며칠을|"
                      r"하늘이|홈런이|코치|바텐더|사투리|AI-Hub|800시간|28차시")
    for name, rng in PARTS:
        sel = [(n, t) for n, _, t in chs if int(n) in rng]
        hits = sum(len(RARE.findall(t)) for _, t in sel)
        cs = sum(printed_chars(t) for _, t in sel)
        d = hits / (cs / 10000) if cs else 0
        bar = "█" * int(d * 2)
        print(f"  {name:<18}{d:>5.1f}/만자  {bar}")
    for f, t in apps:
        d = len(RARE.findall(t)) / (len(t) / 10000)
        if d > 6:
            print(f"  {'부록 ' + f[3:4]:<18}{d:>5.1f}/만자  {'█' * int(d*2)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

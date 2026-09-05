# -*- coding: utf-8 -*-
"""
인사이트 밀도 감사 — "이 장은 왜 돈을 내고 사야 하는가"

전제: 독자가 돈을 내는 이유는 **검색으로 안 나오는 것** 때문이다.
     검색하면 나오는 일반론은 아무리 잘 써도 책의 판매 근거가 되지 못한다.

그래서 문단을 네 종류로 분류한다.

  실측(M)  구체적 수치 + 단위. 저자가 재지 않으면 나올 수 없는 것.
  실패(F)  1인칭 시행착오. 남의 실패는 검색으로 안 나온다.
  사례(C)  이 프로젝트 고유의 고유명·구성. 등장인물·ATL·사투리 등.
  판단(J)  "이럴 땐 이걸 고르라"는 결정 규칙. 경험이 있어야 쓸 수 있다.
  ─ 위 넷 중 아무것도 아니면 일반론(G).

일반론 자체가 나쁜 게 아니다. 다리 역할이 필요하다.
다만 **일반론 비중이 높은 장은 대체 가능** 하고, 그 장이 많으면 책이 안 팔린다.

실행:  python scripts/insight_audit.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT = os.path.join(ROOT, "draft")

# 실측 — 단위가 붙은 구체적 수치
RE_M = re.compile(r"\d[\d,.]*\s*(?:초|분|시간|배|%|fps|GB|MB|KB|ms|밀리초|자|원|장|명|발화|프레임|×)")
# 실패 — 1인칭 시행착오 (문체가이드 원칙3)
RE_F = re.compile(r"저자[는가]?\s*(?:실제로\s*)?(?:겪|밟|잃|버렸|썼|시도)|"
                  r"버렸습니다|폐기|실패했|안 됐|망가|틀렸|되돌|무너졌|"
                  r"며칠을|반나절을|그날 배운|고쳤습니다|잡았습니다")
# 사례 — 이 책 고유의 고유명 + **1차 자료 표지**
#   "저자의 ~엔진은 이렇게 한다" 는 검색으로 안 나온다. 고유명이 없어도 1차 자료다.
RE_C = re.compile(r"하늘이|홈런이|코치|바텐더|마을 사람들|사투리|어댑터 핫스왑|"
                  r"AllThatLink|AI-Hub|팔도|경상도|전라도|800시간|28차시|KDT|"
                  r"저자[의가는]|실측|실제로 겪|실운영|배포 코드|이 책의")
# 판단 — 결정 규칙
RE_J = re.compile(r"고르세요|고릅니다|쓰세요|하지 마세요|권합니다|정답은|"
                  r"기준은|판단 기준|결정 트리|~면 .{0,12}(?:이고|입니다).{0,20}~면|"
                  r"대신|반대로 .{0,10}면|둘 중")


def classify(p):
    tags = ""
    if RE_M.search(p):
        tags += "M"
    if RE_F.search(p):
        tags += "F"
    if RE_C.search(p):
        tags += "C"
    if RE_J.search(p):
        tags += "J"
    return tags or "G"


def paragraphs(t):
    body = t.split("\n", 1)[1] if "\n" in t else t
    out = []
    for p in re.split(r"\n\s*\n", body):
        p = p.strip()
        if len(p) < 60:                       # 제목·구분선·짧은 줄 제외
            continue
        if p.startswith(("```", "#", "---", "> **실습", "> **예상", "> **관련")):
            continue
        # ★ 표를 버리면 안 된다 — 결정표·실측표가 이 책에서 가장 밀도 높은 내용이다.
        #   초판 분류기는 '|' 로 시작하는 블록을 통째로 제외해 Ch26 개선을 못 잡았다.
        out.append(p)
    return out


def main():
    rows = []
    for fn in sorted(os.listdir(DRAFT)):
        m = re.match(r"ch(\d+)(plus)?_", fn)
        if not (m and fn.endswith(".md")):
            continue
        n = int(m.group(1)) + (0.5 if m.group(2) else 0)
        with open(os.path.join(DRAFT, fn), encoding="utf-8") as f:
            ps = paragraphs(f.read())
        if not ps:
            continue
        cnt = {"M": 0, "F": 0, "C": 0, "J": 0, "G": 0}
        for p in ps:
            tg = classify(p)
            if tg == "G":
                cnt["G"] += 1
            else:
                for c in tg:
                    cnt[c] += 1
        uniq = len([p for p in ps if classify(p) != "G"])
        rows.append((n, fn, len(ps), cnt, uniq / len(ps)))

    rows.sort(key=lambda r: r[4])
    print("장별 인사이트 밀도 — 고유 문단 비율 오름차순 (낮을수록 대체 가능)\n")
    print(f"  {'장':<8}{'문단':>5}{'실측':>5}{'실패':>5}{'사례':>5}{'판단':>5}{'일반론':>7}{'고유율':>8}")
    for n, fn, tot, c, r in rows:
        flag = "  ← 대체 위험" if r < 0.45 else ("  ★" if r >= 0.75 else "")
        print(f"  Ch{n:<6g}{tot:>5}{c['M']:>5}{c['F']:>5}{c['C']:>5}{c['J']:>5}{c['G']:>7}{r:>7.0%}{flag}")

    tot_p = sum(r[2] for r in rows)
    tot_u = sum(int(r[4] * r[2]) for r in rows)
    print(f"\n  전체 {tot_p}문단 중 고유 {tot_u} — 평균 고유율 {tot_u/tot_p:.0%}")
    weak = [f"Ch{n:g}" for n, _, _, _, r in rows if r < 0.45]
    print(f"  대체 위험 장 {len(weak)}개: {', '.join(weak) if weak else '없음'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

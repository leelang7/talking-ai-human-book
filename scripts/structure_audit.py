# -*- coding: utf-8 -*-
"""
체계성·중복 감사 — 장의 뼈대가 같은가, 참조가 실재하는가, 같은 말을 두 번 하는가

qc.py 가 순서·참조·문체를 보고 prune_audit.py 가 문장 단위 중복을 본다면, 이것은 그 사이를 본다.

  ① 뼈대     장마다 같은 골격인가 — h1 'Ch{n}. 제목', 절 번호 n.1…n.k 연속, 마지막 절 '이 장에서 기억할 것',
              끝의 '실습 코드' 상자, 장 첫 문단의 구체성(숫자·사건)
  ② 참조     'Ch12 §4' 가 가리키는 절이 실제로 있는가 · '부록 X' 가 있는가 · '그림/표 n.m' 이 있는가
  ③ 용어     같은 것을 다른 말로 부르는가 (립싱크/립 싱크, 리타게팅/리타겟팅 …) — 소수 표기를 목록으로
  ④ 문단 중복 두 파일에 걸쳐 거의 같은 문단(80자 이상, 유사도 0.75 이상)

    python scripts/structure_audit.py            요약 + 목록
    python scripts/structure_audit.py --strict   ①②④ 에 하나라도 걸리면 종료코드 1
"""
import difflib
import glob
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT = os.path.join(ROOT, "draft")

TERMS = [  # (정규형, 이형들) — 정규형이 아닌 표기를 센다
    ("립싱크", ["립 싱크", "립싱킹", "lip sync", "lipsync", "립-싱크"]),
    ("리타게팅", ["리타겟팅", "리타케팅", "리타깃팅", "retargeting"]),
    ("드라이버 영상", ["드라이빙 영상", "구동 영상"]),
    ("페르소나", ["퍼소나"]),
    ("아이들 루프", ["idle 루프", "유휴 루프", "아이들루프"]),
    ("끼어들기", ["바지인", "barge-in", "바지-인"]),
    ("텍스트 정규화", ["텍스트 노멀라이제이션"]),
    ("실측", ["실 측정"]),
    ("웹소켓", ["WebSocket", "websocket", "웹 소켓"]),
]


def files():
    ch = sorted(glob.glob(os.path.join(DRAFT, "ch*.md")))
    ap = sorted(glob.glob(os.path.join(DRAFT, "appendix", "*.md")))
    fr = sorted(glob.glob(os.path.join(DRAFT, "00_*.md")))
    return fr, ch, ap


def body(text):
    out, incode = [], False
    for ln in text.split("\n"):
        if ln.strip().startswith("```"):
            incode = not incode
            continue
        if not incode:
            out.append(ln)
    return "\n".join(out)


def label_of(path):
    m = re.match(r"ch(\d+)(plus)?_", os.path.basename(path))
    return (m.group(1).lstrip("0") + ("+" if m.group(2) else "")) if m else None


def sections(text):
    return [m.group(1) for m in re.finditer(r"^## (\S+)", body(text), re.M)]


def audit():
    fr, ch, ap = files()
    findings = defaultdict(list)
    secmap, figs, tabs = {}, defaultdict(set), defaultdict(set)
    app_letters = set(re.match(r"app([A-Z])", os.path.basename(p)).group(1) for p in ap)

    # ① 뼈대
    for p in ch:
        lab = label_of(p)
        t = open(p, encoding="utf-8").read()
        b = body(t)
        name = os.path.basename(p)
        h1 = re.search(r"^# +(Ch\S+?)\.?\s+(.+)$", b, re.M)
        if not h1:
            findings["뼈대"].append(f"{name}: h1 'Ch{lab}. 제목' 없음")
        secs = sections(t)
        nums = []
        for s in secs:
            m = re.match(r"(\d+\+?)\.(\d+)$", s)
            if not m or m.group(1) != lab:
                findings["뼈대"].append(f"{name}: 절 번호 이상 '{s}' (장 {lab})")
            else:
                nums.append(int(m.group(2)))
        if nums != list(range(1, len(nums) + 1)):
            findings["뼈대"].append(f"{name}: 절 번호 불연속 {nums}")
        secmap[lab] = set(nums)
        last = re.findall(r"^## \S+ (.+)$", b, re.M)
        if lab == "30":                                   # 마지막 장은 '마지막 한 줄' 로 닫는다 — 일부러
            pass
        elif not last or "기억할 것" not in last[-1]:
            findings["뼈대"].append(f"{name}: 마지막 절이 '이 장에서 기억할 것' 이 아님 ('{last[-1] if last else ''}')")
        if "**실습 코드**" not in t:
            findings["뼈대"].append(f"{name}: 끝의 '실습 코드' 상자 없음")
        # 첫 문단 구체성 — h1 뒤 첫 세 문장에 숫자나 등장인물이 있는가
        after = b.split("\n", 1)[1] if "\n" in b else ""
        first = " ".join([ln for ln in after.split("\n") if ln.strip() and not ln.startswith(("#", "|", ">", "!", "표:"))][:2])
        if not re.search(r"\d|하늘이|홈런이|코치|바텐더|마을 사람들|민트|저자|저는|제가|\"|“|「", first[:240]):
            findings["첫문단"].append(f"{name}: '{first.lstrip('- ')[:60]}…'")   # 참고 목록 — 사람이 읽고 판단
        for m in re.finditer(r"!\[", b):
            figs[lab].add(1)
        for i, _ in enumerate(re.finditer(r"^표: ", b, re.M), 1):
            tabs[lab].add(i)
        for i, _ in enumerate(re.finditer(r"^!\[", b, re.M), 1):
            figs[lab].add(i)

    # ② 참조
    for p in fr + ch + ap:
        name = os.path.basename(p)
        b = body(open(p, encoding="utf-8").read())
        for m in re.finditer(r"Ch0?(\d+\+?)\s*§\s*(\d+)", b):
            lab, sec = m.group(1), int(m.group(2))
            if lab in secmap and sec not in secmap[lab]:
                findings["참조"].append(f"{name}: Ch{lab} §{sec} — 그 절 없음 (있는 절 1~{max(secmap[lab]) if secmap[lab] else 0})")
            elif lab not in secmap:
                findings["참조"].append(f"{name}: Ch{lab} — 그 장 없음")
        for m in re.finditer(r"부록 ([A-Z])(?![A-Za-z])", b):
            if m.group(1) not in app_letters and m.group(1) not in "IJK":   # I·J·K 는 온라인 부록
                findings["참조"].append(f"{name}: 부록 {m.group(1)} — 없음")
        for m in re.finditer(r"(그림|표) (\d+\+?)\.(\d+)", b):
            lab, n = m.group(2), int(m.group(3))
            pool = figs if m.group(1) == "그림" else tabs
            if lab in secmap and n not in pool.get(lab, set()):
                findings["참조"].append(f"{name}: {m.group(0)} — 그 번호 없음")

    # ③ 용어
    for p in fr + ch + ap:
        b = body(open(p, encoding="utf-8").read())
        for canon, variants in TERMS:
            for v in variants:
                c = len(re.findall(r"(?<![(（/·])(?<!— )" + re.escape(v), b))   # '끼어들기(barge-in)' 처럼 괄호 안 원어 표기는 허용
                if c:
                    findings["용어"].append(f"{os.path.basename(p)}: '{v}' {c}회 → '{canon}'")

    # ④ 문단 중복 (파일 간)
    paras = []
    for p in fr + ch + ap:
        b = body(open(p, encoding="utf-8").read())
        for para in re.split(r"\n\s*\n", b):
            q = re.sub(r"[\s*_`>]+", "", para)
            if len(q) >= 80 and not para.lstrip().startswith(("|", "#", "!", "표:")):
                paras.append((os.path.basename(p), q, para.strip()[:70]))
    # 빠른 후보: 앞 24자 같은 것 + 난수 표본 대신 전수 비교(문단 수 ~2천 → 200만 비교는 무겁다) → 12자 셔글 색인
    index = defaultdict(list)
    for i, (f, q, _) in enumerate(paras):
        for k in range(0, min(len(q) - 12, 120), 12):
            index[q[k:k + 12]].append(i)
    cand = set()
    for ids in index.values():
        if len(ids) > 1:
            for a in ids:
                for b2 in ids:
                    if a < b2 and paras[a][0] != paras[b2][0]:
                        cand.add((a, b2))
    for a, b2 in sorted(cand):
        r = difflib.SequenceMatcher(None, paras[a][1], paras[b2][1]).ratio()
        if r >= 0.75:
            findings["중복"].append(f"{paras[a][0]} ↔ {paras[b2][0]}  {r:.2f}  '{paras[a][2]}…'")
    return findings


def main():
    strict = "--strict" in sys.argv
    f = audit()
    print("\n  체계성·중복 감사\n")
    for cat in ("뼈대", "참조", "용어", "중복", "첫문단"):
        items = f.get(cat, [])
        print(f"  {cat:<4} {len(items):>3}건")
        for it in items[:40]:
            print("     ", it)
    bad = sum(len(f.get(c, [])) for c in ("뼈대", "참조", "중복"))
    print()
    if strict and bad:
        print(f"  ✗ 뼈대·참조·중복 {bad}건\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

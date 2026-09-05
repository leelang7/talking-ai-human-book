# -*- coding: utf-8 -*-
"""
잉여 감사 — 무엇을 지울 것인가

분량이 목표를 넘을 때 **고르게 줄이면 안 된다.** 좋은 문단과 잉여 문단을
같은 비율로 깎으면 밀도가 그대로다. 잉여만 찾아서 지워야 한다.

찾는 것 넷:

  ① 같은 말을 두 장에서      — 문장 단위 중복
  ② 상투구                  — 아무 정보도 안 나르는 연결 문구
  ③ 자기 인용 과다           — "앞에서 봤듯이" 류가 몰린 곳
  ④ 고아 파일               — 원고 어디서도 참조되지 않는 것

지우자는 판단까지는 하지 않는다. **후보를 세어서 보여줄 뿐이다.**

    python scripts/prune_audit.py
    python scripts/prune_audit.py --dup      중복만
"""
import glob
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT = os.path.join(ROOT, "draft")

# 정보를 나르지 않는 연결 문구. 지워도 문단이 그대로 성립하는 것들.
FILLER = [
    "결론부터 말하면", "다시 말해", "요컨대", "말하자면",
    "중요한 것은", "핵심은", "이것이 핵심입니다",
    "앞서 말했듯이", "앞에서 봤듯이", "앞에서 본 것처럼", "이미 말했듯이",
    "다시 강조하지만", "한 번 더 말하면", "거듭 말하지만",
    "당연하게도", "물론입니다", "말할 것도 없이",
]
# 한 장 안에서 이 횟수를 넘으면 자기 인용이 과하다
SELFREF_LIMIT = 6
SELFREF = re.compile(r"(앞[서에]|이미|다시)\s*(말|보|다루|살펴)")

STOP = re.compile(r"^(#|\||```|>|!\[|\s*[-*]\s)")


def chapters():
    for p in sorted(glob.glob(os.path.join(DRAFT, "ch*.md"))):
        yield os.path.basename(p)[:-3], open(p, encoding="utf-8").read()


def sentences(text):
    """본문 문장만. 표·코드·인용·도판은 뺀다 — 거기는 중복이 정상이다."""
    out, incode = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            incode = not incode
            continue
        if incode or STOP.match(line) or not line.strip():
            continue
        for s in re.split(r"(?<=[.다요])\s+", line.strip()):
            s = re.sub(r"[*`_]", "", s).strip()
            if len(s) >= 24:
                out.append(s)
    return out


def norm(s):
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", s)


def find_dups():
    seen = defaultdict(list)
    for name, text in chapters():
        for s in sentences(text):
            k = norm(s)
            if len(k) >= 18:
                seen[k].append((name, s))
    dups = []
    for k, hits in seen.items():
        chs = {c for c, _ in hits}
        if len(chs) > 1:                      # 서로 다른 장에서 같은 문장
            dups.append((sorted(chs), hits[0][1], len(hits)))
    return sorted(dups, key=lambda d: -len(d[1]))


def find_filler():
    hits = defaultdict(list)
    for name, text in chapters():
        for f in FILLER:
            n = text.count(f)
            if n:
                hits[name].append((f, n))
    return hits


def find_selfref():
    out = []
    for name, text in chapters():
        n = len(SELFREF.findall(text))
        if n > SELFREF_LIMIT:
            out.append((name, n))
    return sorted(out, key=lambda x: -x[1])


def find_orphans():
    """목차에 없는 장 · 어디서도 안 쓰이는 도판.

    파일명으로 찾으면 둔하다 — 원고는 파일명이 아니라 **장 레이블**로 서로를
    가리킨다. 그래서 `Ch03+` 같은 레이블이 목차에 있는지를 본다.
    실제로 이 검사가 Ch03+ 가 목차 표에서 빠진 것을 잡았다.
    """
    toc_path = os.path.join(DRAFT, "01_목차.md")
    toc = open(toc_path, encoding="utf-8").read() if os.path.exists(toc_path) else ""
    missing = []
    for p in sorted(glob.glob(os.path.join(DRAFT, "ch*.md"))):
        m = re.match(r"ch(\d+)(plus)?_", os.path.basename(p))
        if not m:
            continue
        label = f"Ch{m.group(1)}" + ("+" if m.group(2) else "")
        # 표의 첫 칸에 있어야 한다 — 본문에서 스쳐 언급된 것은 목차가 아니다
        if not re.search(r"^\|\s*" + re.escape(label) + r"\s*\|", toc, re.M):
            missing.append((label, os.path.basename(p)))

    corpus = ""
    for q in glob.glob(os.path.join(DRAFT, "**", "*.md"), recursive=True):
        corpus += open(q, encoding="utf-8").read()
    unused = [os.path.basename(f) for f in glob.glob(os.path.join(DRAFT, "figures", "*"))
              if os.path.basename(f) not in corpus]
    return missing, unused


def sizes():
    rows = []
    for name, text in chapters():
        body = len(re.sub(r"\s", "", text))
        rows.append((name, body))
    avg = sum(b for _, b in rows) / max(1, len(rows))
    return sorted(rows, key=lambda r: -r[1]), avg


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    print()

    if only in (None, "--dup"):
        dups = find_dups()
        print(f"  ① 장을 넘나드는 중복 문장 — {len(dups)}건")
        for chs, s, n in dups[:12]:
            print(f"     {'·'.join(chs)}")
            print(f"       {s[:70]}")
        if len(dups) > 12:
            print(f"     … 외 {len(dups) - 12}건")
        print()
    if only == "--dup":
        return 0

    fill = find_filler()
    total = sum(n for v in fill.values() for _, n in v)
    print(f"  ② 상투구 — {total}회 / {len(fill)}개 장")
    for name in sorted(fill, key=lambda k: -sum(n for _, n in fill[k]))[:6]:
        items = ", ".join(f"{f}×{n}" for f, n in sorted(fill[name], key=lambda x: -x[1])[:3])
        print(f"     {name:28} {sum(n for _, n in fill[name]):>2}회   {items}")
    print()

    sref = find_selfref()
    print(f"  ③ 자기 인용 과다 (>{SELFREF_LIMIT}회) — {len(sref)}개 장")
    for name, n in sref[:6]:
        print(f"     {name:28} {n}회")
    print()

    missing, unused = find_orphans()
    print(f"  ④ 목차 표에 없는 장 — {len(missing)}건 · 안 쓰이는 도판 — {len(unused)}건")
    for label, fn in missing:
        print(f"     {label:8} {fn}")
    for fn in unused:
        print(f"     (도판) {fn}")
    print()

    rows, avg = sizes()
    over = [(n, b) for n, b in rows if b > avg * 1.5]
    print(f"  ⑤ 평균의 1.5배를 넘는 장 — {len(over)}개 (평균 {avg:,.0f}자)")
    for n, b in over:
        print(f"     {n:28} {b:>6,}자   +{b - avg:>5,.0f}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

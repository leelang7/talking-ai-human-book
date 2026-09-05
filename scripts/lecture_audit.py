# -*- coding: utf-8 -*-
"""
강의 자산 대조 — 강의에는 있는데 책에는 없는 것

저자의 28차시 강의 심화 블록 423개를 원고와 대조한다. 사람이 읽어서
비교하면 하루가 걸리고, 그래서 지금까지 4개 차시밖에 못 했다(자기비판 C0 ③).

**기계가 할 수 있는 부분만 한다.** 판단은 여전히 사람이 한다.

방법은 단순하다. 강의 블록에서 **고유한 기술 토큰** 을 뽑고 —
`skip_prompt` 같은 식별자, `p95` 같은 약어, `30000/1001` 같은 수치 —
그것이 원고 어디에도 없으면 후보로 올린다.

없다고 다 넣어야 하는 것은 아니다. 이 책이 **일부러 뺀 것도 많다**
(LangGraph, 양자화 세부 등은 Vol.02 나 다른 책의 영역이다).
그래서 이 스크립트는 **후보를 세어서 보여줄 뿐** 결정하지 않는다.

    python scripts/lecture_audit.py              차시별 요약
    python scripts/lecture_audit.py 02           한 차시의 후보 전부
    python scripts/lecture_audit.py --terms      토큰 빈도순
"""
import glob
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT = os.path.join(ROOT, "draft")
INDEX = os.path.join(DRAFT, "_강의자산_인덱스.txt")

# 이 책이 다루지 않기로 한 영역. 후보에서 뺀다 — 없는 것이 정상이다.
OUT_OF_SCOPE = {
    "langgraph", "langchain", "typeddict", "add_messages", "annotated",
    "reducer", "dag", "compile", "draw_ascii", "draw_mermaid", "invoke",
    "checkpointer", "recursion", "state", "node", "edge",
}
# 너무 흔해서 신호가 안 되는 것
STOP = {
    "llm", "api", "ai", "gpu", "cpu", "tts", "stt", "ok", "id", "url", "db",
    "http", "https", "json", "html", "css", "js", "py", "md", "svg", "mp4",
    "wav", "mp3", "png", "jpg", "the", "and", "for", "with", "true", "false",
    "none", "vol", "ch", "n", "s", "x", "y", "z",
}

TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.]{2,}")
NUMBER = re.compile(r"\b\d+(?:[./]\d+)?\s*(?:ms|초|배|%|fps|GB|MB|kHz|토큰|건|장)\b")


def corpus():
    """원고 전체 — 본문 · 부록 · 온라인 · 코드까지."""
    parts = []
    for pat in ("draft/**/*.md", "code/**/*.py", "code/**/*.html"):
        for p in glob.glob(os.path.join(ROOT, pat), recursive=True):
            if "_강의자산" in p:
                continue
            parts.append(open(p, encoding="utf-8", errors="replace").read())
    return "\n".join(parts)


def blocks():
    """(차시, 본문) 목록."""
    out = []
    for line in open(INDEX, encoding="utf-8-sig"):
        line = line.strip()
        if "|" not in line:
            continue
        head, body = line.split("|", 1)
        m = re.match(r"(\d+)", head)
        if m and body.strip():
            out.append((m.group(1), body.strip()))
    return out


def terms_of(text):
    """블록에서 고유 기술 토큰을 뽑는다."""
    found = set()
    for t in TOKEN.findall(text):
        low = t.lower().rstrip(".")
        if low in STOP or low in OUT_OF_SCOPE or len(low) < 3:
            continue
        found.add(t.rstrip("."))
    for t in NUMBER.findall(text):
        found.add(re.sub(r"\s+", "", t))
    return found


def audit():
    book = corpus()
    low = book.lower()
    missing = defaultdict(list)          # 차시 → [(토큰, 블록 미리보기)]
    freq = Counter()
    seen_blocks = defaultdict(int)
    for sess, body in blocks():
        seen_blocks[sess] += 1
        for t in terms_of(body):
            if t.lower() in low:
                continue
            missing[sess].append((t, body))
            freq[t] += 1
    return missing, freq, seen_blocks


def main():
    args = sys.argv[1:]
    missing, freq, counts = audit()

    if args and args[0] == "--terms":
        print(f"\n  원고에 없는 토큰 {len(freq)}종 — 잦은 순\n")
        for t, n in freq.most_common(40):
            where = sorted({s for s in missing for x, _ in missing[s] if x == t})
            print(f"    {n:>3}회  {t:28} {'·'.join(where[:6])}차시")
        print()
        return 0

    if args:
        sess = args[0].zfill(2)
        rows = missing.get(sess, [])
        uniq = {}
        for t, body in rows:
            uniq.setdefault(t, body)
        print(f"\n  {sess}차시 — 블록 {counts.get(sess, 0)}개 · 원고에 없는 토큰 {len(uniq)}종\n")
        for t, body in sorted(uniq.items()):
            snip = re.sub(r"\s+", " ", body)
            i = snip.find(t)
            s = max(0, i - 60)
            print(f"    ● {t}")
            print(f"      …{snip[s:s + 150]}…")
        print()
        return 0

    print(f"\n  강의 블록 {sum(counts.values())}개 · 원고에 없는 토큰 {len(freq)}종\n")
    print("   차시   블록   미검출 토큰   대표")
    print("  " + "─" * 68)
    for sess in sorted(counts):
        uniq = sorted({t for t, _ in missing.get(sess, [])})
        if not uniq:
            continue
        top = ", ".join(sorted(uniq, key=lambda t: -freq[t])[:4])
        print(f"   {sess}    {counts[sess]:>3}      {len(uniq):>3}       {top[:52]}")
    print()
    print("  한 차시를 자세히 — python scripts/lecture_audit.py 02")
    print("  토큰 빈도순  — python scripts/lecture_audit.py --terms")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

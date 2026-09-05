# -*- coding: utf-8 -*-
"""
주장 감사 — 출간 전에 근거 없는 것을 찾는다

원고의 문장 중 **검증 가능한 주장** 을 전부 뽑아 셋으로 나눈다.

  ① 수치 주장     "230초" "3.3%" "22.5MB" — 어디서 온 숫자인가
  ② 고유명사 주장  C2PA · SynthID · Nyquist · WebRTC — 외부 사실. 틀리면 환각
  ③ 저자 경험 주장 "저자는 …했다" — 프로젝트 파일·강의 자료에 흔적이 있는가

수치는 세 곳과 대조한다: 코드 상수 · 실측 로그(_work) · 부록 C.
셋 중 어디에도 없고 "약·대략·경험적으로" 같은 완충어도 없으면 **미근거** 로 올린다.

판단은 사람이 한다. 이 스크립트는 **목록** 을 낸다.

    python scripts/claims_audit.py            요약
    python scripts/claims_audit.py --numbers  미근거 수치 전부
    python scripts/claims_audit.py --names    외부 고유명사 전부
    python scripts/claims_audit.py --author   저자 경험 주장 전부
"""
import glob
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT = os.path.join(ROOT, "draft")

NUM = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*(초|ms|밀리초|분|시간|%|배|fps|kHz|Hz|GB|MB|KB|px|프레임|토큰|건|명|장|개|줄|라디안|도|dB|pt|mm)")
HEDGE = ("약 ", "대략", "경험적으로", "어림", "정도", "근처", "안팎", "쯤", "가량", "예시 숫자", "실측", "잰 ")
NAME = re.compile(r"\b([A-Z][A-Za-z0-9]+(?:[ -][A-Z][A-Za-z0-9]+)*|[A-Z]{2,}[A-Za-z0-9-]*)\b")
NAME_SKIP = {"Ch", "Part", "Track", "GPU", "CPU", "API", "TTS", "STT", "LLM", "AI", "URL", "HTTP",
             "JSON", "HTML", "CSS", "SVG", "OK", "FAIL", "PASS", "ID", "VRAM", "RAM", "UI", "UX",
             "PNG", "JPG", "MP", "WAV", "MP4", "MP3", "TL", "DR", "YAML", "CLI", "SDK", "GB", "MB"}
AUTHOR = re.compile(r"저자[가는의도]?\s[^.]*?(했|겪|썼|버렸|실측|만들|정착|봤|잰|돌렸)[^.]*\.")


def sources():
    """숫자의 근거가 될 수 있는 텍스트 전부 — 코드 · 실측 로그 · 부록 C."""
    parts = []
    for pat in ("code/**/*.py", "code/**/*.yaml", "code/**/_work/**/*.txt",
                "code/**/_work/**/*.log", "code/**/_work/**/*.json", "code/**/*.json", "draft/appendix/appC_benchmarks.md",
                "draft/appendix/appN_cost_model.md"):
        for p in glob.glob(os.path.join(ROOT, pat), recursive=True):
            try:
                parts.append(open(p, encoding="utf-8", errors="replace").read())
            except OSError:
                pass
    return "\n".join(parts)


def sentences(text):
    out, incode = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            incode = not incode; continue
        if incode:
            continue
        for s in re.split(r"(?<=[.다요!?])\s+", line.strip()):
            if len(s) > 12:
                out.append(s)
    return out


def norm_num(s):
    s = s.replace(",", "")
    return s.rstrip("0").rstrip(".") if "." in s else s      # 3.00 == 3.0 == 3


def audit():
    src = sources()
    src_nums = set(norm_num(m.group(1)) for m in NUM.finditer(src))
    src_nums |= set(re.findall(r"\d+(?:\.\d+)?", src))
    unbacked, names, author = [], Counter(), []
    docs = sorted(glob.glob(os.path.join(DRAFT, "ch*.md"))) + \
           sorted(glob.glob(os.path.join(DRAFT, "appendix", "*.md")))
    for p in docs:
        ch = os.path.basename(p).split("_")[0]
        t = open(p, encoding="utf-8").read()
        for s in sentences(t):
            if s.startswith("#"):                          # 절 제목 "17.6 분석…" 은 수치가 아니다
                continue
            for m in NUM.finditer(s):
                n = norm_num(m.group(1))
                if n in src_nums or any(h in s for h in HEDGE):
                    continue
                if m.group(2) == "%":                      # 93.8% 는 근거 파일에 0.938 로 있을 수 있다
                    try:
                        frac = norm_num(f"{float(n) / 100:.4f}")
                    except ValueError:
                        frac = None
                    if frac in src_nums:
                        continue
                if n in ("1", "2", "3", "4", "5", "0"):        # 개수·순서는 주장이 아니다
                    continue
                unbacked.append((ch, m.group(0), s[:110]))
            for m in NAME.finditer(s):
                w = m.group(1)
                if w in NAME_SKIP or w.startswith("Ch") or len(w) < 3:
                    continue
                names[w] += 1
            for m in AUTHOR.finditer(s):
                author.append((ch, m.group(0)[:120]))
    return unbacked, names, author


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    unbacked, names, author = audit()

    if mode == "--numbers":
        by = defaultdict(list)
        for ch, n, s in unbacked:
            by[ch].append((n, s))
        for ch in sorted(by):
            print(f"\n  {ch} — {len(by[ch])}건")
            seen = set()
            for n, s in by[ch]:
                if s in seen: continue
                seen.add(s); print(f"    {n:>10}  {s}")
        return 0
    if mode == "--names":
        for w, c in sorted(names.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {c:>3}  {w}")
        return 0
    if mode == "--author":
        for ch, s in author:
            print(f"  {ch:8} {s}")
        return 0

    print(f"\n  코드·실측·부록C 에 없는 수치 주장   {len(unbacked)}건")
    print(f"  외부 고유명사                      {len(names)}종 (총 {sum(names.values())}회)")
    print(f"  저자 경험 주장                     {len(author)}건")
    print("\n  python scripts/claims_audit.py --numbers | --names | --author\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

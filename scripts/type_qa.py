# -*- coding: utf-8 -*-
"""
조판 검수 — 눈으로 넘기지 말고 세어라

출간본 PDF 를 열어 **조판 사고 다섯 종류** 를 쪽 번호와 함께 센다.
편집자가 한 장씩 넘기며 잡던 것을 기계가 먼저 잡는다.

  ① 자간 늘어짐   양끝맞춤 줄에서 낱말 사이가 비정상으로 벌어진 줄
  ② 상자 빈 여백   코드·인용 상자 안 첫 줄이 상자 위에서 너무 떨어진 것
  ③ 헐렁한 쪽     본문이 쪽의 절반도 못 채우고 끝난 쪽
  ④ 외톨이 줄     쪽 맨 아래 한 줄만 남은 문단(고아) · 쪽 맨 위 한 줄(과부)
  ⑤ 넘치는 표     본문 폭을 벗어난 표·코드

    python scripts/type_qa.py                build/book.pdf 검수
    python scripts/type_qa.py --max-stretch 12   기준 넘으면 종료코드 1
"""
import argparse
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "build", "book.pdf")

STRETCH_RATIO = 2.2      # 그 줄의 낱말 사이 평균이 본문 중앙값의 몇 배면 '늘어짐' 인가
BOX_GAP_PT = 16.0        # 상자 위 여백 상한
LOOSE_FILL = 0.55        # 쪽 높이의 이 비율도 못 채우면 헐렁
MIN_CHARS = 300          # 그러면서 글자도 이만큼 적으면


MONO = ("Consolas", "D2Coding", "Courier", "Mono")


def skip_bands(page):
    """검사에서 뺄 세로 구간 — 코드 상자(고정폭 글꼴)와 서식 빈칸.

    코드 블록의 도식(`입력 ──POST──▶ …`)과 동의서 서식(`동의자 :   (서명)`)은
    **일부러 벌려 놓은 것** 이다. 이것을 자간 사고로 세면 검수기가 양치기 소년이 된다.
    """
    bands = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if any(m in s["font"] for m in MONO):
                    bands.append((l["bbox"][1] - 1, l["bbox"][3] + 1))
                    break
    return bands


def lines_of_words(page):
    """쪽의 낱말을 줄 단위로 묶는다. PyMuPDF 의 'words' 는 공백으로 이미 쪼개져 있다."""
    bands = skip_bands(page)
    rows = defaultdict(list)
    for x0, y0, x1, y1, w, blk, ln, wn in page.get_text("words"):
        if any(a <= y0 <= z or a <= y1 <= z for a, z in bands):
            continue
        rows[(blk, ln)].append((x0, x1, y1 - y0, w))
    out = []
    for k in sorted(rows):
        ws = sorted(rows[k])
        if len(ws) >= 5:
            out.append(ws)
    return out


def word_gaps(ws):
    """줄 안 낱말 사이 빈틈. 글자 높이로 나눠 글꼴 크기와 무관하게 만든다."""
    h = sorted(w[2] for w in ws)[len(ws) // 2] or 1.0
    return [(b[0] - a[1]) / h for a, b in zip(ws, ws[1:]) if b[0] - a[1] > 0], h


def scan(path):
    import fitz
    doc = fitz.open(path)
    H = doc[0].rect.height
    W = doc[0].rect.width
    out = defaultdict(list)

    # 본문 낱말 간격의 중앙값 — 이 책의 '정상' 기준 (글자 높이로 정규화)
    allg = []
    per_page = {}
    for i, p in enumerate(doc, 1):
        rows = []
        for ws in lines_of_words(p):
            g, h = word_gaps(ws)
            if len(g) >= 4:
                rows.append((sorted(g)[len(g) // 2], ws))
                allg.append(sorted(g)[len(g) // 2])
        per_page[i] = rows
    normal = sorted(allg)[len(allg) // 2] if allg else 0.25

    for i, p in enumerate(doc, 1):
        d = p.get_text("dict")
        blocks = [b for b in d["blocks"] if b.get("lines")]
        # ① 자간 늘어짐
        for med, ws in per_page.get(i, []):
            if med > normal * STRETCH_RATIO:
                txt = " ".join(w[3] for w in ws)[:44]
                out["자간"].append((i, round(med / normal, 1), txt))
        # ② 상자 위 여백
        is_part = "Pa r t" in p.get_text()[:40] or p.get_text().strip().startswith("Part")
        for dr in p.get_drawings():
            r = dr["rect"]
            if is_part or not (250 < r.width < 500 and 12 < r.height < 260):
                continue      # 파트 표지의 장 목록 표는 상자가 아니다
            ins = [b["bbox"] for b in blocks
                   if r.y0 - 1 < b["bbox"][1] and b["bbox"][3] < r.y1 + 1 and r.x0 - 2 < b["bbox"][0]]
            if ins:
                gap = min(x[1] for x in ins) - r.y0
                if gap > BOX_GAP_PT:
                    out["상자여백"].append((i, round(gap, 1)))
        if not blocks:
            continue
        top = min(b["bbox"][1] for b in blocks)
        bot = max(b["bbox"][3] for b in blocks)
        nchar = len(p.get_text().strip())
        # ③ 헐렁한 쪽
        if i > 2 and bot < H * LOOSE_FILL and nchar < MIN_CHARS:
            out["헐렁"].append((i, nchar, round(bot / H, 2)))
        # ⑤ 넘치는 것
        for b in blocks:
            if b["bbox"][2] > W - 6:
                out["폭초과"].append((i, round(b["bbox"][2], 1)))
                break
    return out, normal, len(doc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=PDF)
    ap.add_argument("--max-stretch", type=int, default=None, help="이 수를 넘으면 종료코드 1")
    a = ap.parse_args()
    if not os.path.exists(a.pdf):
        print("  PDF 가 없다 — scripts/build_book.py 를 먼저 돌려라")
        return 2
    out, normal, n = scan(a.pdf)
    print(f"\n  조판 검수 — {os.path.basename(a.pdf)} · {n}쪽 · 정상 낱말 간격 {normal:.2f}pt\n")
    print(f"  ① 자간 늘어짐   {len(out['자간']):>4}줄")
    for pg, r, txt in out["자간"][:8]:
        print(f"       p{pg:<4} {r}배  {txt}")
    print(f"  ② 상자 위 여백  {len(out['상자여백']):>4}건  {out['상자여백'][:5]}")
    print(f"  ③ 헐렁한 쪽     {len(out['헐렁']):>4}쪽  {[x[0] for x in out['헐렁']][:8]}")
    print(f"  ④ 폭 초과       {len(out['폭초과']):>4}건  {[x[0] for x in out['폭초과']][:6]}")
    print()
    if a.max_stretch is not None and len(out["자간"]) > a.max_stretch:
        print("  ✗ 자간 늘어짐 %d > 기준 %d\n" % (len(out["자간"]), a.max_stretch))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

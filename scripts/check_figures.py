# -*- coding: utf-8 -*-
"""도판 검사 — 그림도 결과물이므로 검사한다.

  1. 박스끼리 겹치는가
  2. 연결선이 박스를 관통하는가
  3. 인쇄했을 때 글자가 8pt 미만인가   ← 도판 계획의 자기 규칙
  4. 글자가 캔버스 밖으로 나가는가
  5. 캡션 없이 배치된 그림이 있는가
"""
import re, sys, glob, os

TEXT_MM = 152.0          # 판형 본문 폭
MIN_PT  = 8.0
MM_PER_PT = 25.4 / 72.0

def _viewbox(s):
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', s)
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)

def _nofill(s):
    """fill:none 인 class 이름 — 윤곽선 표식이지 상자가 아니다."""
    return {m.group(1) for m in re.finditer(r'\.(\w+)\s*\{([^}]*)\}', s)
            if 'fill:none' in m.group(2).replace(' ', '')}


def _rects(s):
    out, ghost = [], _nofill(s)
    for m in re.finditer(r'<rect([^>]*?)x="([-\d.]+)"[^>]*?y="([-\d.]+)"'
                         r'[^>]*?width="([\d.]+)"[^>]*?height="([\d.]+)"', s):
        attr = m.group(1)
        x, y, w, h = map(float, m.groups()[1:])
        if h < 12:                      # 얇은 것은 막대·구분선
            continue
        cls = re.search(r'class="(\w+)"', attr)
        if cls and cls.group(1) in ghost:      # 점선 윤곽 = 주석
            continue
        if 'fill="none"' in attr:
            continue
        out.append((x, y, x + w, y + h))
    return out

def _segs(s):
    out = []
    for m in re.finditer(r'<path class="ln" d="M([^"]+)"', s):
        pts = []
        for t in m.group(1).replace("L", " ").split():
            a, b = t.split(",")
            pts.append((float(a), float(b)))
        out += list(zip(pts, pts[1:]))
    return out

def _fonts(s):
    """class 이름 → font-size(단위) 매핑을 <style>에서 읽는다."""
    fs = {}
    for m in re.finditer(r'\.(\w+)\s*\{([^}]*)\}', s):
        f = re.search(r'font-size:\s*([\d.]+)px', m.group(2))
        if f:
            fs[m.group(1)] = float(f.group(1))
    return fs

def _texts(s):
    out = []
    for m in re.finditer(r'<text([^>]*)>(.*?)</text>', s, re.S):
        attr, body = m.group(1), re.sub(r'\s+', ' ', m.group(2)).strip()
        cls = re.search(r'class="(\w+)"', attr)
        x   = re.search(r'x="([-\d.]+)"', attr)
        m2 = re.search(r'text-anchor="(\w+)"', attr)
        anc = m2.group(1) if m2 else 'start'
        out.append((cls.group(1) if cls else '',
                    float(x.group(1)) if x else 0.0, anc, body))
    return out

def _width(body, size):
    """한글은 대략 size, 라틴/숫자/공백은 대략 size*0.55."""
    w = 0.0
    for ch in body:
        w += size if ord(ch) > 0x2000 else size * 0.55
    return w

def check(path):
    s = open(path, encoding="utf-8").read()
    name = os.path.basename(path)
    vw, vh = _viewbox(s)
    bad = []
    if not vw:
        return [(name, "viewBox 없음")]

    unit_mm = TEXT_MM / vw            # 1 user unit 이 인쇄되는 실제 mm

    R = _rects(s)
    for i in range(len(R)):
        for j in range(i + 1, len(R)):
            a, b = R[i], R[j]
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                bad.append((name, f"박스 겹침 {a} × {b}"))

    for (p1, p2) in _segs(s):
        for r in R:
            vert = p1[0] == p2[0]
            if vert and r[0] < p1[0] < r[2] and \
               max(r[1], min(p1[1], p2[1])) < min(r[3], max(p1[1], p2[1])):
                bad.append((name, f"선이 박스 관통 {p1}-{p2}"))
            if not vert and r[1] < p1[1] < r[3] and \
               max(r[0], min(p1[0], p2[0])) < min(r[2], max(p1[0], p2[0])):
                bad.append((name, f"선이 박스 관통 {p1}-{p2}"))

    fs = _fonts(s)
    smallest = None
    for cls, x, anc, body in _texts(s):
        size = fs.get(cls)
        if not size or not body:
            continue
        pt = size * unit_mm / MM_PER_PT
        if smallest is None or pt < smallest[0]:
            smallest = (pt, cls)
        w = _width(body, size)
        left = {'middle': x - w / 2, 'end': x - w}.get(anc, x)
        if left < -2 or left + w > vw + 2:
            bad.append((name, f"글자가 캔버스 밖 — “{body[:22]}”"))
    if smallest and smallest[0] < MIN_PT:
        bad.append((name, f"인쇄 글자 {smallest[0]:.1f}pt "
                          f"(.{smallest[1]}) — 최소 {MIN_PT}pt"))
    return bad

def main():
    figs = sorted(glob.glob("draft/figures/*.svg"))
    used = set()
    for md in glob.glob("draft/**/*.md", recursive=True):
        used |= set(re.findall(r'\!\[([^\]]*)\]\(figures/([\w.]+)\)',
                               open(md, encoding="utf-8").read()))
    placed  = {f for _, f in used}
    nocap   = {f for c, f in used if len(c.strip()) < 8}

    allbad = []
    for f in figs:
        allbad += check(f)
    for f in sorted(set(os.path.basename(x) for x in figs) - placed):
        allbad.append((f, "원고에 배치되지 않음"))
    for f in sorted(nocap):
        allbad.append((f, "캡션이 없거나 너무 짧음"))

    for n, msg in allbad:
        print(f"  [FAIL] {n:24} {msg}")
    print(f"\n  도판 {len(figs)}개 · 배치 {len(placed)}개 · 지적 {len(allbad)}건")
    return 1 if allbad else 0

if __name__ == "__main__":
    sys.exit(main())

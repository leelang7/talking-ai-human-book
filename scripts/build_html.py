# -*- coding: utf-8 -*-
"""
원고 → 조판 HTML (인쇄 미리보기)

**도판과 표의 배치를 처음부터 바로잡는다.**

Vol.02 는 이미지를 `img { margin: auto }` 로만 가운데 뒀다. 그러면 이미지는
중앙에 오지만 **캡션이 `text-align: justify` 를 상속받아 왼쪽에 붙는다.**
이미지와 캡션의 축이 어긋나 보이는 것이 그 때문이다.

해법은 단위를 바꾸는 것이다 — `img` 하나가 아니라 **`figure` 통째로** 가운데 둔다.
그러면 이미지·캡션·주석이 한 축에 정렬된다.

이 스크립트가 하는 일:
    · 마크다운 이미지 → figure + **장별 자동 번호** (그림 7-2)
    · 표 바로 위의 '표: …' 줄 → 표 캡션으로 승격 + 자동 번호
    · 도판·표가 **페이지 중간에서 잘리지 않게** 함
    · 넓은 표는 글자를 줄이고, 그래도 넘치면 가로 스크롤(화면)·축소(인쇄)

실행:  python scripts/build_html.py            → build/preview.html
       python scripts/build_html.py --check    → 배치 문제만 검사(종료코드)
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT, BUILD = os.path.join(ROOT, "draft"), os.path.join(ROOT, "build")

CSS = """
:root{ --w:152mm; --h:225mm; --fg:#16181d; --muted:#6b7280; --line:#d9dde5; --accent:#F59E0B;   /* 시리즈 색 = 표지 앰버. Vol.01 빨강·Vol.02 청록과 섞이지 않게 */ }
*{ box-sizing:border-box; }
body{ margin:0; background:#eceef2; color:var(--fg);
      font-family:"Noto Serif KR","Nanum Myeongjo",serif; font-size:10.5pt; line-height:1.72; }
.page{ background:#fff; width:var(--w); min-height:var(--h); margin:14px auto; padding:18mm 16mm;
       box-shadow:0 1px 6px rgba(0,0,0,.12); }

h1{ font-size:19pt; margin:0 0 14pt; line-height:1.35; }
h2{ font-size:13pt; margin:20pt 0 7pt; padding-bottom:3pt; border-bottom:1px solid var(--line); }
h3{ font-size:11pt; margin:14pt 0 5pt; }
/* 본문 정렬 — 왼쪽. 양끝맞춤은 한국어에서 낱말 사이를 벌린다.
   한글은 하이픈이 없고 인라인 코드(`cfg_weight`)는 통째로 다음 줄로 넘어가므로,
   남은 자리를 낱말 사이로만 메우게 된다. 조판 검수에서 139줄 → 왼쪽 정렬로 0줄. */
p{ margin:6pt 0; }
h1, h2, h3, h4, figcaption, .cap, .sub{ word-break:keep-all; overflow-wrap:break-word; }
h1, h2, h3{ text-wrap:balance; }   /* 두 줄 제목의 둘째 줄에 낱말 하나만 남지 않게 */
.hy{ hyphens:auto; -webkit-hyphens:auto; }   /* 긴 라틴 낱말(backchannel) — 앞 줄이 벌어지지 않게 음절 하이픈 */
p, li{ text-align:justify; text-align-last:left; word-break:normal; overflow-wrap:break-word; }
.oa{ letter-spacing:-0.2pt; } .ob{ letter-spacing:0.3pt; }   /* 외톨이 글자 보정 — 조판기가 해당 문단에만 붙인다 */
/* 본문은 양끝맞춤 + 음절 단위 줄바꿈(한국어 책 관행). keep-all 로 낱말을 지키면 오른쪽이 들쭉날쭉하거나(왼쪽맞춤)
   낱말 사이가 벌어진다(양끝맞춤, 실측 최대 10pt). 음절 줄바꿈이면 최대 5pt 로 가지런하다(2026-09-05 실측).
   남는 문제는 문단 마지막 줄에 1~2글자만 남는 외톨이 — build_book 이 PDF 를 읽어 그 문단에만 .oa/.ob 를 붙여 없앤다. */
blockquote{ margin:8pt 0; padding:5pt 10pt; border-left:3px solid var(--accent);
            background:#f6f8fc; text-align:left; page-break-inside:auto; }
blockquote p{ margin:3pt 0; }
blockquote.callout{ font-size:9pt; padding:4pt 9pt; margin:6pt 0; page-break-before:avoid; }
code{ font-family:"D2Coding","Consolas",monospace; font-size:9pt; background:#f2f4f8; padding:1px 4px; }
/* 본문 속 긴 코드·영문 토큰이 줄바꿈을 못 하면 그 줄의 낱말 사이가 벌어진다(조판 검수 ①). */
p code, li code{ overflow-wrap:anywhere; }
p strong, li strong{ overflow-wrap:anywhere; }
pre{ background:#f6f8fa; border:1px solid var(--line); border-radius:4px; padding:6pt 10pt;
     overflow-x:auto; page-break-inside:auto; }
pre code{ background:none; padding:0; line-height:1.45; display:block; }

/* 도판 — 핵심: img 가 아니라 figure 를 가운데 둔다.
   img 에만 margin:auto 를 주면 이미지는 중앙, 캡션은 왼쪽에 붙어 축이 어긋난다. */
figure{ margin:13pt auto; text-align:center; page-break-inside:avoid; max-width:100%; }
figure img{ display:block; margin:0 auto; max-width:100%; height:auto;
            border:1px solid var(--line); border-radius:3px; }
figure figcaption{ margin-top:5pt; font-size:8.8pt; color:var(--muted);
                   text-align:center; line-height:1.5; }
figure figcaption .num{ color:var(--fg); font-weight:600; }
figure.narrow img{ max-width:70%; }
figure.tall img{ max-width:58%; }

/* 표 */
.tw{ margin:11pt 0; } .tw.small{ break-inside:avoid; page-break-inside:avoid; }   /* 6행 이하 표는 쪼개지 않는다(7행부터는 쪼개는 편이 앞 쪽 빈 바닥보다 낫다) — 두 줄만 다음 쪽에 남는 것보다 통째로 넘기는 게 낫다 */
table tr{ page-break-inside:avoid; } thead{ display:table-header-group; }
.tw > .cap{ font-size:8.8pt; color:var(--muted); text-align:center; margin-bottom:4pt; }
.tw > .cap .num{ color:var(--fg); font-weight:600; }
.tw > .scroll{ overflow-x:auto; }
table{ border-collapse:collapse; width:100%; font-size:9pt; }
th,td{ border:1px solid var(--line); padding:4pt 6pt; text-align:left;
       word-break:keep-all; vertical-align:top; }
th{ background:#f4f6fa; font-weight:600; white-space:nowrap; }
table.cols6 { font-size:8.4pt; } table.cols6 th,table.cols6 td{ padding:3pt 4pt; }
table.cols8 { font-size:7.8pt; } table.cols8 th,table.cols8 td{ padding:2pt 3pt; }

hr{ border:0; border-top:1px solid var(--line); margin:16pt 0; }
ul,ol{ padding-left:18pt; } li{ margin:3pt 0; }

@media print{
  body{ background:#fff; }
  .page{ box-shadow:none; margin:0; width:auto; min-height:auto; padding:0; page-break-after:always; }
  .tw > .scroll{ overflow:visible; }
  table{ font-size:8.2pt; }
}
"""

_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_TBLCAP = re.compile(r"^표\s*[:：]\s*(.+)$")
_FIGCAP = re.compile(r"^그림\s*[:：]\s*(.+)$")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "")


def _inline(s):
    s = _esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = _LINK.sub(lambda m: '<a href="%s">%s</a>' % (m.group(2), m.group(1)), s)
    return s


def _inline_block(ln):
    t = ln.rstrip()
    if not t.strip():
        return ""
    if t.startswith("#"):
        lvl = min(len(t) - len(t.lstrip("#")), 4)
        return "<h%d>%s</h%d>" % (lvl, _inline(t.lstrip("# ").strip()), lvl)
    if re.fullmatch(r"-{3,}", t.strip()):
        return "<hr>"
    if t.lstrip().startswith("> "):
        return "<blockquote>%s</blockquote>" % _inline(t.lstrip()[2:])
    if re.match(r"^\s*[-*]\s+", t):
        return "<ul><li>%s</li></ul>" % _inline(re.sub(r"^\s*[-*]\s+", "", t))
    if re.match(r"^\s*\d+[.)]\s+", t):
        return "<ol><li>%s</li></ol>" % _inline(re.sub(r"^\s*\d+[.)]\s+", "", t))
    return "<p>%s</p>" % _inline(t)



def _shape_class(src):
    """세로로 긴 그림은 폭을 줄인다 — 전폭으로 앉히면 한 쪽의 80% 를 먹는다(출간 검수에서 잡힘).
    가로 그림은 wide(전폭), 정사각은 narrow(70%), 세로는 tall(58%)."""
    try:
        from PIL import Image
        for base in (DRAFT, os.path.join(DRAFT, "..")):
            path = os.path.join(base, src)
            if os.path.exists(path):
                w, h = Image.open(path).size
                r = h / w
                return "tall" if r > 1.1 else ("narrow" if r > 0.85 else "wide")
    except Exception:
        pass
    return "wide"


def _render_table(rows, chno, n, cap, issues):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [c for c in cells if not all(re.fullmatch(r":?-{2,}:?", x or "-") for x in c)]
    if not cells:
        return ""
    ncol = max(len(r) for r in cells)
    if ncol >= 8:
        issues.append("Ch%s 표 %d: 열 %d개 — 인쇄 폭 초과 위험" % (chno, n, ncol))
    cls = "cols8" if ncol >= 8 else ("cols6" if ncol >= 6 else "")
    head, body = cells[0], cells[1:]
    h = "".join("<th>%s</th>" % _inline(x) for x in head)
    b = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % _inline(x) for x in r) for r in body)
    capdiv = ('<div class="cap"><span class="num">표 %s.%d</span> %s</div>'
              % (chno, n, _esc(cap))) if cap else ""
    return ('<div class="tw%s">%s<div class="scroll">'
            '<table class="%s"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
            "</div></div>" % (" small" if len(body) <= 6 else "", capdiv, cls, h, b))


# ── 보강 장(3+ · 23+ · 28+) 표기 ──────────────────────────────────────────────
# 파일·코드 폴더는 'ch03plus' 를 유지하되, 책에는 "3A" 로 찍는다.
# "3+.6" "그림 3+-1" "Ch23+" 는 읽히지 않는다(2026-09-05 독자 검수). "3A.6" "그림 3A.1" "Ch23A" 로.
_PLUS_REF = re.compile(r"(Ch0?(?:3|23|28))\+")                    # Ch03+ · Ch3+ · Ch23+ · Ch28+
_PLUS_SEC = re.compile(r"(?<![0-9A-Za-z])(3|23|28)\+(?=\.[0-9])")  # 3+.6 · §23+.6


def disp_label(s):
    """장 라벨('3+' · 'Ch03+')의 표시형 — '3A' · 'Ch03A'."""
    return s.replace("+", "A")


def disp_refs(md):
    """본문 속 보강 장 참조와 절 번호를 표시형으로."""
    return _PLUS_SEC.sub(lambda m: m.group(1) + "A", _PLUS_REF.sub(lambda m: m.group(1) + "A", md))


_SEG = re.compile(r"(<pre>.*?</pre>|<code>.*?</code>|<[^>]+>)", re.S)
_LATIN = re.compile(r"(?<![A-Za-z/._-])([A-Za-z][a-z]{7,}[A-Za-z]*)(?![A-Za-z/._-])")


_CAMEL = re.compile(r"([a-z]{2,})([A-Z][a-z]{2,})")                 # LangChain → Lang<wbr>Chain
_CODE_BREAK = re.compile(r"([/_.\-:=])(?=[A-Za-z0-9_])")                # 코드 안 경로·식별자 경계
_SHY = {                                                                  # 소프트 하이픈 — 책에 자주 나오는 긴 라틴 낱말
    "Chatterbox": "Chatter\u00adbox", "backchannel": "back\u00adchannel", "retargeting": "re\u00adtarget\u00ading",
    "conversion": "conver\u00adsion", "Holistic": "Holis\u00adtic", "expression": "expres\u00adsion",
    "transformers": "trans\u00adformers", "diffusers": "dif\u00adfusers", "accelerate": "accel\u00aderate",
    "inference": "infer\u00adence", "streaming": "stream\u00ading", "landmarks": "land\u00admarks",
    "benchmark": "bench\u00admark", "framework": "frame\u00adwork", "container": "con\u00adtainer",
    "websocket": "web\u00adsocket", "WebSocket": "Web\u00adSocket", "Playwright": "Play\u00adwright",
    "multiplier": "multi\u00adplier", "animation": "ani\u00admation", "checkpoint": "check\u00adpoint",
}


def hyphenate_latin(html):
    """긴 라틴 낱말(backchannel · retargeting)을 lang=en 스팬으로 감싸 음절 하이픈을 허용한다.

    양끝맞춤에서 이런 낱말이 줄 끝에 걸리면 통째로 다음 줄로 넘어가고 앞 줄이 3배로 벌어진다(p199 실측 3.4배).
    코드·태그 안은 건드리지 않는다. 8글자 이상, 첫 글자 뒤가 전부 소문자인 낱말만 — 약어(WebRTC)·경로는 제외."""
    parts = _SEG.split(html)
    for i in range(0, len(parts), 2):                 # 짝수 칸이 태그 밖 텍스트
        t = _LATIN.sub(lambda m: '<span class="hy" lang="en">' + m.group(1) + "</span>", parts[i])
        t = _CAMEL.sub(lambda m: m.group(1) + "<wbr>" + m.group(2), t)
        for w, hy in _SHY.items():
            t = t.replace(w, hy)
        parts[i] = t
    for i in range(1, len(parts), 2):                 # 홀수 칸이 태그·코드
        if parts[i].startswith("<code>"):
            parts[i] = "<code>" + _CODE_BREAK.sub(lambda m: m.group(1) + "<wbr>", parts[i][6:-7]) + "</code>"
    return "".join(parts)


def md_to_html(md, chno, issues):
    """마크다운을 조판 HTML 로. 도판·표 번호를 장 단위로 매긴다."""
    md, chno = disp_refs(md), disp_label(chno)
    fig_n = tbl_n = 0
    out, lines, i = [], md.split("\n"), 0

    while i < len(lines):
        ln = lines[i]

        # 코드 블록 — 한 덩어리로 만든다. `<pre><code>` 뒤에 줄바꿈을 넣으면
        # 그 줄바꿈이 그대로 살아 **상자 첫 줄이 빈 채로** 조판된다(출간본 검수에서 잡힘).
        if ln.strip().startswith("```"):
            i += 1
            body = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(_esc(lines[i]))
                i += 1
            i += 1
            out.append("<pre><code>" + "\n".join(body).strip("\n") + "</code></pre>")
            continue

        m = _IMG.search(ln)
        if m:
            fig_n += 1
            alt, src = m.group(1).strip(), m.group(2).strip()
            cap = alt
            if not cap and i + 1 < len(lines):
                c = _FIGCAP.match(lines[i + 1].strip())
                if c:
                    cap = c.group(1)
                    i += 1
            if not cap:
                issues.append("Ch%s 그림 %d: 캡션 없음 (%s)" % (chno, fig_n, src))
            cls = "narrow" if "narrow" in src else _shape_class(src)
            out.append('<figure class="%s"><img src="%s" alt="%s">'
                       '<figcaption><span class="num">그림 %s.%d</span> %s</figcaption></figure>'
                       % (cls, _esc(src), _esc(cap), chno, fig_n, _esc(cap)))
            i += 1
            continue

        if ln.lstrip().startswith("|"):
            cap = None
            # 캡션과 표 사이에 빈 줄이 있을 수 있다 — 빈 항목을 건너뛰고 되돌아본다.
            k = len(out) - 1
            while k >= 0 and not out[k].strip():
                k -= 1
            if k >= 0:
                c = _TBLCAP.match(_strip_tags(out[k]).strip())
                if c:
                    cap = c.group(1)
                    del out[k:]
            rows, j = [], i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append(lines[j])
                j += 1
            tbl_n += 1
            out.append(_render_table(rows, chno, tbl_n, cap, issues))
            i = j
            continue

        # 인용 블록 — 연속된 '>' 줄을 하나로 묶는다. 줄마다 따로 만들면 상자가 줄 수만큼 생기고,
        # 줄을 건너 이어지는 **굵게** 가 변환되지 않은 채 남는다(출간본 검수에서 잡힘).
        if ln.lstrip().startswith(">"):
            paras, cur = [], []
            def flush():
                if not cur:
                    return
                # '**실습 코드** : …' 처럼 굵은 표지로 시작하는 줄은 항목이다 — 줄바꿈을 지킨다
                joined = cur[0]
                for x in cur[1:]:
                    joined += ("<br>" if x.startswith("**") else " ") + x
                paras.append(re.sub(r"\s+[:：]\s+", ": ", joined))      # '실습 코드 : x' → '실습 코드: x'
                cur.clear()
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                body = re.sub(r"^\s*>\s?", "", lines[i]).rstrip()
                if body.strip():
                    cur.append(body.strip())
                else:
                    flush()
                i += 1
            flush()
            cls = ' class="callout"' if paras and paras[0].startswith("**실습") else ""
            out.append("<blockquote%s>%s</blockquote>" % (cls, "".join("<p>%s</p>" % _inline(x).replace("&lt;br&gt;", "<br>") for x in paras)))
            continue
        # 목록 — 연속된 항목을 하나의 <ul>/<ol> 로
        m_ul = re.match(r"^\s*[-*]\s+", ln)
        m_ol = re.match(r"^\s*\d+[.)]\s+", ln)
        if m_ul or m_ol:
            tag, pat = ("ul", r"^\s*[-*]\s+") if m_ul else ("ol", r"^\s*\d+[.)]\s+")
            items = []
            while i < len(lines) and re.match(pat, lines[i]):
                items.append(re.sub(pat, "", lines[i]).rstrip())
                i += 1
            out.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % _inline(x) for x in items), tag))
            continue

        out.append(_inline_block(ln))
        i += 1

    return hyphenate_latin("\n".join(x for x in out if x)), fig_n, tbl_n


def chapters():
    out = []
    for fn in sorted(os.listdir(DRAFT)):
        m = re.match(r"ch(\d+)(plus)?_", fn)
        if m and fn.endswith(".md"):
            label = m.group(1).lstrip("0") + ("+" if m.group(2) else "")
            out.append((float(m.group(1)) + (0.5 if m.group(2) else 0), label, fn))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="배치 문제만 검사")
    ap.add_argument("--out", default=os.path.join(BUILD, "preview.html"))
    a = ap.parse_args()

    issues, pages, figs, tbls = [], [], 0, 0
    for _, label, fn in chapters():
        with open(os.path.join(DRAFT, fn), encoding="utf-8") as f:
            html, nf, nt = md_to_html(f.read(), label, issues)
        figs += nf
        tbls += nt
        pages.append('<section class="page">%s</section>' % html)

    print("\n  장 %d개 · 도판 %d개 · 표 %d개" % (len(pages), figs, tbls))
    if issues:
        print("\n  배치 지적 %d건" % len(issues))
        for x in issues[:14]:
            print("   · %s" % x)
        if len(issues) > 14:
            print("   … 외 %d건" % (len(issues) - 14))
    else:
        print("  배치 지적 없음")

    if a.check:
        print()
        return 1 if issues else 0

    os.makedirs(BUILD, exist_ok=True)
    # 도판을 빌드 폴더로 복사한다 — 원고의 상대경로가 그대로 풀리게.
    src_fig = os.path.join(DRAFT, "figures")
    if os.path.isdir(src_fig):
        import shutil
        dst_fig = os.path.join(BUILD, "figures")
        shutil.rmtree(dst_fig, ignore_errors=True)
        shutil.copytree(src_fig, dst_fig)
        print("  도판 %d개 복사" % len(os.listdir(dst_fig)))
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html lang=ko><head><meta charset=utf-8>"
                "<title>AI 휴먼 해부학 — 조판 미리보기</title>"
                "<style>%s</style></head><body>\n%s\n</body></html>"
                % (CSS, "\n".join(pages)))
    print("\n  → %s\n" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

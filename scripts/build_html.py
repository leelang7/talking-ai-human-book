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
:root{ --w:152mm; --h:225mm; --fg:#16181d; --muted:#6b7280; --line:#d9dde5; --accent:#3f6fe8; }
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
p{ margin:6pt 0; text-align:left; word-break:normal; }
/* 양끝맞춤 + keep-all 은 한국어에서 낱말 사이를 벌린다 — 줄바꿈 지점이 공백뿐이라
   긴 라틴 토큰(LivePortrait·LangChain) 하나가 그 줄 전체를 늘린다. 한글은 음절 단위
   줄바꿈이 정상이므로 word-break:normal 로 되돌린다(조판 검수에서 139줄 → 확인). */
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

/* 표 */
.tw{ margin:11pt 0; }
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
    capdiv = ('<div class="cap"><span class="num">표 %s-%d</span> %s</div>'
              % (chno, n, _esc(cap))) if cap else ""
    return ('<div class="tw">%s<div class="scroll">'
            '<table class="%s"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
            "</div></div>" % (capdiv, cls, h, b))


def md_to_html(md, chno, issues):
    """마크다운을 조판 HTML 로. 도판·표 번호를 장 단위로 매긴다."""
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
            cls = "narrow" if "narrow" in src else "wide"
            out.append('<figure class="%s"><img src="%s" alt="%s">'
                       '<figcaption><span class="num">그림 %s-%d</span> %s</figcaption></figure>'
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

    return "\n".join(x for x in out if x), fig_n, tbl_n


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
                "<title>말하는 AI 휴먼을 만드는 법 — 조판 미리보기</title>"
                "<style>%s</style></head><body>\n%s\n</body></html>"
                % (CSS, "\n".join(pages)))
    print("\n  → %s\n" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

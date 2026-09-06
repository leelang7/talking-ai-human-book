# -*- coding: utf-8 -*-
"""
출간본 빌드 — 원고 전체를 한 권의 HTML 로 조판하고, 헤드리스 크로미움으로 PDF 를 뽑는다.

    표지 → 판권 → 서문 → 이 책의 사용법 → 등장인물 → 차례
    → 파트 표지 + 장 33 → 부록(인쇄 10종) → 온라인 부록 안내

    python scripts/build_book.py            → build/book.html + build/book.pdf (차례에 쪽 번호까지, 2패스)
    python scripts/build_book.py --html     → HTML 만

build_html.py 의 변환기(md_to_html)를 그대로 쓴다 — 도판·표 번호는 장 단위.
인쇄 부록은 draft/appendix/ 에 있는 것, 온라인 부록은 draft/online/ 에 있는 것이다 — 폴더가 진실이다.
"""
import argparse
import glob
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_html import CSS, DRAFT, BUILD, chapters, md_to_html, _inline, _esc, disp_label   # noqa: E402

TITLE = "AI 휴먼 해부학"
SUB = "얼굴·목소리·두뇌·기억 — 네 층을 조립하고 실측하는 법<br>사진 한 장에서 실시간 대화 아바타까지,<br>픽셀이 사람이 되는 여정"
SERIES = "All That AI · Vol.03"
DEDICATION = [   # 표제지 뒷면 — 저자가 한 줄로 바꿔도 되게 리스트로 둔다
    "이 책에서 <em>조건을 재는 사진</em> 은 전부 민트의 것입니다.",
    "회색 러시안블루, 나의 고양이.",
    "지금은 고양이별에 있습니다.",
]
VOLUMES = [   # 표제지 뒷면(시리즈 쪽) — 앞 두 권은 서문에 적힌 제목 그대로, 다음 권은 온라인 부록 J 의 가제
    ("Vol.01", "테슬라처럼 만드는 비전 자율주행과 피지컬 AI", "픽셀이 핸들이 된다", False),
    ("Vol.02", "우리집 AI 의사·수의사·헬스코치", "픽셀이 진단이 된다", False),
    ("Vol.03", "AI 휴먼 해부학", "픽셀이 사람이 된다", True),
    ("Vol.04", "우리집 휴머노이드 (준비 중)", "픽셀이 몸이 된다", False),
]
AUTHOR = "이석창 (Seokchang Lee)"
REPO = "github.com/leelang7/talking-ai-human-book"          # 공개 컴패니언 저장소 (2026-09-05)
ISBN = ""                          # 부크크 등록 시 발급 → 여기 넣고 다시 조판 (비면 줄을 찍지 않는다)
PUB_DATE = "2026년 9월"            # 초판 1쇄 발행
PUBLISHER = [("펴낸이", "한건희"), ("펴낸곳", "주식회사 부크크"), ("출판사등록", "2014.07.15 (제2014-16호)"),
             ("주소", "서울특별시 금천구 가산디지털1로 119 SK트윈타워 A동 305-7호"), ("전화", "1670-8316"),
             ("이메일", "info@bookk.co.kr"), ("홈페이지", "www.bookk.co.kr")]   # 부크크 판권 표준 문구 — 등록 화면의 안내와 대조할 것
APP_ORDER = "ABCDEFGHLN"          # 인쇄 부록 순서 (폴더에 있는 것만)

BOOK_CSS = CSS + """
@page{ size:152mm 225mm; margin:17mm 15mm 16mm 15mm; }
@page :left{ margin-left:13mm; margin-right:17mm; }   /* 제본 쪽(안쪽) 17 · 바깥 13 — 합계 30 유지 → 쪽수 불변 */
@page :right{ margin-left:17mm; margin-right:13mm; }
body{ background:#fff; font-family:"Noto Serif KR","Batang","Malgun Gothic",serif; }
code, pre{ font-family:"D2Coding","Consolas","Malgun Gothic",monospace; }
.page{ box-shadow:none; margin:0; width:auto; min-height:auto; padding:0; page-break-after:always; }
.page:last-child{ page-break-after:auto; }
.cover{ text-align:center; padding-top:70mm; }
.cover .series{ font-size:10pt; color:var(--muted); letter-spacing:.2em; }
.cover h1{ font-size:26pt; margin:14pt 0 8pt; line-height:1.3; }
.cover .sub{ font-size:11pt; color:#333; margin:0 8mm; line-height:1.6; }
.cover .author{ margin-top:40mm; font-size:12pt; }
.colophon{ font-size:9pt; color:#333; padding-top:64mm; }
.blank{ min-height:10mm; }
.dedic{ padding-top:86mm; text-align:center; color:#333; }
.dedic p{ margin:0 0 1.9em; font-size:10.5pt; line-height:1.9; text-align:center; text-align-last:center; }
.dedic p:first-child{ color:var(--muted); font-size:10pt; }
.vols{ padding-top:38mm; }
.vols .h{ font-size:9.5pt; color:var(--muted); letter-spacing:.2em; text-align:center; margin-bottom:16pt; }
.vols .v{ margin:0 auto 11pt; width:106mm; }
.vols .v .t{ font-size:10pt; color:#333; }
.vols .v .l{ font-size:9pt; color:var(--muted); margin-top:1pt; }
.vols .v.me .t{ font-weight:600; color:#16181d; }
.vols .v.me .l{ color:#16181d; }
.vols .n{ width:106mm; margin:20pt auto 0; font-size:8.5pt; color:var(--muted); line-height:1.6; }
.colophon table{ font-size:9pt; width:auto; } .colophon td{ border:0; padding:2pt 6pt; }
.colophon td:first-child{ width:26mm; white-space:nowrap; color:var(--muted); }
.part{ padding-top:48mm; }
.part .label{ font-size:11pt; color:var(--muted); letter-spacing:.15em; }
.part h1{ font-size:22pt; margin:8pt 0 12pt; }
.part .blurb{ font-size:10.5pt; color:#333; }
.part table{ margin-top:14pt; }
.toc h1{ font-size:18pt; }
.toc .p{ font-weight:700; margin:12pt 0 4pt; font-size:11pt; }
.toc .c{ margin:2pt 0 2pt 10pt; display:flex; }
.toc .c .t{ flex:1; } .toc .c .n{ width:24pt; text-align:right; color:var(--muted); font-variant-numeric:tabular-nums; }
.toc .s{ margin:0 0 3pt 26pt; font-size:8.4pt; color:#555; line-height:1.45; }
h1.ch{ margin-top:6mm; page-break-before:always; }
h1.ch small{ display:block; font-size:10pt; color:var(--muted); font-weight:400; letter-spacing:.15em; margin-bottom:6pt; }
section.page > h1.ch:first-child{ page-break-before:auto; }
h2, h3{ page-break-after:avoid; }
p, li{ orphans:3; widows:3; }
.online ul{ padding-left:14pt; }
.idx{ column-count:2; column-gap:9mm; font-size:9pt; }
.idx .ih{ font-weight:700; margin:8pt 0 3pt; break-after:avoid; color:var(--muted); }
.idx .ii{ display:flex; gap:4pt; margin:1.5pt 0; break-inside:avoid; }
.idx .ii .t{ flex:1; } .idx .ii .n{ color:var(--muted); font-variant-numeric:tabular-nums; }
/* 카피피팅 사다리 — 행간·글자 크기는 절대 바꾸지 않는다(장마다 줄간격이 달라 보인다는 지적, 2026-09-05).
   문단·제목·도판·표 사이 간격만 조금씩 조인다/늘린다. 기본: p 6pt · h2 20/7 · h3 14/5 · figure 13 · .tw 11 · blockquote 8 · td 4 */
.tight1 p, .tight1 li{ margin:4.5pt 0; } .tight1 h2{ margin:16pt 0 6pt; } .tight1 h3{ margin:11pt 0 4pt; } .tight1 figure{ margin:10pt auto; } .tight1 .tw{ margin:9pt 0; } .tight1 blockquote{ margin:6pt 0; }
.tight2 p, .tight2 li{ margin:3.5pt 0; } .tight2 h2{ margin:13pt 0 5pt; } .tight2 h3{ margin:9pt 0 3pt; } .tight2 figure{ margin:8pt auto; } .tight2 .tw{ margin:7pt 0; } .tight2 blockquote{ margin:5pt 0; } .tight2 td, .tight2 th{ padding-top:3pt; padding-bottom:3pt; } .tight2 h1.ch{ margin-top:3mm; }
.loose1 p, .loose1 li{ margin:7.5pt 0; } .loose1 h2{ margin:24pt 0 9pt; } .loose1 h3{ margin:17pt 0 6pt; } .loose1 figure{ margin:16pt auto; } .loose1 .tw{ margin:14pt 0; } .loose1 blockquote{ margin:10pt 0; } .loose1 td, .loose1 th{ padding-top:5pt; padding-bottom:5pt; }
.loose2 p, .loose2 li{ margin:8.5pt 0; } .loose2 h2{ margin:28pt 0 11pt; } .loose2 h3{ margin:20pt 0 7pt; } .loose2 figure{ margin:19pt auto; } .loose2 .tw{ margin:17pt 0; } .loose2 blockquote{ margin:12pt 0; } .loose2 td, .loose2 th{ padding-top:6pt; padding-bottom:6pt; }
.toc.tight1 .s{ margin-bottom:2pt; } .toc.tight2 .s{ margin-bottom:1pt; } .toc.tight2 .c{ margin:1pt 0 1pt 10pt; }
.toc.loose1 .s{ margin-bottom:5pt; } .toc.loose1 .c{ margin:3.5pt 0 3.5pt 10pt; } .toc.loose2 .s{ margin-bottom:7pt; } .toc.loose2 .c{ margin:5pt 0 5pt 10pt; }
h1.ch.cont{ page-break-before:auto; margin-top:16mm; }
.keep{ break-inside:avoid; page-break-inside:avoid; }
"""


def read(name):
    with open(os.path.join(DRAFT, name), encoding="utf-8") as f:
        return f.read()


def parts_from_toc():
    """01_목차.md 의 '## Part…/## Track…' 머리와 그 아래 장 표에서 파트 구조를 읽는다."""
    toc = read("01_목차.md").split("\n")
    parts, cur = [], None
    for ln in toc:
        m = re.match(r"^## (Part \d|Track [ABC])\. (.+?)\s*—\s*(\d+)장.*$", ln)
        if m:
            cur = {"label": m.group(1), "title": m.group(2).strip(), "blurb": "", "chapters": []}
            parts.append(cur)
            continue
        if cur is None:
            continue
        mc = re.match(r"^\| (Ch\d+\+?) \| \*\*(.+?)\*\* \| (.+?) \|", ln)
        if mc:
            cur["chapters"].append((mc.group(1), mc.group(2), mc.group(3).strip()))
        elif ln.startswith("## "):
            cur = None
        elif ln.strip() and not ln.startswith("|") and not cur["chapters"] and not cur["blurb"]:
            cur["blurb"] = ln.strip().lstrip("> ").strip()
    return parts


def chapter_html(label, fn, issues):
    md = read(fn)
    md = re.sub(r"^# +Ch\S*\.?\s*", "# ", md, count=1)          # 'Ch07. 제목' → 제목 (번호는 따로 찍는다)
    html, nf, nt = md_to_html(md, label, issues)
    m = re.search(r"<h1>(.*?)</h1>", html)
    title = m.group(1) if m else fn
    if m:
        html = html.replace(m.group(0), '<h1 class="ch" id="ch%s"><small>CHAPTER %s</small>%s</h1>'
                            % (label.replace("+", "plus"), disp_label(label), title), 1)
    secs = re.findall(r"<h2>(.*?)</h2>", html)
    return html, title, secs, nf, nt


def appendix_files():
    out = {}
    for fn in os.listdir(os.path.join(DRAFT, "appendix")):
        m = re.match(r"app([A-Z])_.*\.md$", fn)
        if m:
            out[m.group(1)] = fn
    return out


def appendix_html(letter, fn, issues):
    md = open(os.path.join(DRAFT, "appendix", fn), encoding="utf-8").read()
    html, _, _ = md_to_html(md, letter, issues)
    m = re.search(r"<h1>(.*?)</h1>", html)
    title = m.group(1) if m else fn
    if m:
        html = html.replace(m.group(0), '<h1 class="ch" id="app%s">%s</h1>' % (letter, title), 1)
    return html, title


def backmatter_html(name, key, issues):
    """뒷붙임(참고문헌·저자 후기) — 부록과 같은 모양으로 찍되 번호는 붙이지 않는다."""
    html, _, _ = md_to_html(open(os.path.join(DRAFT, name), encoding="utf-8").read(), "0", issues)
    m = re.search(r"<h1>(.*?)</h1>", html)
    title = m.group(1) if m else name
    if m:
        html = html.replace(m.group(0), '<h1 class="ch" id="%s">%s</h1>' % (key, title), 1)
    return html, title


def online_titles():
    out = []
    for fn in sorted(os.listdir(os.path.join(DRAFT, "online"))):
        if fn.endswith(".md"):
            first = open(os.path.join(DRAFT, "online", fn), encoding="utf-8").readline().strip("# \n")
            out.append(first)
    return out


def sparse_pages(pdf_path):
    """채움 40% 미만인 쪽(파트 표지 제외) — 헐렁(loose)보다 넓은 그물. 장 꼬리가 여기 걸리면 조이기만 시도한다."""
    import fitz
    d = fitz.open(pdf_path)
    H = d[0].rect.height
    out = set()
    for i, pg in enumerate(d, 1):
        if pg.get_text().strip().startswith(("Pa r t", "Part")):
            continue
        bl = [b for b in pg.get_text("dict")["blocks"] if b.get("lines") and b["bbox"][3] > 36 and b["bbox"][1] < H - 36]
        if not bl or max(b["bbox"][3] for b in bl) / H < 0.40:
            out.add(i)
    return out


def part_disp(label):
    """파트 라벨 표시형 — 세 트랙은 Part 3 의 하위 구분이다 (Part 0 이 있던 시절의 번호를 정리, 2026-09-05)."""
    return ("Part 3 · " + label) if label.startswith("Track") else label


def loose_pages(pdf_path):
    """검수기(type_qa)와 같은 기준 — 머리·꼬리 뺀 본문 블록이 300자 미만이고 쪽의 55%도 못 채우면 헐렁."""
    import fitz
    d = fitz.open(pdf_path)
    H = d[0].rect.height
    out = set()
    for i, pg in enumerate(d, 1):
        # 머리글(y<36)·꼬리글(y>H-36)만 뺀다 — 본문 첫 줄이 y=48 에서 시작하므로 60 으로 자르면 한 줄짜리 쪽을 놓친다(p295 '관련 —' 한 줄)
        bl = [b for b in pg.get_text("dict")["blocks"] if b.get("lines") and b["bbox"][3] > 36 and b["bbox"][1] < H - 36]
        if not bl:
            out.add(i)                                    # 본문이 아예 없는 쪽
            continue
        n = sum(len(sp["text"]) for b in bl for l in b["lines"] for sp in l["spans"])
        rules = [dr["rect"].y0 for dr in pg.get_drawings() if dr["rect"].width > 100 and dr["rect"].height < 3]   # 표 괘선
        top = min(b["bbox"][1] for b in bl)
        cont = len(rules) >= 3 and min(rules) - top < 4   # 쪽이 표 괘선으로 시작 = 앞 쪽에서 이어진 표의 꼬리 → 헐렁
        fill = max(b["bbox"][3] for b in bl) / H
        if fill < 0.35 and ((n < 150 and len(rules) < 3) or cont):      # 3줄도 안 되는 꼬리, 또는 이어진 표 꼬리
            out.add(i)
    return out


_WS = "[" + chr(9) + chr(10) + chr(13) + " ]*"
_KEEP = re.compile("((?:<p>(?:(?!</p>).)*</p>" + _WS + "){1,2})((?:<hr>" + _WS + ")?)"
                   "(<blockquote[^>]*>(?:(?!</blockquote>).)*</blockquote>)" + _WS + "$", re.S)


def keep_tail(html):
    """장 끝 '실습 코드' 상자는 앞 문단 둘과 한 덩어리로 — 상자만 새 쪽으로 넘어가 혼자 남지 않게."""
    return _KEEP.sub(lambda m: '<div class="keep">' + m.group(1) + m.group(2) + m.group(3) + "</div>", html.rstrip(), count=1)


ORPH = {}       # 문단 끝 20자(공백 제거) → "oa"(자간 -0.2pt 당김) | "ob"(+0.3pt 밀어냄)
_PUNCT = "[]" + ".,;:!?)}\"'”’…·—-" + "]"


def _key(text):
    """문단 식별 키 — 끝 20자. 쪽이 갈린 문단도 꼬리 블록에는 끝이 있다."""
    return re.sub(r"\s+", "", text)[-20:]


def orphan_paras(pdf_path):
    """마지막 줄이 1~2글자뿐인 문단(외톨이 글자) — 본문 폭 문단만, 코드 상자·표 칸 제외."""
    import fitz
    d = fitz.open(pdf_path)
    W = d[0].rect.width
    out = []
    in_toc = False
    for pg in d:
        head = pg.get_text()[:40]
        if head.startswith("차례"):
            in_toc = True                                  # 차례는 줄이 짧아 외톨이 판정 대상이 아니다
        if "CHAPTER" in head.replace(" ", "") or re.match(r"Part[0-9]+" + chr(10), head.replace(" ", "")):
            in_toc = False                                 # 장 머리 또는 파트 표지('Part 1' 뒤 마침표 없음 — 차례의 'Part 1.' 과 다르다)
        if in_toc:
            continue
        rules = [dr["rect"].y0 for dr in pg.get_drawings() if dr["rect"].width > 100 and dr["rect"].height < 3]
        for blk in pg.get_text("dict")["blocks"]:
            ls = blk.get("lines", [])
            if len(ls) < 2 or (blk["bbox"][2] - blk["bbox"][0]) < W * 0.45:
                continue
            if any(m in sp["font"] for l in ls for sp in l["spans"] for m in ("Consolas", "D2Coding", "Courier", "Mono")):
                continue
            if any(blk["bbox"][1] - 2 < y < blk["bbox"][3] + 2 for y in rules):
                continue                                   # 표 안(괘선이 지나감) — 칸의 짧은 줄은 외톨이가 아니다
            if abs(ls[-1]["bbox"][0] - ls[0]["bbox"][0]) > 3:
                continue                                   # 마지막 줄이 첫 줄과 다른 x 에서 시작 — 차례의 쪽 번호 같은 것
            sizes = sorted(sp["size"] for l in ls for sp in l["spans"])
            if sizes[len(sizes) // 2] > 11.5:
                continue                                   # 제목(13pt+)은 문단이 아니다 — 제목 줄 나눔은 text-wrap:balance 가 맡는다
            last = "".join(sp["text"] for sp in ls[-1]["spans"]).strip()
            core = re.sub(_PUNCT, "", re.sub(r"\s+", "", last))
            if 0 < len(core) <= 2:
                out.append(_key("".join(sp["text"] for l in ls for sp in l["spans"])))
    return out


def tag_orphans(section_html):
    """ORPH 에 오른 문단(<p>·<li>)에 .oa/.ob 를 붙인다 — 그 문단의 자간만 ±0.2pt."""
    if not ORPH:
        return section_html
    import html as _html

    def fix(m):
        tag, attrs, inner = m.group(1), m.group(2) or "", m.group(3)
        cls = ORPH.get(_key(_html.unescape(re.sub(r"<[^>]+>", "", inner))))
        if not cls:
            return m.group(0)
        if 'class="' in attrs:
            attrs = attrs.replace('class="', 'class="%s ' % cls, 1)
        else:
            attrs += ' class="%s"' % cls
        return "<%s%s>%s</%s>" % (tag, attrs, inner, tag)
    return re.sub(r"<(p|li)(\s[^>]*)?>(.*?)</(?:p|li)>", fix, section_html, flags=re.S)


def front_html(name, cls=""):
    html, _, _ = md_to_html(read(name), "0", [])
    return '<section class="page front%s">%s</section>' % ((" " + cls) if cls else "", html)


def build(toc_pages=None, tight=None, index_html=None):
    tight = tight or {}
    issues = []
    parts = parts_from_toc()
    ch_files = {label: fn for _, label, fn in chapters()}     # '7', '3+', '28+'
    body, entries = [], []                                    # entries: (kind, key, title, secs)

    body.append('<section class="page cover"><div class="series">%s</div><h1>%s</h1>'
                '<div class="sub">%s</div><div class="author">%s 지음</div></section>' % (SERIES, TITLE, SUB, AUTHOR))
    body.append('<section class="page dedic">%s</section>'
                % "".join("<p>%s</p>" % x for x in DEDICATION))   # 표제지 뒷면 — 헌정
    for fi, name in enumerate(("00_서문.md", "00_이책의_사용법.md", "00_등장인물.md")):
        body.append(front_html(name, tight.get("front%d" % fi, "")))

    toc_idx = len(body)
    body.append("TOC_PLACEHOLDER")

    figs = tbls = 0
    used = set()
    for part in parts:
        rows = "".join("<tr><td>%s</td><td><strong>%s</strong></td><td>%s</td></tr>" % (disp_label(c), _inline(t), _inline(b))
                       for c, t, b in part["chapters"])
        body.append('<section class="page part"><div class="label">%s</div><h1>%s</h1><div class="blurb">%s</div>'
                    '<div class="tw"><table><tbody>%s</tbody></table></div></section>'
                    % (part_disp(part["label"]), _esc(part["title"]), _inline(part["blurb"]), rows))
        entries.append(("part", part["label"], part["title"], []))
        for c, _, _ in part["chapters"]:
            label = c[2:].lstrip("0")                          # 'Ch03+' → '3+', 'Ch07' → '7'
            fn = ch_files.get(label)
            if not fn:
                issues.append("목차의 %s 에 해당하는 원고 파일 없음" % c)
                continue
            used.add(label)
            html, title, secs, nf, nt = chapter_html(label, fn, issues)
            html = keep_tail(html)
            figs += nf
            tbls += nt
            body.append('<section class="page%s">%s</section>' % (" " + tight["ch" + label] if ("ch" + label) in tight else "", html))
            entries.append(("ch", label, title, secs))
    for label, fn in ch_files.items():
        if label not in used:
            issues.append("목차에 없는 장 파일: %s" % fn)

    entries.append(("part", "부록", "부록", []))
    apps = appendix_files()
    for letter in APP_ORDER:
        if letter in apps:
            html, title = appendix_html(letter, apps[letter], issues)
            html = keep_tail(html)
            body.append('<section class="page%s">%s</section>' % (" " + tight["app" + letter] if ("app" + letter) in tight else "", html))
            entries.append(("app", letter, title, []))
    ol = "".join("<li>%s</li>" % _inline(t) for t in online_titles())   # 제목의 *기울임* 도 변환
    nch = len([x for x in os.listdir(os.path.join(ROOT, "code"))
                if os.path.isdir(os.path.join(ROOT, "code", x)) and not x.startswith(("_", "."))])
    nwork = len(glob.glob(os.path.join(ROOT, "code", "*", "_work", "*.json")))
    ntest = len(glob.glob(os.path.join(ROOT, "code", "*", "test_*.py")))
    online = ('<div class="online keep"><h1 class="ch cont" id="online">저장소와 온라인 부록</h1>'
              '<p>이 책의 코드와 실측 근거는 전부 공개 저장소에 있습니다 — <code>%s</code>. '
              '원고와 조판 PDF 는 저작권 때문에 들어 있지 않습니다.</p>'
              '<p><strong>장·부록 폴더 %d개.</strong> 각 장 끝의 <em>실습 코드</em> 줄에 적힌 경로가 그 폴더입니다. '
              '폴더마다 실행 스크립트와 <code>test_*.py</code>(%d개)가 있고, 본문의 수치를 낸 측정 결과는 '
              '<code>_work/*.json</code>(%d개)로 남아 있습니다. 부록 C §7 의 재현 절차가 이 파일들을 가리킵니다.</p>'
              '<p>아래 <strong>온라인 부록 셋</strong>은 기준일이 있거나 시리즈 독자용입니다. '
              '종이에 굳히지 않고 저장소의 <code>draft/online/</code>에서 갱신합니다.</p><ul>%s</ul>'
              '<p>모델 지형도(부록 K)는 <strong>6개월마다</strong> 기준일과 함께 고쳐 씁니다. '
              '책을 산 시점과 기준일이 많이 벌어졌다면 저장소 쪽을 보세요 — 본문의 판단 기준은 그대로 쓰되 '
              '모델 이름만 바뀝니다.</p></div>' % (REPO, nch, ntest, nwork, ol))
    body[-1] = body[-1][:-len("</section>")] + online + "</section>"   # 마지막 부록에 이어 붙인다
    entries.append(("app", "online", "온라인 부록", []))

    for name, key in (("98_참고문헌.md", "refs"), ("97_저자후기.md", "after")):
        bh, btitle = backmatter_html(name, key, issues)
        body.append('<section class="page%s">%s</section>'
                    % (" " + tight[key] if key in tight else "", keep_tail(bh)))
        entries.append(("app", key, btitle, []))

    # 찾아보기 — 쪽 번호는 조판이 끝나야 알 수 있다. 자리만 잡아 두고 마지막 패스에서 채운다.
    idx_idx = len(body)
    body.append('<section class="page index"><h1 class="ch" id="index">찾아보기</h1>'
                + (index_html or "<p>(조판 후 채워집니다)</p>") + "</section>")
    entries.append(("app", "index", "찾아보기", []))
    rows_v = "".join('<div class="v%s"><div class="t">%s &nbsp;·&nbsp; %s</div>'
                     '<div class="l">%s</div></div>' % (" me" if me else "", vol, t, l)
                     for vol, t, l, me in VOLUMES)
    body.append('<section class="page vols"><div class="h">%s 시리즈</div>%s'
                '<div class="n">각 권은 따로 읽을 수 있습니다. 이 책이 앞의 두 권에서 무엇을 물려받았는지는 '
                '온라인 부록 I 에 적어 두었습니다.</div></section>'
                % (SERIES.split(" · ")[0], rows_v))   # 시리즈 쪽 — 판권지 바로 앞(둘 다 머리글·쪽번호 없음)
    # 판권지 — 책 끝 (부크크 표준 항목). ISBN 은 발급 뒤 상수에 넣는다.
    rows = [("제목", "%s — 얼굴·목소리·두뇌·기억, 네 층을 조립하고 실측하는 법" % TITLE), ("시리즈", SERIES),
            ("초판 1쇄 발행", PUB_DATE), ("지은이", AUTHOR)] + PUBLISHER + ([("ISBN", ISBN)] if ISBN else []) + \
           [("컴패니언 저장소", REPO), ("측정 환경", "RTX 4070 SUPER 12GB · Windows 11 · 본문 수치는 부록 C의 측정 조건 기준")]
    body.append('<section class="page colophon"><table>' + "".join("<tr><td>%s</td><td>%s</td></tr>" % r for r in rows) +
                '</table><p>ⓒ 이석창 2026. 본 책은 저작자의 지적 재산이므로 무단 전재와 복제를 금합니다. '
                '본문의 코드는 저장소의 라이선스를, 인용된 외부 모델·라이브러리는 각자의 라이선스를 따릅니다.</p></section>')

    pages = toc_pages or {}
    lines = ['<section class="page toc%s"><h1>차례</h1>' % ((" " + tight["toc"]) if "toc" in tight else "")]
    for kind, key, title, secs in entries:
        if kind == "part":
            lines.append('<div class="p">%s%s</div>' % ("" if key == "부록" else part_disp(key) + ". ", _esc(title)))
            continue
        n = pages.get(kind + key, "")
        name = ("Ch%s  " % disp_label(key)) if kind == "ch" else ""
        lines.append('<div class="c"><span class="t">%s%s</span><span class="n">%s</span></div>' % (name, title, n))
        if secs:
            lines.append('<div class="s">%s</div>' % " · ".join(re.sub(r"<[^>]+>", "", s) for s in secs[:8]))
    lines.append("</section>")
    body[toc_idx] = "\n".join(lines)

    def wrap(sections):
        return ("<!doctype html><html lang=ko><head><meta charset=utf-8><title>%s</title><style>%s</style></head>"
                "<body>\n%s\n</body></html>" % (TITLE, BOOK_CSS, "\n".join(sections)))
    # 표지·판권(앞 두 섹션)은 머리글·쪽번호 없이 따로 찍는다 — 쪽 번호는 서문부터 1
    body = [tag_orphans(x) for x in body]
    # 태그 균형 — <em>/<strong>/<code> 가 한 구역 안에서 닫히지 않으면 그 뒤 책 전체가 기울거나 굵어진다
    for x in body:
        for tag in ("em", "strong", "code"):
            o, c = x.count("<%s>" % tag), x.count("</%s>" % tag)
            if o != c:
                t = re.search(r"<h1[^>]*>(.*?)</h1>", x, re.S)
                issues.append("태그 불균형 <%s> %d/%d — %s" % (tag, o, c, re.sub(r"<[^>]+>", "", t.group(1))[:30] if t else "?"))
    return wrap(body), issues, figs, tbls, entries, wrap(body[:2]), wrap(body[-2:]), wrap(body[2:-2])


# ── 찾아보기 — 전문 서적의 마지막 한 장 ─────────────────────────────────
# 낱말마다 "이 책에서 그것을 설명하는 곳" 이 있어야 한다. 본문 전체에서 세는 것이 아니라
# **표제어가 실제로 다뤄지는 쪽** 만 남긴다(한 쪽에 여러 번 나와도 한 번, 5쪽 넘으면 앞의 다섯).
INDEX_TERMS = {
    "가": ["감정 태그", "골든셋", "그림자", "기억(3층)", "끼어들기"],
    "나": ["나이퀴스트", "노이즈 게이트"],
    "다": ["더블 버퍼", "동의서", "드라이버", "딥페이크"],
    "라": ["라이선스", "리깅", "리타게팅", "립싱크"],
    "마": ["멀티 아바타", "메타발언", "모델 카드", "미디엄샷"],
    "바": ["바운딩", "발화 종료 판정", "번역", "벤치마크", "보관 기간", "분산", "블렌드셰이프", "비젬"],
    "사": ["사투리", "샤크다운", "상태 기계", "생성 로그", "수어", "스티칭", "실패 카탈로그", "싱크"],
    "아": ["아이들 루프", "어댑터", "얼굴 검출", "오디오 정규화", "온도", "워터마크", "원가", "음성 클로닝", "인페인팅"],
    "자": ["자막", "잡 큐", "재시도", "정규화", "제스처", "지문자", "지연 예산"],
    "차": ["채점기", "청킹", "초당 과금", "추모"],
    "카": ["컨테이너", "컨텍스트", "크로스페이드", "클로즈업"],
    "타": ["태그", "텍스트 정규화", "토큰 예산", "통역", "트랙 A", "트랙 B", "트랙 C"],
    "파": ["파인튜닝", "파츠", "페르소나", "폴백", "표정", "프롬프트"],
    "하": ["하이브리드 검색", "한글 경로", "핫스왑", "회귀 게이트", "휴식 포즈"],
    "A~Z": ["C2PA", "fps", "LoRA", "p95", "RAG", "STT", "SynthID", "TTFA", "TTS", "VAD", "VRM", "WebRTC"],
}


def build_index_html(body_pdf, front_pages, first_body_page):
    """본문 PDF 를 훑어 표제어가 나오는 쪽을 모은다. 쪽 번호는 인쇄 쪽 번호(서문=1)."""
    from pypdf import PdfReader
    r = PdfReader(body_pdf)
    texts = [(pg.extract_text() or "") for pg in r.pages]
    rows = []
    for head, terms in INDEX_TERMS.items():
        items = []
        for term in terms:
            key = term.split("(")[0].strip()
            hits = [i + 1 for i, t in enumerate(texts) if key in t and i + 1 >= first_body_page]
            if not hits:
                continue
            items.append((term, hits[:5]))
        if items:
            rows.append((head, items))
    out = ['<div class="idx">']
    for head, items in rows:
        out.append('<div class="ih">%s</div>' % _esc(head))
        for term, hits in items:
            out.append('<div class="ii"><span class="t">%s</span><span class="n">%s</span></div>'
                       % (_esc(term), ", ".join(str(h) for h in hits)))
    out.append("</div>")
    return "\n".join(out), sum(len(i) for _, i in rows)


# 조판은 카피피팅 때문에 같은 문서를 대여섯 번 다시 찍는다. 브라우저를 매번 띄우면
# 기동 시간만 쌓이므로 한 번 띄워 재사용한다. 끝에 close_browser() 로 닫는다.
_BROWSER = {"pw": None, "b": None}


def _page():
    if _BROWSER["b"] is None:
        from playwright.sync_api import sync_playwright
        _BROWSER["pw"] = sync_playwright().start()
        _BROWSER["b"] = _BROWSER["pw"].chromium.launch()
    return _BROWSER["b"].new_page()


def close_browser():
    if _BROWSER["b"] is not None:
        _BROWSER["b"].close()
        _BROWSER["pw"].stop()
        _BROWSER["b"] = _BROWSER["pw"] = None


_PASS = {"n": 0}


def render_pdf(html_path, pdf_path, header=True):
    import time as _t
    _PASS["n"] += 1
    t0 = _t.time()
    pg = _page()
    try:
        pg.goto("file:///" + html_path.replace("\\", "/"))
        pg.wait_for_timeout(500)
        pg.pdf(path=pdf_path, width="152mm", height="225mm", print_background=True,
               margin={"top": "17mm", "bottom": "16mm", "left": "15mm", "right": "15mm"},
               display_header_footer=header,
               header_template='<div style="font-size:7pt;color:#888;width:100%;text-align:center;'
                               'font-family:serif">' + TITLE + '</div>',
               footer_template='<div style="font-size:8pt;color:#444;width:100%;text-align:center;'
                               'font-family:serif"><span class="pageNumber"></span></div>')
    finally:
        pg.close()
        print("    렌더 %d회차 %.0fs" % (_PASS["n"], _t.time() - t0), flush=True)


def chapter_pages(pdf_path, entries):
    """PDF 본문에서 'CHAPTER n' / 부록 제목이 처음 나오는 쪽을 찾는다."""
    from pypdf import PdfReader
    r = PdfReader(pdf_path)
    texts = [(pg.extract_text() or "").replace(" ", "") for pg in r.pages]
    pages = {}
    # ① 장 — 'CHAPTER n' 은 장 머리에만 있다
    for i, txt in enumerate(texts, 1):
        for kind, key, _, _ in entries:
            if kind == "ch" and (kind + key) not in pages and ("CHAPTER%s" % disp_label(key)) in txt[:60]:   # 장 머리는 쪽 맨 위
                pages[kind + key] = i
    # ② 부록 — 제목이 차례에도 나오므로 마지막 장이 시작한 쪽 이후에서만 찾는다
    after = max(pages.values()) if pages else 0
    for i, txt in enumerate(texts, 1):
        if i <= after:
            continue
        for kind, key, title, _ in entries:
            if kind == "app" and (kind + key) not in pages:
                needle = re.sub(r"<[^>]+>", "", title)[:10].replace(" ", "")
                if needle and txt.startswith(needle):          # 부록 제목도 쪽 맨 위 — 본문 속 언급은 제외
                    pages[kind + key] = i
    # ②' 파트 표지 — 이게 없으면 Ch5 의 구간이 Part 1 표지까지 이어져, 장 꼬리가 아니라 파트 표지로
    #    헐렁 여부를 판정한다(2026-09-05: Ch5·15·21·27 과 차례가 전부 이 때문에 안 잡혔다).
    for i, txt in enumerate(texts, 1):
        flat = txt.replace(chr(10), "")
        for kind, key, title, _ in entries:
            if kind == "part" and (kind + key) not in pages:
                needle = (part_disp(key) + re.sub(r"<[^>]+>", "", title)[:4]).replace(" ", "")
                if flat.startswith(needle):
                    pages[kind + key] = i
    # ③ 앞부분(서문·사용법·등장인물·차례) — 첫 장 이전 쪽에서 제목으로 찾는다 (카피피팅 대상)
    first_ch = min(pages.values()) if pages else len(texts) + 1
    for i, txt in enumerate(texts, 1):
        if i >= first_ch:
            break
        for k, nd in (("front0", "서문"), ("front1", "이책의사용법"), ("front2", "등장인물"), ("toc", "차례")):
            if k not in pages and txt.startswith(nd):
                pages[k] = i
    # ④ 온라인 부록 — 마지막 부록에 이어 붙어 있어 쪽 맨 위가 아니다. 제목+첫 문장으로 찾는다
    if "apponline" not in pages:
        for i, txt in enumerate(texts, 1):
            if i > after and "온라인부록아래셋은" in txt.replace(chr(10), ""):
                pages["apponline"] = i
                break
    return pages, len(r.pages)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", action="store_true", help="HTML 만")
    a = ap.parse_args()
    os.makedirs(BUILD, exist_ok=True)
    # 도판만 복사한다 — `_src/`(중간 파일)와 숨김 폴더는 조판에 안 들어간다
    src_fig, dst_fig = os.path.join(DRAFT, "figures"), os.path.join(BUILD, "figures")
    shutil.rmtree(dst_fig, ignore_errors=True)
    shutil.copytree(src_fig, dst_fig,
                    ignore=shutil.ignore_patterns("_*", ".*"))
    html, issues, figs, tbls, entries, html_front, html_back, html_body = build()
    out = os.path.join(BUILD, "book.html")
    open(out, "w", encoding="utf-8").write(html)
    print("\n  장 %d · 부록 %d · 도판 %d · 표 %d" % (sum(1 for e in entries if e[0] == "ch"),
                                                   sum(1 for e in entries if e[0] == "app") - 1, figs, tbls))
    for x in issues[:10]:
        print("   · " + x)
    if any(x.startswith("태그 불균형") for x in issues):
        print("  ✗ 태그 불균형 — 조판을 멈춥니다 (원고의 코드 스팬 밖 '*' 나 닫히지 않은 강조를 찾으세요)")
        close_browser()
        return 1
    print("  → %s" % out)
    if a.html:
        close_browser()
        return 0
    pdf = os.path.join(BUILD, "book.pdf")
    fh, bh = os.path.join(BUILD, "_front.html"), os.path.join(BUILD, "_body.html")
    fp, bp = os.path.join(BUILD, "_front.pdf"), os.path.join(BUILD, "_body.pdf")
    kh, kp = os.path.join(BUILD, "_back.html"), os.path.join(BUILD, "_back.pdf")
    open(fh, "w", encoding="utf-8").write(html_front)
    render_pdf(fh, fp, header=False)                       # 표제지: 머리글·쪽번호 없음
    open(kh, "w", encoding="utf-8").write(html_back)
    render_pdf(kh, kp, header=False)                       # 판권지: 머리글·쪽번호 없음 (책 맨 끝)
    open(bh, "w", encoding="utf-8").write(html_body)
    render_pdf(bh, bp)
    pages, n = chapter_pages(bp, entries)                  # 쪽 번호는 본문 기준(서문이 1쪽)
    # 차례 쪽 번호 맞추기(2패스)는 카피피팅이 끝난 뒤에 한다 — 그 전에 맞춰 봐야
    # 행간을 줄이는 순간 전부 어긋난다. 렌더 한 번(약 1분)이 여기서 줄어든다.
    pages2, n2 = pages, n
    # ── 카피피팅: 마지막 쪽이 거의 빈 장은 행간을 조금 줄여 다시 짠다 (최대 2단계) ──
    from pypdf import PdfReader as _R
    LADDER = ["tight1", "tight2", "loose1", "loose2"]
    NO_FIT = {"apponline", "appindex"}        # 조판 클래스를 받지 않는 구간 — 사다리를 헛돌리지 않는다
    tight = {}
    def _ends(pages_map, total):
        ks = [(k, v) for k, v in sorted(pages_map.items(), key=lambda kv: kv[1])]
        return {k: (ks[i + 1][1] - 1 if i + 1 < len(ks) else total) for i, (k, _) in enumerate(ks)}, dict(ks)

    must = set()                                       # 한 번이라도 헐렁했던 구간 — 되돌리지 않는다
    for _pass in range(len(LADDER)):
        loose = loose_pages(bp)
        sparse = sparse_pages(bp)                      # 헐렁보다 넓은 그물 — 조이기만 허용
        ends, starts = _ends(pages2, n2)
        spill = []
        for k, end in ends.items():
            start = starts[k]
            cur = LADDER.index(tight[k]) if k in tight else -1
            if k in NO_FIT or end <= start:
                continue
            if end in loose and cur < len(LADDER) - 1:
                spill.append(k)
                must.add(k)
            elif end in sparse and cur < 1:            # 성긴 꼬리: tight1 → tight2 까지만
                spill.append(k)
        if not spill:
            break
        for k in spill:
            tight[k] = LADDER[(LADDER.index(tight[k]) if k in tight else -1) + 1]
        *_, html_body2 = build(toc_pages=pages2, tight=tight)
        open(bh, "w", encoding="utf-8").write(html_body2)
        render_pdf(bh, bp)
        pages2, n2 = chapter_pages(bp, entries)
        print("  카피피팅 %d패스: %s" % (_pass + 1, ", ".join("%s→%s" % (k, tight[k]) for k in spill)))
    # 조여도 안 빠진 성긴 꼬리는 원래 간격으로 되돌린다 — 간격 통일이 반 쪽 빈 것보다 우선
    ends, _ = _ends(pages2, n2)
    loose, sparse = loose_pages(bp), sparse_pages(bp)
    revert = [k for k, lvl in tight.items()
              if lvl.startswith("tight") and k not in must and ends.get(k) in sparse and ends.get(k) not in loose]
    if revert:
        for k in revert:
            del tight[k]
        *_, html_body2 = build(toc_pages=pages2, tight=tight)
        open(bh, "w", encoding="utf-8").write(html_body2)
        render_pdf(bh, bp)
        pages2, n2 = chapter_pages(bp, entries)
        print("  카피피팅 되돌림(조여도 안 빠짐): %s" % ", ".join(revert))
    print("  카피피팅 유지: %s" % (", ".join("%s→%s" % kv for kv in sorted(tight.items())) or "없음"))
    left = sorted(loose_pages(bp))
    print("  카피피팅 후 헐렁한 쪽(본문 기준): %s" % (left or "없음"))
    # ── 외톨이 글자: 마지막 줄이 1~2글자인 문단만 자간 ±0.2pt (행간·글자 크기는 그대로) ──
    for _op in range(2):
        orph = orphan_paras(bp)
        if not orph:
            break
        for k in orph:
            ORPH[k] = "ob" if ORPH.get(k) == "oa" else "oa"
        *_, html_body2 = build(toc_pages=pages2, tight=tight)
        open(bh, "w", encoding="utf-8").write(html_body2)
        render_pdf(bh, bp)
        pages2, n2 = chapter_pages(bp, entries)
        print("  외톨이 글자 %d패스: %d문단 조정" % (_op + 1, len(orph)))
    print("  외톨이 글자 남음: %d · 헐렁한 쪽: %s" % (len(orphan_paras(bp)), sorted(loose_pages(bp)) or "없음"))
    # ── 찾아보기 — 쪽 번호가 굳은 뒤에 채우고, 한 번 더 찍어 차례까지 맞춘다 ──
    first_body = min(pages2.values()) if pages2 else 1
    idx_html, n_terms = build_index_html(bp, 2, first_body)
    *_, html_body2 = build(toc_pages=pages2, tight=tight, index_html=idx_html)
    open(bh, "w", encoding="utf-8").write(html_body2)
    render_pdf(bh, bp)
    pages2, n2 = chapter_pages(bp, entries)
    *_, html_body2 = build(toc_pages=pages2, tight=tight, index_html=idx_html)   # 차례 쪽 번호를 최종 위치로
    open(bh, "w", encoding="utf-8").write(html_body2)
    render_pdf(bh, bp)
    pages_before = dict(pages2)
    pages2, n2 = chapter_pages(bp, entries)
    drift = sum(1 for k in pages_before if pages2.get(k) != pages_before[k])   # 마지막 두 패스 사이의 어긋남
    print("  찾아보기 표제어 %d개" % n_terms)
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    for src in (fp, bp, kp):
        for pg in PdfReader(src).pages:
            w.add_page(pg)
    # 책갈피(outline) — 파트·장·부록. 본문 쪽 번호 + 앞 2쪽 = PDF 쪽 인덱스
    front_n = len(PdfReader(fp).pages)
    parent = None
    for kind, key, title, _ in entries:
        plain = re.sub(r"<[^>]+>", "", title)
        if kind == "part":
            first_ch = next((e for e in entries[entries.index((kind, key, title, _)) + 1:] if e[0] != "part"), None)
            pg = pages2.get(first_ch[0] + first_ch[1]) if first_ch else None
            parent = w.add_outline_item(("%s. %s" % (key, plain)) if key != "부록" else plain,
                                        max(0, (pg or 1) - 2 + front_n))        # 파트 표지 = 첫 장 바로 앞 쪽
        elif (kind + key) in pages2:
            label = ("Ch%s  %s" % (disp_label(key), plain)) if kind == "ch" else plain
            w.add_outline_item(label, pages2[kind + key] - 1 + front_n, parent=parent)
    if len(w.pages) % 2:                      # 제작 규격은 짝수 쪽 — 마지막 낱장의 뒷면을 백지로 채운다
        box = w.pages[-1].mediabox
        w.add_blank_page(width=float(box.width), height=float(box.height))
        print("  짝수 맞춤 — 마지막에 백지 1쪽 (총 %d쪽)" % len(w.pages))
    w.add_metadata({"/Title": TITLE, "/Author": AUTHOR, "/Subject": SERIES, "/Creator": "build_book.py (Chromium)"})
    w.write(pdf)
    for f in (fh, bh, fp, bp, kh, kp):
        os.remove(f)
    print("  차례 쪽 번호 %d개 · 본문 %d쪽 + 앞 2쪽(표제·헌정) + 뒤 2쪽(시리즈·판권) = %d쪽 · 2패스 후 어긋난 항목 %d" % (len(pages2), n2, n2 + 4, drift))
    print("  → %s\n" % pdf)
    close_browser()
    return 0


if __name__ == "__main__":
    sys.exit(main())

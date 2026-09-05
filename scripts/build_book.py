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
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_html import CSS, DRAFT, BUILD, chapters, md_to_html, _inline, _esc   # noqa: E402

TITLE = "말하는 AI 휴먼을 만드는 법"
SUB = "사진 한 장에서 실시간 대화 아바타까지<br>픽셀이 얼굴이 되고, 그 얼굴이 말을 한다"
SERIES = "All That AI · Vol.03"
AUTHOR = "이석창 (Seokchang Lee)"
REPO = "github.com/leelang7"
APP_ORDER = "ABCDEFGHLN"          # 인쇄 부록 순서 (폴더에 있는 것만)

BOOK_CSS = CSS + """
@page{ size:152mm 225mm; margin:17mm 15mm 16mm 15mm; }
body{ background:#fff; font-family:"Noto Serif KR","Batang","Malgun Gothic",serif; }
code, pre{ font-family:"D2Coding","Consolas","Malgun Gothic",monospace; }
.page{ box-shadow:none; margin:0; width:auto; min-height:auto; padding:0; page-break-after:always; }
.page:last-child{ page-break-after:auto; }
.cover{ text-align:center; padding-top:70mm; }
.cover .series{ font-size:10pt; color:var(--muted); letter-spacing:.2em; }
.cover h1{ font-size:26pt; margin:14pt 0 8pt; line-height:1.3; }
.cover .sub{ font-size:11pt; color:#333; margin:0 8mm; line-height:1.6; }
.cover .author{ margin-top:40mm; font-size:12pt; }
.colophon{ font-size:9pt; color:#333; padding-top:120mm; }
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
.tight1 p, .tight1 li{ line-height:1.62; margin:5pt 0; } .tight1 h2{ margin:16pt 0 6pt; }
.tight2 p, .tight2 li{ line-height:1.55; margin:4pt 0; font-size:10.2pt; } .tight2 h2{ margin:14pt 0 5pt; } .tight2 h3{ margin:11pt 0 4pt; }
.tight3 p, .tight3 li{ line-height:1.48; margin:3.4pt 0; font-size:10pt; } .tight3 h2{ margin:12pt 0 4pt; } .tight3 h3{ margin:9pt 0 3pt; }
.tight3 h1.ch{ margin-top:2mm; } .tight3 .tw{ margin:8pt 0; } .tight3 figure{ margin:9pt auto; }
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
                            % (label.replace("+", "plus"), label, title), 1)
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


def online_titles():
    out = []
    for fn in sorted(os.listdir(os.path.join(DRAFT, "online"))):
        if fn.endswith(".md"):
            first = open(os.path.join(DRAFT, "online", fn), encoding="utf-8").readline().strip("# \n")
            out.append(first)
    return out


def front_html(name):
    html, _, _ = md_to_html(read(name), "0", [])
    return '<section class="page">%s</section>' % html


def build(toc_pages=None, tight=None, index_html=None):
    tight = tight or {}
    issues = []
    parts = parts_from_toc()
    ch_files = {label: fn for _, label, fn in chapters()}     # '7', '3+', '28+'
    body, entries = [], []                                    # entries: (kind, key, title, secs)

    body.append('<section class="page cover"><div class="series">%s</div><h1>%s</h1>'
                '<div class="sub">%s</div><div class="author">%s 지음</div></section>' % (SERIES, TITLE, SUB, AUTHOR))
    body.append('<section class="page colophon"><table>'
                '<tr><td>제목</td><td>%s</td></tr><tr><td>시리즈</td><td>%s</td></tr>'
                '<tr><td>지은이</td><td>%s</td></tr><tr><td>판</td><td>초판 1쇄 · 2026년</td></tr>'
                '<tr><td>저장소</td><td>%s</td></tr><tr><td>출판사 · ISBN</td><td>(출판사 기입)</td></tr>'
                '<tr><td>측정 환경</td><td>RTX 4070 SUPER 12GB · Windows 11 · 본문 수치는 부록 C 의 측정 조건 기준</td></tr>'
                '</table><p>본문의 코드는 저장소의 라이선스를, 인용된 외부 모델·라이브러리는 각자의 라이선스를 따릅니다. '
                '이 책의 어떤 부분도 저작권자의 허락 없이 복제·전송할 수 없습니다.</p></section>'
                % (TITLE, SERIES, AUTHOR, REPO))
    for name in ("00_서문.md", "00_이책의_사용법.md", "00_등장인물.md"):
        body.append(front_html(name))

    toc_idx = len(body)
    body.append("TOC_PLACEHOLDER")

    figs = tbls = 0
    used = set()
    for part in parts:
        rows = "".join("<tr><td>%s</td><td><strong>%s</strong></td><td>%s</td></tr>" % (c, _inline(t), _inline(b))
                       for c, t, b in part["chapters"])
        body.append('<section class="page part"><div class="label">%s</div><h1>%s</h1><div class="blurb">%s</div>'
                    '<div class="tw"><table><tbody>%s</tbody></table></div></section>'
                    % (part["label"], _esc(part["title"]), _inline(part["blurb"]), rows))
        entries.append(("part", part["label"], part["title"], []))
        for c, _, _ in part["chapters"]:
            label = c[2:].lstrip("0")                          # 'Ch03+' → '3+', 'Ch07' → '7'
            fn = ch_files.get(label)
            if not fn:
                issues.append("목차의 %s 에 해당하는 원고 파일 없음" % c)
                continue
            used.add(label)
            html, title, secs, nf, nt = chapter_html(label, fn, issues)
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
            body.append('<section class="page%s">%s</section>' % (" " + tight["app" + letter] if ("app" + letter) in tight else "", html))
            entries.append(("app", letter, title, []))
    ol = "".join("<li>%s</li>" % _esc(t) for t in online_titles())
    body.append('<section class="page online"><h1 class="ch" id="online">온라인 부록</h1>'
                '<p>아래 셋은 기준일이 있거나 시리즈 독자용이라 종이에 굳히지 않고 저장소에서 갱신합니다. '
                '<code>%s</code> 의 <code>draft/online/</code> 에서 읽을 수 있습니다.</p><ul>%s</ul></section>' % (REPO, ol))
    entries.append(("app", "online", "온라인 부록", []))

    # 찾아보기 — 쪽 번호는 조판이 끝나야 알 수 있다. 자리만 잡아 두고 마지막 패스에서 채운다.
    idx_idx = len(body)
    body.append('<section class="page index"><h1 class="ch" id="index">찾아보기</h1>'
                + (index_html or "<p>(조판 후 채워집니다)</p>") + "</section>")
    entries.append(("app", "index", "찾아보기", []))

    pages = toc_pages or {}
    lines = ['<section class="page toc"><h1>차례</h1>']
    for kind, key, title, secs in entries:
        if kind == "part":
            lines.append('<div class="p">%s%s</div>' % ("" if key == "부록" else key + ". ", _esc(title)))
            continue
        n = pages.get(kind + key, "")
        name = ("Ch%s  " % key) if kind == "ch" else ""
        lines.append('<div class="c"><span class="t">%s%s</span><span class="n">%s</span></div>' % (name, title, n))
        if secs:
            lines.append('<div class="s">%s</div>' % " · ".join(re.sub(r"<[^>]+>", "", s) for s in secs[:8]))
    lines.append("</section>")
    body[toc_idx] = "\n".join(lines)

    def wrap(sections):
        return ("<!doctype html><html lang=ko><head><meta charset=utf-8><title>%s</title><style>%s</style></head>"
                "<body>\n%s\n</body></html>" % (TITLE, BOOK_CSS, "\n".join(sections)))
    # 표지·판권(앞 두 섹션)은 머리글·쪽번호 없이 따로 찍는다 — 쪽 번호는 서문부터 1
    return wrap(body), issues, figs, tbls, entries, wrap(body[:2]), wrap(body[2:])


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
            if kind == "ch" and (kind + key) not in pages and ("CHAPTER%s" % key) in txt[:60]:   # 장 머리는 쪽 맨 위
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
    html, issues, figs, tbls, entries, html_front, html_body = build()
    out = os.path.join(BUILD, "book.html")
    open(out, "w", encoding="utf-8").write(html)
    print("\n  장 %d · 부록 %d · 도판 %d · 표 %d" % (sum(1 for e in entries if e[0] == "ch"),
                                                   sum(1 for e in entries if e[0] == "app") - 1, figs, tbls))
    for x in issues[:10]:
        print("   · " + x)
    print("  → %s" % out)
    if a.html:
        close_browser()
        return 0
    pdf = os.path.join(BUILD, "book.pdf")
    fh, bh = os.path.join(BUILD, "_front.html"), os.path.join(BUILD, "_body.html")
    fp, bp = os.path.join(BUILD, "_front.pdf"), os.path.join(BUILD, "_body.pdf")
    open(fh, "w", encoding="utf-8").write(html_front)
    render_pdf(fh, fp, header=False)                       # 표지·판권: 머리글·쪽번호 없음
    open(bh, "w", encoding="utf-8").write(html_body)
    render_pdf(bh, bp)
    pages, n = chapter_pages(bp, entries)                  # 쪽 번호는 본문 기준(서문이 1쪽)
    # 차례 쪽 번호 맞추기(2패스)는 카피피팅이 끝난 뒤에 한다 — 그 전에 맞춰 봐야
    # 행간을 줄이는 순간 전부 어긋난다. 렌더 한 번(약 1분)이 여기서 줄어든다.
    pages2, n2 = pages, n
    # ── 카피피팅: 마지막 쪽이 거의 빈 장은 행간을 조금 줄여 다시 짠다 (최대 2단계) ──
    from pypdf import PdfReader as _R
    tight = {}
    for level in ("tight1", "tight2", "tight3"):
        r = _R(bp); texts = [(pg.extract_text() or "").strip() for pg in r.pages]
        keys = [(k, v) for k, v in sorted(pages2.items(), key=lambda kv: kv[1])]
        spill = []
        for idx, (k, start) in enumerate(keys):
            end = keys[idx + 1][1] - 1 if idx + 1 < len(keys) else len(texts)
            if end > start and len(texts[end - 1]) < 350 and tight.get(k) != "tight3":
                spill.append(k)
        if not spill:
            break
        for k in spill:
            tight[k] = level
        *_, html_body2 = build(toc_pages=pages2, tight=tight)
        open(bh, "w", encoding="utf-8").write(html_body2)
        render_pdf(bh, bp)
        pages2, n2 = chapter_pages(bp, entries)
        print("  카피피팅 %s: %d개 장/부록 조정" % (level, len(spill)))
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
    for src in (fp, bp):
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
            label = ("Ch%s  %s" % (key, plain)) if kind == "ch" else plain
            w.add_outline_item(label, pages2[kind + key] - 1 + front_n, parent=parent)
    w.add_metadata({"/Title": TITLE, "/Author": AUTHOR, "/Subject": SERIES, "/Creator": "build_book.py (Chromium)"})
    w.write(pdf)
    for f in (fh, bh, fp, bp):
        os.remove(f)
    print("  차례 쪽 번호 %d개 · 본문 %d쪽 + 앞 2쪽 = %d쪽 · 2패스 후 어긋난 항목 %d" % (len(pages2), n2, n2 + 2, drift))
    print("  → %s\n" % pdf)
    close_browser()
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""전자책(EPUB) 빌드 — 부크크 전자책 · 유페이퍼 제출용

종이책(build_book.py)과 같은 원고를 쓰되, 인쇄 장치는 전부 뺀다.
    · 쪽 번호·머리글·거울 여백·짝수 맞춤 없음 (재유동 형식이라 '쪽' 이 없다)
    · 찾아보기 없음 — 쪽 번호가 없으니 색인은 뜻이 없다. 대신 목차를 깊게 준다
    · 도판은 파일을 그대로 싣고, 캡션은 figcaption 으로

pandoc(pypandoc) 으로 만든다. 표지는 앞표지 이미지(ebook/cover/cover_final_2k.png).

    python scripts/build_epub.py
    python scripts/build_epub.py --out ebook/AI휴먼해부학.epub
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT = os.path.join(ROOT, "draft")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

TITLE = "AI 휴먼 해부학"
SUB = "얼굴·목소리·두뇌·기억 — 네 층을 조립하고 실측하는 법"
AUTHOR = "이석창"
SERIES = "All That AI · Vol.03"
APP_ORDER = "ABCDEFGHLN"

COLOPHON = """
# 판권

**AI 휴먼 해부학**

발 행 | 2026 년 09 월 08 일

저 자 | 이석창

펴낸이 | 한건희

펴낸곳 | 주식회사 부크크

출판사등록 | 2014.07.15.(제2014-16호)

주 소 | 서울특별시 금천구 가산디지털1로 119 SK트윈타워 A동 305호

전 화 | 1670-8316

이메일 | info@bookk.co.kr

ISBN | 979-11-12-28705-2

www.bookk.co.kr

ⓒ 이석창 2026

본 책은 저작자의 지적 재산으로서 무단 전재와 복제를 금합니다.
"""

CSS = """
body { line-height: 1.7; }
h1 { font-size: 1.5em; margin: 1.2em 0 0.6em; }
h2 { font-size: 1.2em; margin: 1.4em 0 0.4em; }
h3 { font-size: 1.05em; margin: 1.1em 0 0.3em; }
p { margin: 0.6em 0; text-align: justify; }
blockquote { border-left: 3px solid #F59E0B; margin: 0.9em 0; padding: 0.4em 0.9em;
             background: #fbf7ef; }
pre { background: #f4f5f7; padding: 0.6em; border-radius: 4px; font-size: 0.82em;
      white-space: pre-wrap; word-break: break-all; }
code { font-size: 0.9em; }
table { border-collapse: collapse; width: 100%; font-size: 0.82em; margin: 0.8em 0; }
tr { page-break-inside: avoid; }
thead { display: table-header-group; }
th, td { border: 1px solid #ccc; padding: 3px 6px; text-align: left; }
th { background: #f2f4f8; }
img { max-width: 100%; }
figcaption, .cap { font-size: 0.82em; color: #555; text-align: center; margin-top: 0.3em; }
"""


def chapters():
    out = []
    for fn in sorted(os.listdir(DRAFT)):
        m = re.match(r"ch(\d+)(plus)?_", fn)
        if m and fn.endswith(".md"):
            label = m.group(1).lstrip("0") + ("+" if m.group(2) else "")
            out.append((float(m.group(1)) + (0.5 if m.group(2) else 0), label, fn))
    return sorted(out)


def appendix_files():
    out = {}
    for fn in os.listdir(os.path.join(DRAFT, "appendix")):
        m = re.match(r"app([A-Z])_.*\.md$", fn)
        if m:
            out[m.group(1)] = fn
    return out


def read(rel):
    return open(os.path.join(DRAFT, rel), encoding="utf-8").read()


def fix_paths(md, base):
    """도판 상대 경로를 원고 폴더 기준 절대 경로로 — pandoc 이 그 자리에서 읽는다."""
    def sub(m):
        alt, path = m.group(1), m.group(2)
        if path.startswith(("http:", "https:")):
            return m.group(0)
        return "![%s](%s)" % (alt, os.path.join(base, path).replace("\\", "/"))
    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", sub, md)


def build_markdown():
    parts = []
    parts.append("# %s\n\n**%s**\n\n%s · %s 지음\n" % (TITLE, SUB, SERIES, AUTHOR))
    for name in ("00_서문.md", "00_이책의_사용법.md", "00_등장인물.md"):
        parts.append(fix_paths(read(name), DRAFT))
    for _, label, fn in chapters():
        parts.append(fix_paths(read(fn), DRAFT))
    apps = appendix_files()
    for letter in APP_ORDER:
        if letter in apps:
            parts.append(fix_paths(read(os.path.join("appendix", apps[letter])),
                                   os.path.join(DRAFT, "appendix")))
    for name in ("98_참고문헌.md", "97_저자후기.md"):
        parts.append(fix_paths(read(name), DRAFT))
    parts.append(COLOPHON)
    md = "\n\n".join(parts)
    # 인쇄 전용 표기 정리 — '표:' 캡션 줄은 표 위 설명으로 그대로 두되, 쪽 참조는 없다
    md = md.replace("\r\n", "\n")
    return md



COVER_PAGE = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ko">
<head><title>앞표지</title><meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<style type="text/css">body{margin:0;padding:0;text-align:center}img{max-width:100%;height:auto}</style></head>
<body><div><img src="{IMG}" alt="" /></div></body>
</html>
"""


def insert_cover_page(path):
    """부크크 요청(2026-09-16) — 원고 1페이지를 앞표지로.

    pandoc 이 만든 표지(cover.xhtml)는 읽기 도구가 표지로만 다루기도 해서,
    본문 첫 쪽으로도 같은 그림을 한 장 더 놓는다. 그림은 이미 안에 있는 것을 가리키므로
    파일 크기는 거의 안 늘어난다.
    """
    import re
    import shutil
    import zipfile

    src = zipfile.ZipFile(path)
    names = src.namelist()
    opf_name = [n for n in names if n.endswith(".opf")][0]
    opf = src.read(opf_name).decode("utf-8")
    cover_id = re.search(r'<meta[^>]*name="cover"[^>]*content="([^"]+)"', opf)
    if not cover_id:
        src.close()
        print("  ⚠ 표지 메타데이터가 없다 — 앞표지 쪽을 넣지 못했다")
        return
    href = re.search(r'<item id="%s"[^>]*href="([^"]+)"' % re.escape(cover_id.group(1)), opf).group(1)
    base = opf_name.rsplit("/", 1)[0] + "/" if "/" in opf_name else ""
    page_href = "text/coverpage.xhtml"
    rel = "../" + href if href.startswith("media/") else href

    opf2 = opf.replace("</manifest>",
                       '  <item id="coverpage" href="%s" media-type="application/xhtml+xml" />\n  </manifest>'
                       % page_href, 1)
    # 읽기 순서 — 표지 다음, 나머지 앞
    m = re.search(r'<spine[^>]*>\s*', opf2)
    after = re.search(r'(<itemref[^>]*idref="[^"]*cover[^"]*"[^>]*/>)', opf2)
    ref = '<itemref idref="coverpage" />'
    if after:
        opf2 = opf2.replace(after.group(1), after.group(1) + "\n    " + ref, 1)
    else:
        opf2 = opf2[:m.end()] + ref + "\n    " + opf2[m.end():]

    tmp = path + ".tmp"
    out = zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED)
    out.writestr(src.getinfo("mimetype"), src.read("mimetype"), zipfile.ZIP_STORED)
    for n in names:
        if n == "mimetype":
            continue
        out.writestr(n, opf2.encode("utf-8") if n == opf_name else src.read(n))
    out.writestr(base + page_href, COVER_PAGE.replace("{IMG}", rel).encode("utf-8"))
    out.close()
    src.close()
    shutil.move(tmp, path)
    print("  원고 1쪽 = 앞표지 (%s)" % rel)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "ebook", "AI휴먼해부학_Vol03.epub"))
    ap.add_argument("--md", action="store_true", help="합친 마크다운만 저장하고 끝낸다")
    a = ap.parse_args()

    md = build_markdown()
    build_dir = os.path.join(ROOT, "build")
    os.makedirs(build_dir, exist_ok=True)
    md_path = os.path.join(build_dir, "_epub.md")
    open(md_path, "w", encoding="utf-8", newline="\n").write(md)
    print("  합친 원고 %d자 → %s" % (len(md), md_path))
    if a.md:
        return 0

    css_path = os.path.join(build_dir, "_epub.css")
    open(css_path, "w", encoding="utf-8", newline="\n").write(CSS)
    meta_path = os.path.join(build_dir, "_epub_meta.yaml")
    meta = ["---", "title: '%s'" % TITLE, "subtitle: '%s'" % SUB,
            "author: '%s'" % AUTHOR, "lang: ko",
            "description: '%s — %s'" % (SERIES, SUB),
            "rights: 'Copyright 2026 %s. All rights reserved.'" % AUTHOR, "---", ""]
    open(meta_path, "w", encoding="utf-8", newline=chr(10)).write(chr(10).join(meta))

    # 부크크가 로고를 찍어 보내 준 앞표지 — 우리 원본(cover_final_2k.png)이 아니라 이것을 쓴다.
    cover = os.path.join(ROOT, "ebook", "cover", "bookk_front.jpeg")
    import pypandoc
    args = ["--toc", "--toc-depth=2", "--split-level=1",
            "--css=" + css_path, "--metadata-file=" + meta_path,
            "--resource-path=" + DRAFT]
    if os.path.exists(cover):
        args.append("--epub-cover-image=" + cover)
    # 부크크는 외부유통에 **EPUB 2.0** 만 받는다(EPUB3 불가) — Vol.02 에서 겪은 것.
    pypandoc.convert_file(md_path, "epub2", format="markdown+pipe_tables+backtick_code_blocks",
                          outputfile=a.out, extra_args=args)
    insert_cover_page(a.out)                   # 부크크 요청 — 원고 1페이지를 앞표지로
    size = os.path.getsize(a.out) / 1024 / 1024
    print("  → %s  (EPUB2 · %.1fMB)" % (a.out, size))
    if size >= 20:
        print("  ⚠ 부크크 전자책 상한 20MB 를 넘었다 — 도판을 줄여야 한다(Vol.02 는 shrink_epub.py 로 눌렀다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

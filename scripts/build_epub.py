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

| | |
|---|---|
| 제목 | AI 휴먼 해부학 — 얼굴·목소리·두뇌·기억, 네 층을 조립하고 실측하는 법 |
| 시리즈 | All That AI · Vol.03 |
| 초판 1쇄 발행 | 2026년 9월 |
| 지은이 | 이석창 (Seokchang Lee) |
| 펴낸곳 | 주식회사 부크크 |
| 컴패니언 저장소 | github.com/leelang7/talking-ai-human-book |
| 측정 환경 | RTX 4070 SUPER 12GB · Windows 11 · 본문 수치는 부록 C의 측정 조건 기준 |

ⓒ 이석창 2026. 본 책은 저작자의 지적 재산이므로 무단 전재와 복제를 금합니다.
본문의 코드는 저장소의 라이선스를, 인용된 외부 모델·라이브러리는 각자의 라이선스를 따릅니다.
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
table { border-collapse: collapse; width: 100%; font-size: 0.85em; margin: 0.8em 0; }
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

    cover = os.path.join(ROOT, "ebook", "cover", "cover_final_2k.png")
    import pypandoc
    args = ["--toc", "--toc-depth=2", "--split-level=1",
            "--css=" + css_path, "--metadata-file=" + meta_path,
            "--resource-path=" + DRAFT]
    if os.path.exists(cover):
        args.append("--epub-cover-image=" + cover)
    pypandoc.convert_file(md_path, "epub3", format="markdown+pipe_tables+backtick_code_blocks",
                          outputfile=a.out, extra_args=args)
    size = os.path.getsize(a.out)
    print("  → %s  (%.1fMB)" % (a.out, size / 1024 / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())

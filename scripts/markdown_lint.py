"""Markdown 파일 *일관성·서식* 점검.

다음 5 카테고리:
    1. 줄 길이 (default 200자) — 너무 긴 줄은 PDF 변환 시 깨짐
    2. 헤더 깊이 (## 부터 시작, # 1 회만)
    3. 트레일링 공백 / 탭 혼합
    4. 빈 링크 텍스트 (`[](url)`)
    5. *우리집* 표기 일관성 — 본문에서 *우리 집* 띄어쓰기 권장 X

본 점검은 *경고만* — fail 처리 X (출간 후 정오 후보 카운트).

사용:
    python scripts/markdown_lint.py                 # 전체
    python scripts/markdown_lint.py --path file.md  # 단일 파일
    python scripts/markdown_lint.py --strict        # warn fail 화
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]

TARGET_GLOBS = ["*.md", "draft/**/*.md", "ebook/**/*.md", "code/**/*.md"]
SKIP = {"__pycache__", ".pytest_cache", "_run_all", "_train_queue", "_broll", "_xai_out"}

MAX_LINE = 200
LONG_LINE_TOLERANCE = 3   # 한 파일당 3 줄 까지는 OK


def collect_md_files() -> List[Path]:
    files: List[Path] = []
    for g in TARGET_GLOBS:
        for f in ROOT.glob(g):
            if any(part in SKIP or part.startswith("_") for part in f.parts):
                continue
            if f.is_file() and f.suffix == ".md":
                files.append(f)
    return sorted(set(files))


def check_file(path: Path) -> Tuple[int, int, List[str]]:
    """반환: (warn, fail, 메시지 리스트)"""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    warns: List[str] = []
    fails: List[str] = []

    # 1. 줄 길이
    long_lines = [i for i, ln in enumerate(lines, 1)
                  if len(ln) > MAX_LINE and not ln.lstrip().startswith("|")
                  and not ln.lstrip().startswith("```")]
    # 표 라인은 제외 (한글 표가 길어질 수 있음)
    if len(long_lines) > LONG_LINE_TOLERANCE:
        warns.append(f"긴 줄 {len(long_lines)}개 (>{MAX_LINE}자)")

    # 2. 헤더 깊이
    h1_count = sum(1 for ln in lines if ln.startswith("# ") and not ln.startswith("## "))
    if h1_count > 1:
        warns.append(f"H1 (# ) {h1_count}회 — 1회만 권장")

    # 3. 트레일링 공백
    trailing = sum(1 for ln in lines if ln.endswith(" ") and ln.strip())
    if trailing > 5:
        warns.append(f"트레일링 공백 {trailing}줄")

    # 4. 탭 혼합 (markdown 은 스페이스 권장)
    tab_lines = sum(1 for ln in lines if "\t" in ln)
    if tab_lines > 0:
        warns.append(f"탭 문자 {tab_lines}줄")

    # 5. 빈 링크 텍스트
    empty_links = len(re.findall(r"\[\]\([^)]+\)", text))
    if empty_links > 0:
        warns.append(f"빈 링크 텍스트 {empty_links}개")

    # 6. *우리집* vs *우리 집* 혼용
    spaced = len(re.findall(r"우리\s+집", text))
    unspaced = len(re.findall(r"우리집", text))
    if spaced > 0 and unspaced > spaced * 5:
        warns.append(f"*우리집* 표기 혼용: 띄어쓰기 {spaced}회 (붙임 {unspaced}회 권장)")

    return (len(warns), len(fails), warns)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--path", help="단일 파일")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args()

    if args.path:
        files = [Path(args.path)]
    else:
        files = collect_md_files()

    print(f"Markdown 일관성 점검 — {len(files)} 파일")
    print("=" * 64)

    total_warn = 0
    total_fail = 0
    files_with_warn = 0
    for f in files:
        warn, fail, msgs = check_file(f)
        if warn or fail:
            rel = f.relative_to(ROOT).as_posix()
            icon = "❌" if fail else "⚠"
            print(f"  {icon} {rel}")
            for m in msgs:
                print(f"     · {m}")
            total_warn += warn
            total_fail += fail
            files_with_warn += 1

    print()
    print(f"  파일 {len(files)} · 경고 있는 파일 {files_with_warn} · 총 경고 {total_warn} · FAIL {total_fail}")
    if total_fail or (args.strict and total_warn):
        sys.exit(1)
    if total_warn == 0:
        print("🎉 모든 markdown 일관성 통과")
    else:
        print("ℹ 경고만 — 출간 후 정오 후보로 누적")


if __name__ == "__main__":
    main()

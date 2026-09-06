"""저장소 내 markdown 의 *상대 경로 링크* 가 실제 파일을 가리키는지 점검.

외부 URL (http/https) 과 mailto: 는 *건드리지 않음*.
부록·README·INDEX·CHANGELOG·HEALTH 등의 *내부 링크* 만 검증.

사용:
    python scripts/check_dead_links.py
    python scripts/check_dead_links.py --strict   # warn 도 fail
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]

# 점검 대상 markdown 파일 패턴
TARGET_GLOBS = [
    "*.md",
    "draft/*.md",
    "draft/appendix/*.md",
    "ebook/*.md",
    "code/**/*.md",
]

# 무시할 디렉터리
SKIP_DIRS = {"__pycache__", ".pytest_cache", "_run_all_*", "_train_queue",
             "_broll", "_xai_out", "_site", ".venv"}

LINK_RE = re.compile(r"\]\(([^)]+)\)")
URL_PREFIXES = ("http://", "https://", "mailto:", "ftp://", "tel:")


def collect_md_files() -> List[Path]:
    files: List[Path] = []
    for g in TARGET_GLOBS:
        for f in ROOT.glob(g):
            if any(part in SKIP_DIRS for part in f.parts):
                continue
            if f.is_file() and f.suffix == ".md":
                files.append(f)
    return sorted(set(files))


def extract_links(md_path: Path) -> List[Tuple[int, str]]:
    """반환: [(라인번호, 링크 경로), ...]"""
    out: List[Tuple[int, str]] = []
    try:
        text = md_path.read_text(encoding="utf-8")
    except Exception:
        return out
    for i, line in enumerate(text.splitlines(), 1):
        for m in LINK_RE.finditer(line):
            target = m.group(1).strip()
            # 외부 URL 제외
            if target.lower().startswith(URL_PREFIXES):
                continue
            # 앵커만 (`#section`)
            if target.startswith("#"):
                continue
            # 코드 블록 fence 안의 ``` 등은 별도 처리 안 함
            # 쿼리·앵커 분리
            target = target.split("#", 1)[0].split("?", 1)[0].strip()
            if not target:
                continue
            out.append((i, target))
    return out


def resolve(md_path: Path, target: str) -> Path:
    """md 파일 기준 상대 경로 해석. 절대 경로(/x)는 ROOT 기준."""
    if target.startswith("/"):
        return (ROOT / target.lstrip("/")).resolve()
    return (md_path.parent / target).resolve()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--strict", action="store_true",
                   help="warn 도 fail 처리")
    args = p.parse_args()

    print("죽은 링크 점검 (내부 상대 경로만)")
    print("=" * 64)

    files = collect_md_files()
    print(f"  점검 대상 markdown : {len(files)} 파일")

    total_links = 0
    dead: List[Tuple[Path, int, str]] = []
    for f in files:
        for ln, target in extract_links(f):
            total_links += 1
            tgt = resolve(f, target)
            if not tgt.exists():
                dead.append((f, ln, target))

    print(f"  총 내부 링크 : {total_links}")
    print(f"  죽은 링크 : {len(dead)}")
    if dead:
        print()
        for f, ln, target in dead[:30]:
            rel = f.relative_to(ROOT).as_posix()
            print(f"  ❌ {rel}:{ln} → {target}")
        if len(dead) > 30:
            print(f"  ... 외 {len(dead) - 30} 건")
        # 분류 — *템플릿 비어있는 placeholder* 는 보통 OK 처리
        placeholder_only = all(
            "REPLACE_ME" in t or "TODO" in t.upper() or
            "_path" in t or t.endswith(".pdf") or t.endswith(".pt")
            for _, _, t in dead
        )
        if placeholder_only:
            print("  (모두 *템플릿 placeholder* — 출간 후 채워질 자료)")
            print("\n  ⚠ 죽은 링크가 모두 placeholder 라 warn 처리")
            if args.strict:
                sys.exit(1)
            return
        if args.strict or len(dead) > 50:
            sys.exit(1)
        print("\n  ⚠ 일부 죽은 링크 — 다음 갱신 시 검토")
        return

    print("\n🎉 모든 내부 링크가 유효")


if __name__ == "__main__":
    main()

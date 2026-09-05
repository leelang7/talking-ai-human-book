# -*- coding: utf-8 -*-
"""
코드 참조 대조 — 원고가 이름으로 가리키는 것이 코드에 실제로 있는가

원고는 `is_self_echo()` · `leak_scan` · `rig.py` 처럼 코드를 **이름으로** 가리킨다.
그 이름이 코드에 없으면 독자는 없는 것을 찾는다.

실제로 이 검사가 찾은 것 —
    Ch07 이 "회귀 테스트가 지킨다" 고 쓴 케이스가 테스트에 없었고, 동작도 없었다
    Ch16 이 부르는 파라미터 넷(`mouthOpen` 등)이 `ch16_parts/` 에 없었다
    Ch28+ 가 처방한 `unblock` 플래그 엔드포인트가 콘솔에 없었다

셋 다 코드를 만들어 채웠다. **원고가 코드를 가리키면 코드가 그 자리에 있어야 한다.**

오탐이 있다. 프롬프트 단어(`headshot`), 예외 이름(`TypeError`), 어댑터 파일명,
남의 라이브러리 옵션(`driving_multiplier`)은 코드 폴더에 없는 것이 정상이다.
그런 것은 아래 목록으로 뺀다 — **뺄 때는 왜 빼는지 적는다.**

    python scripts/code_refs.py
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 코드 폴더에 없는 것이 정상인 이름들. 이유를 같이 적는다.
ALLOW = {
    # 생성 모델 프롬프트 어휘 (Ch04 §4) — 코드가 아니라 프롬프트에 쓰는 단어
    "headshot", "illustration", "portrait",
    # 파이썬 예외 이름 (Ch10 §4) — 표준 라이브러리
    "AttributeError", "TypeError", "ValueError", "RuntimeError",
    # 남의 라이브러리 옵션 이름 (Ch12) — LivePortrait 의 인자
    "driving_multiplier", "driving_option", "animation_region",
    # Ch18 의 VRM 표정 이름 — three-vrm 의 blendshape 키
    "blink", "aa",
    # Chatterbox 요청 파라미터 (Ch03+) — ATL 서버가 받는 값. 라우팅은 code/ch03plus_dialect
    "exaggeration", "cfg_weight", "drama",
    # 흔한 일반어
    "python", "ffmpeg", "true", "false", "None", "null", "undefined",
}
# 접두가 이것이면 어댑터·모델 파일명이다 (Ch03+)
ALLOW_PREFIX = ("cbx_", "mixamorig")

TOKEN = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)(?:\(\))?`")
FILE = re.compile(r"`([a-z_][a-z0-9_]*\.(?:py|html|js|json))`")


def code_corpus():
    text, names = [], set()
    for p in glob.glob(os.path.join(ROOT, "code", "**", "*.*"), recursive=True):
        names.add(os.path.basename(p))
        if p.endswith((".py", ".html", ".js")):
            text.append(open(p, encoding="utf-8", errors="replace").read())
    return "\n".join(text), names


def main():
    code, files = code_corpus()
    missing = {}
    for md in sorted(glob.glob(os.path.join(ROOT, "draft", "ch*.md"))):
        t = open(md, encoding="utf-8").read()
        ch = os.path.basename(md)
        for m in FILE.finditer(t):
            if m.group(1) not in files:
                missing.setdefault(ch, set()).add(m.group(1))
        for m in TOKEN.finditer(t):
            ident = m.group(1)
            if len(ident) < 5 or ident in ALLOW or ident.startswith(ALLOW_PREFIX):
                continue
            if ident.endswith((".py", ".html")):
                continue
            if re.search(r"\b" + re.escape(ident) + r"\b", code) is None:
                missing.setdefault(ch, set()).add(ident)

    n = sum(len(v) for v in missing.values())
    print(f"\n  원고가 이름으로 가리키는데 코드에 없는 것 — {n}건 / {len(missing)}개 장")
    for ch, ids in sorted(missing.items()):
        print(f"    {ch:34} {', '.join(sorted(ids))}")
    print()
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())

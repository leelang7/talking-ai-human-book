# -*- coding: utf-8 -*-
"""
절 재번호 — 임시 표기 `X.Y+` 를 정식 번호로 흡수한다

집필 중에 절을 사이에 끼워 넣을 때 `7.9+` 같은 표기를 썼다. 그때는 뒤 번호를
전부 밀지 않아도 되니 편하지만, **남겨 두면 목차가 이상해지고 참조가 헷갈린다.**
자기비판 B3 이 오래 열려 있던 항목이다.

혼자서는 위험한 작업이다. 절 번호를 밀면 `Ch07 §9` 같은 참조가 조용히
다른 절을 가리키게 된다. 원고에는 그런 참조가 **200개 넘게** 있다.

그래서 이 스크립트는 세 가지를 같이 한다.

    ① 제목을 새 번호로 바꾼다
    ② 그 장을 가리키는 `ChNN §M` 을 전부 다시 매핑한다
    ③ 장 안의 맨 `§M` 도 다시 매핑한다   ← 이게 제일 많고 제일 잘 빠뜨린다

끝나면 `scripts/qc.py` 의 절 참조 검사가 무결성을 확인한다.

    python scripts/renumber.py           무엇이 바뀌는지만 본다 (기본)
    python scripts/renumber.py --apply   실제로 고친다
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT = os.path.join(ROOT, "draft")

HEAD = re.compile(r"^##\s+(\d+\+?)\.(\d+)(\+*)\s+(.*)$", re.M)


def chapter_key(path):
    m = re.match(r"ch(\d+)(plus)?_", os.path.basename(path))
    return m.group(1).lstrip("0") + ("+" if m.group(2) else "") if m else None


def plan_for(text):
    """(옛 라벨 → 새 번호) 매핑과 (옛, 새, 제목) 목록.

    `19.1+` 는 19.1 과 19.2 **사이** 에 끼워 넣은 절이므로, 나타나는 순서대로
    1부터 다시 세면 된다. 원고의 물리적 순서가 곧 정답이다.
    """
    heads = HEAD.findall(text)
    if not any(h[2] for h in heads):
        return None                       # 임시 표기가 없으면 건드리지 않는다
    mapping, rows = {}, []
    for i, (major, minor, plus, title) in enumerate(heads, start=1):
        old = f"{major}.{minor}{plus}"
        rows.append((old, f"{major}.{i}", title))
        mapping[old] = i
    return mapping, rows


def _old_to_new(mapping):
    """`19.4` → 5 형태의 정수 매핑. `+` 표기는 원래 번호가 없으므로 제외한다."""
    out = {}
    for old, new in mapping.items():
        if not old.endswith("+"):
            out[int(old.split(".")[1])] = new
    return out


def remap_bare(text, mapping):
    """장 안의 맨 `§N` 을 새 번호로.

    **다른 장을 가리키는 `Ch20 §6` 은 건드리면 안 된다.** 앞에 장 번호가 붙어
    있으면 그건 이 장의 절이 아니다. 그것들은 remap_cross 가 각자의 매핑으로
    처리한다. 이 구분을 빠뜨리면 남의 장 참조가 조용히 어긋난다.

    연쇄 충돌(9→10 을 먼저 하면 그 10 을 다시 11 로)은 걱정하지 않아도 된다 —
    `re.sub` 는 원본을 **한 번만** 훑고 자기가 넣은 결과를 다시 보지 않는다.
    """
    o2n = _old_to_new(mapping)
    pat = re.compile(r"(Ch\d+\+?\s*§\s*\d+)"       # 다른 장 참조 — 손대지 않음
                     r"|(부록 [A-N]\s*§\s*\d+)"     # 부록 참조 — 손대지 않음
                     r"|§\s*(\d+)")                 # 이 장의 절

    def sub(m):
        if m.group(1) or m.group(2):
            return m.group(0)
        n = int(m.group(3))
        return f"§{o2n.get(n, n)}"

    return pat.sub(sub, text)


def remap_cross(text, chapter, mapping):
    """다른 문서에서 이 장을 가리키는 `ChNN §M`."""
    o2n = _old_to_new(mapping)
    pat = re.compile(r"(Ch0*" + re.escape(chapter) + r"\s*§\s*)(\d+)")

    def sub(m):
        return f"{m.group(1)}{o2n.get(int(m.group(2)), int(m.group(2)))}"

    return pat.sub(sub, text)


def main():
    apply = "--apply" in sys.argv
    plans = {}
    for p in sorted(glob.glob(os.path.join(DRAFT, "ch*.md"))):
        pl = plan_for(open(p, encoding="utf-8").read())
        if pl:
            plans[p] = pl

    if not plans:
        print("\n  임시 절번호가 없습니다. 할 일 없음.\n")
        return 0

    print(f"\n  {'적용' if apply else '미리보기'} — 대상 {len(plans)}개 장\n")
    for p, (mapping, rows) in plans.items():
        print(f"  Ch{chapter_key(p)}  ({os.path.basename(p)})")
        for old, new, title in rows:
            if old != new:
                print(f"     {old:>7} → {new:<7}  {title[:38]}")
        print()

    if not apply:
        print("  실제로 고치려면 --apply\n")
        return 0

    # ① 제목 + ③ 장 내부 맨 §
    for p, (mapping, rows) in plans.items():
        t = open(p, encoding="utf-8").read()
        t = remap_bare(t, mapping)
        for old, new, title in rows:
            t = t.replace(f"## {old} {title}", f"## {new} {title}")
        open(p, "w", encoding="utf-8").write(t)

    # ② 모든 문서에서 ChNN §M
    for q in glob.glob(os.path.join(DRAFT, "**", "*.md"), recursive=True):
        t = o = open(q, encoding="utf-8").read()
        for p, (mapping, _rows) in plans.items():
            t = remap_cross(t, chapter_key(p), mapping)
        if t != o:
            open(q, "w", encoding="utf-8").write(t)

    print("  적용했습니다. `python scripts/qc.py` 로 참조 무결성을 확인하세요.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

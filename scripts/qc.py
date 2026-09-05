# -*- coding: utf-8 -*-
"""
원고 QC — 순서 · 체계성 · 내용 · 품질 자동 검증

이 책은 Ch09(싱크 검증)와 Ch27(회귀 게이트)에서 "사람의 주의력이 아니라 자동 게이트"를
주장한다. 원고 자체에 그것을 적용하지 않으면 앞뒤가 안 맞는다.

실행:  python scripts/qc.py            (종료 코드 0 = 통과)
       python scripts/qc.py --verbose
"""
import argparse
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT = os.path.join(ROOT, "draft")
APPDIR = os.path.join(DRAFT, "appendix")
ONLINEDIR = os.path.join(DRAFT, "online")

FAIL, WARN = [], []


def fail(cat, msg):
    FAIL.append((cat, msg))


def warn(cat, msg):
    WARN.append((cat, msg))


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def chapters():
    """ch*.md 를 장 번호 순으로. ch28plus 는 28.5 로 정렬."""
    out = []
    for fn in os.listdir(DRAFT):
        m = re.match(r"ch(\d+)(plus)?_", fn)
        if m and fn.endswith(".md"):
            n = int(m.group(1)) + (0.5 if m.group(2) else 0)
            out.append((n, fn, read(os.path.join(DRAFT, fn))))
    return sorted(out)


def appendices(d=None):
    d = d or APPDIR
    out = {}
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        m = re.match(r"app([A-Z]+)_", fn)
        if m and fn.endswith(".md"):
            out[m.group(1)] = (fn, read(os.path.join(d, fn)))
    return out


# ── 1. 체계성: 장마다 같은 뼈대를 갖추었는가 ──────────────────────────
def check_structure(chs):
    for n, fn, t in chs:
        label = f"Ch{n:g}"
        if not re.match(r"^# ", t):
            fail("체계성", f"{label} H1 제목 없음 ({fn})")
        if "이 장에서 기억할 것" not in t:
            fail("체계성", f"{label} '이 장에서 기억할 것' 없음")
        if "**실습 코드**" not in t and "**실습 자료**" not in t:
            warn("체계성", f"{label} 실습 코드 푸터 없음")
        if "예상 소요" not in t:
            warn("체계성", f"{label} 예상 소요 없음")


# ── 2. 순서: 절 번호가 단조 증가하는가 ───────────────────────────────
def check_section_order(chs):
    for n, fn, t in chs:
        label = f"Ch{n:g}"
        # ★ float 로 파싱하면 안 된다 — "7.10" 이 7.1 이 되어 7.9 보다 작아진다.
        #   절 번호는 (주, 부, 삽입) 정수쌍이다.
        #   "19.1+" 는 19.1 과 19.2 **사이** 에 끼워 넣은 절이다(초안 임시 표기).
        #   개정판 재번호 때 정식 번호로 흡수한다 — 자기비판 B3 참조.
        secs = re.findall(r"^## (\d+)(?:\+)?\.(\d+)(\+?)", t, re.M)
        nums = [(int(a), int(b), 1 if plus else 0) for a, b, plus in secs]
        for a, b in zip(nums, nums[1:]):
            if b <= a:
                fail("순서", f"{label} 절 번호 역행/중복: {a[0]}.{a[1]} → {b[0]}.{b[1]}")
        plus = [f"{x[0]}.{x[1]}+" for x in nums if x[2]]
        if plus:
            warn("순서", f"{label} 임시 절번호 {', '.join(plus)} — 개정판 재번호 대상")
        # '++' 는 금지. 같은 자리에 두 번 끼워 넣을 상황이면 그 장은 재번호할 때다.
        if re.search(r"^## \d+\.\d+\+\+", t, re.M):
            fail("순서", f"{label} '++' 절번호 — 임시표기 남발. 장 전체를 재번호하세요")
        # '기억할 것'이 마지막 절인가.
        # Ch30 은 예외 — 시리즈를 닫는 '마지막 한 줄'로 끝나는 것이 의도된 구성이다.
        last = re.findall(r"^## [\d.+]+ (.+)$", t, re.M)
        if last and "기억할 것" not in last[-1] and n != 30:
            warn("순서", f"{label} 마지막 절이 '기억할 것'이 아님: {last[-1][:30]}")


# ── 3. 참조 무결성: 가리키는 곳이 실제로 있는가 ──────────────────────
def check_refs(chs, apps):
    ONLINE = appendices(ONLINEDIR)
    valid_ch = {int(n) if n == int(n) else n for n, _, _ in chs}
    ch_ints = {int(n) for n, _, _ in chs}
    all_docs = [(f"Ch{n:g}", t) for n, _, t in chs] + \
               [(f"부록{k}", t) for k, (_, t) in apps.items()]
    for name, t in all_docs:
        for m in re.finditer(r"Ch(\d+)", t):
            if int(m.group(1)) not in ch_ints:
                fail("참조", f"{name} → 없는 장 Ch{m.group(1)}")
        for m in re.finditer(r"부록 ([A-Z]{1,2})\b", t):
            # Vol.01/02 의 부록을 가리키는 문맥은 이 권의 부록이 아니다
            if re.search(r"Vol\.0[12][^.]{0,12}$", t[max(0, m.start() - 20):m.start()]):
                continue
            # '온라인 부록 X' — 저장소 배포본. 인쇄 부록에 없어도 정상이다.
            if t[max(0, m.start() - 4):m.start()] == "온라인 ":
                if m.group(1) not in ONLINE:
                    fail("참조", f"{name} → 없는 온라인 부록 {m.group(1)}")
                continue
            if m.group(1) not in apps:
                fail("참조", f"{name} → 없는 부록 {m.group(1)}")


# ── 4. 부록 고아: 본문에서 한 번도 안 불리는 부록 ────────────────────
def check_orphans(chs, apps):
    """본문 참조는 두 형태다 — 문장 속 '부록 L' 과 푸터의 '관련 부록 : L(…), N(…)'."""
    body = "\n".join(t for _, _, t in chs)
    footer_letters = set()
    known = set(apps) | set(appendices(ONLINEDIR))       # 인쇄 + 온라인
    for cname, _cno, ctext in chs:
        for m in re.finditer(r"관련 부록\*{0,2}\s*[:：]\s*(.+)", ctext):
            # **여는 괄호가 바로 뒤에 오는 것만** 부록 참조로 본다.
            # 느슨하게 [A-Z]{1,2} 를 다 주우면 `A(X-Pose 빌드)` 의 X 와
            # `L(UI/UX)` 의 UI·UX 까지 부록으로 오해한다. 실제로 그랬다.
            cited = set(re.findall(r"\b([A-Z]{1,2})\s*\(", m.group(1)))
            footer_letters |= cited
            footer_letters |= set(re.findall(r"\b([A-Z]{1,2})\b", m.group(1)))
            # 없는 부록을 가리키는 푸터. 목록 형태라 위의 '부록 X' 검사에는
            # 안 걸린다 — 실제로 Ch28 이 사라진 부록 M 을 계속 가리키고 있었다.
            for k in sorted(cited - known):
                fail("참조", f"{cname} 푸터 → 없는 부록 {k}")
    for k in apps:
        if re.search(rf"부록 {k}\b", body) or k in footer_letters:
            continue
        warn("체계성", f"부록 {k} 가 본문에서 참조되지 않음")


# ── 5. 순서: 전방 참조(뒤 장을 미리 가리킴)가 과한가 ─────────────────
def check_forward(chs):
    fw = defaultdict(list)
    for n, _, t in chs:
        for m in re.finditer(r"Ch(\d+)", t):
            tgt = int(m.group(1))
            if tgt > n + 0.6:                    # 자기보다 뒤
                fw[f"Ch{n:g}"].append(tgt)
    for k, v in fw.items():
        far = [x for x in v if x - float(k[2:]) > 10]
        if len(set(v)) > 6:
            warn("순서", f"{k} 전방 참조 {len(set(v))}종 — 선행 지식 부담 점검")
        if far:
            warn("순서", f"{k} 10장 이상 앞선 참조: {sorted(set(far))}")
    return fw


# ── 5+. 절 참조: `Ch07 §9` 가 실제로 있는 절인가 ─────────────────────
def check_xrefs(chs, apps):
    """원고에는 `Ch07 §9`·`부록 G §4` 같은 참조가 백 개 넘게 있다.
    **절을 추가하거나 번호를 바꾸면 이것들이 조용히 깨진다.**

    Ch28+ 의 절을 재번호할 때 실제로 이 검사가 필요했다. 사람은 못 센다.
    """
    have_ch = defaultdict(set)          # "7" · "28+" → {1, 2, 3, …}
    for _n, fn, t in chs:
        m = re.match(r"ch(\d+)(plus)?_", fn)
        key = m.group(1).lstrip("0") + ("+" if m.group(2) else "")
        for h in re.finditer(r"^##\s+\d+\+?\.(\d+)", t, re.M):
            have_ch[key].add(int(h.group(1)))

    have_app = defaultdict(set)         # "G" → {1, 2, …}
    for k, (_fn, t) in apps.items():
        for h in re.finditer(r"^##\s+(\d+)\.", t, re.M):
            have_app[k].add(int(h.group(1)))

    body = [(f"Ch{n:g}", t) for n, _, t in chs] + \
           [(f"부록{k}", t) for k, (_, t) in apps.items()]
    for name, t in body:
        for m in re.finditer(r"Ch(\d+\+?)\s*§\s*(\d+)", t):
            tgt, sec = m.group(1).lstrip("0"), int(m.group(2))
            if tgt in have_ch and sec not in have_ch[tgt]:
                fail("참조", f"{name} → Ch{tgt} §{sec} 는 없는 절")
        for m in re.finditer(r"부록 ([A-N])\s*§\s*(\d+)", t):
            tgt, sec = m.group(1), int(m.group(2))
            if tgt in have_app and sec not in have_app[tgt]:
                fail("참조", f"{name} → 부록 {tgt} §{sec} 는 없는 절")


# ── 6. 품질: 분량 균형 ───────────────────────────────────────────────
def check_length(chs):
    """**평균이 아니라 중앙값과 비교한다.**

    평균은 긴 장 몇 개에 끌려 올라간다. Ch07 이 11,546자면 평균이 오르고,
    그러면 멀쩡한 장들이 줄줄이 '분량 부족' 으로 찍힌다. 그 경고를 따라
    글을 채우면 평균이 또 오르고, 다음 장이 부족해진다 — **끝나지 않는다.**

    실제로 이 원고에서 그 일이 일어났다. 장을 하나 채울 때마다 평균이
    올라가 다른 장이 새로 부족해졌다. 지표가 작업을 유도한 것이 아니라
    **작업이 지표를 밀어 올리고 있었다.**

    중앙값은 *전형적인 장* 을 가리키고 긴 장 몇 개에 흔들리지 않는다.
    (Ch09 §5 의 '우연 기준선' 과 같은 이야기다 — 숫자 하나는 비교 대상이
    있어야 뜻을 갖는다.)
    """
    lens = sorted((len(t), n) for n, _, t in chs)
    mid = lens[len(lens) // 2][0]
    for l, n in lens:
        if l < mid * 0.55:
            warn("품질", f"Ch{n:g} 분량 부족 {l:,}자 (중앙값 {mid:,})")
        if l > mid * 1.8:
            warn("품질", f"Ch{n:g} 분량 과다 {l:,}자 (중앙값 {mid:,})")
    return mid


# ── 7. 품질: 문체 가이드 준수 ────────────────────────────────────────
def check_style(chs):
    for n, fn, t in chs:
        label = f"Ch{n:g}"
        body = t.split("## ", 1)[-1]
        # 원칙 1 — 장은 장면으로 연다: 도입부에 숫자나 대사가 있는가
        head = t[:700]
        if not re.search(r"\d", head) and '"' not in head and "*" not in head:
            warn("품질", f"{label} 도입부에 구체적 숫자·장면 없음(문체가이드 원칙1)")
        # 원칙 6 — 표는 결정에만
        tables = len(re.findall(r"^\|", t, re.M))
        if tables > 40:
            warn("품질", f"{label} 표 행 {tables}개 — 산문으로 풀 여지(원칙6)")
        # 원칙 5 — 한 문단 = 한 생각
        longp = [p for p in body.split("\n\n") if len(p) > 520 and not p.startswith(("|", "```", ">", "-"))]
        if len(longp) >= 3:
            warn("품질", f"{label} 520자 넘는 문단 {len(longp)}개(원칙5)")


# ── 8. 내용: 핵심 수치가 문서 간에 어긋나지 않는가 ───────────────────
KEY_FACTS = {
    r"195\.8": "립싱크 실측(초)",
    r"32\.1": "리타게팅 실측(초)",
    r"21배|21×|× 21|영상 1초당": "실시간 대비 배수",
    r"85%": "병목 비중",
    r"29\.97": "fps 드리프트",
    r"15\.0GB": "핫스왑 전 VRAM",          # 3.0GB × 5 — Chatterbox 베이스 실측(ch03plus _work/vram_probe.json)
    r"3\.2GB": "핫스왑 후 VRAM",           # 생성 피크 reserved 실측
}


def check_facts(chs, apps):
    corpus = {**{f"Ch{n:g}": t for n, _, t in chs},
              **{f"부록{k}": t for k, (_, t) in apps.items()}}
    for pat, name in KEY_FACTS.items():
        hits = [d for d, t in corpus.items() if re.search(pat, t)]
        if not hits:
            fail("내용", f"핵심 수치 '{name}' 가 원고에서 사라짐")
    # 메타 문서의 장/부록 수 표기
    toc = read(os.path.join(DRAFT, "01_목차.md"))
    m = re.search(r"부록 (\d+)종", toc)
    if m and int(m.group(1)) != len(apps):
        fail("체계성", f"목차 표기 '부록 {m.group(1)}종' ≠ 실제 {len(apps)}종")
    for k in apps:
        if not re.search(rf"\*\*App {k}\*\*", toc):
            fail("체계성", f"목차에 부록 {k} 행 없음")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    chs, apps = chapters(), appendices()
    print(f"원고 QC — 본문 {len(chs)}장 · 부록 {len(apps)}종\n")

    check_structure(chs)
    check_section_order(chs)
    check_refs(chs, apps)
    check_orphans(chs, apps)
    check_xrefs(chs, apps)
    fw = check_forward(chs)
    avg = check_length(chs)
    check_style(chs)
    check_facts(chs, apps)

    if a.verbose:
        print(f"  평균 장 분량 {avg:,.0f}자")
        print(f"  전방 참조가 있는 장 {len(fw)}개\n")

    for cat in ("체계성", "순서", "참조", "내용", "품질"):
        f = [m for c, m in FAIL if c == cat]
        w = [m for c, m in WARN if c == cat]
        if f or w:
            print(f"■ {cat}")
            for m in f:
                print(f"   [FAIL] {m}")
            for m in w:
                print(f"   [warn] {m}")
            print()

    print(f"결과: FAIL {len(FAIL)} · warn {len(WARN)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

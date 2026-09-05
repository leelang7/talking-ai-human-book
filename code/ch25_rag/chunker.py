# -*- coding: utf-8 -*-
"""
Ch25 — 한국어 청킹 + 하이브리드 검색

이 장에서 **비용 대비 효과가 가장 큰 것 하나** 를 코드로 강제한다.

    각 조각 앞에 상위 제목을 붙인다.

"3.2 환불 규정" 아래의 조각에 그 제목이 없으면, 검색됐을 때 무엇에 대한
내용인지 알 수 없다. 붙이는 데 드는 비용은 문자열 연결 하나다.

나머지 규칙(Ch25 §3~4):
    · 의미 단위로 자른다 — 글자 수로 기계적으로 자르면 문장이 끊긴다
    · 한국어는 300~600자 — 같은 정보량에 필요한 글자가 영어보다 적다
    · 10~20% 겹침 — 경계에 걸친 정보를 놓치지 않는다
    · 표는 통째로 — 일반 텍스트로 자르면 행과 열이 뒤섞인다
    · 의미 + 키워드 하이브리드 — 고유명사·숫자는 의미 검색이 약하다

임베딩 없이 돈다. 실제로는 `_semantic` 을 임베딩 유사도로 바꾸면 된다.

실행:  python chunker.py        (샘플 문서 청킹 + 검색)
       python test_chunker_rag.py
"""
import math
import re
from collections import Counter

MIN_CHARS, MAX_CHARS, OVERLAP = 300, 600, 0.15
_HEAD = re.compile(r"^(#{1,6})\s+(.*)$")
_TABLE = re.compile(r"^\s*\|")


def chunk(md, max_chars=MAX_CHARS, min_chars=MIN_CHARS, overlap=OVERLAP):
    """마크다운 문서를 조각으로. **제목 경로를 각 조각에 박는다.**"""
    lines, path, blocks = md.split("\n"), [], []
    buf, in_table = [], False

    def flush(force=False):
        nonlocal buf
        if not buf:
            return
        text = "\n".join(buf).strip()
        if text and not re.fullmatch(r"[-*_]{3,}", text):     # 제목 바로 뒤 구분선만 남은 블록은 조각이 아니다
            blocks.append({"path": list(path), "text": text,
                           "kind": "table" if in_table else "prose"})
        buf = []

    for ln in lines:
        if (m := _HEAD.match(ln)):
            flush()
            lvl, title = len(m.group(1)), m.group(2).strip()
            path = path[:lvl - 1] + [title]      # 제목 경로 갱신
            in_table = False
            continue
        t = bool(_TABLE.match(ln))
        if t != in_table:                        # 표 시작/끝은 경계다
            flush()
            in_table = t
        buf.append(ln)
    flush()

    out = []
    for b in blocks:
        # ★ 표는 쪼개지 않는다. 행과 열이 뒤섞이면 검색되어도 못 읽는다.
        pieces = [b["text"]] if b["kind"] == "table" \
            else _split_prose(b["text"], max_chars, min_chars, overlap)
        for i, p in enumerate(pieces):
            head = " > ".join(b["path"])
            out.append({
                "id": f"c{len(out):03d}",
                "path": b["path"],
                "kind": b["kind"],
                "body": p,
                # 제목 맥락을 본문 앞에 실제로 붙인다 — 검색·답변 둘 다 좋아진다
                "text": (f"[{head}]\n{p}" if head else p),
                "part": (i + 1, len(pieces)),
            })
    return out


def _split_prose(text, max_chars, min_chars, overlap):
    """문단 → 문장 순으로 의미 경계를 지키며 자른다."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text)
             if p.strip() and not re.fullmatch(r"[-*_]{3,}", p.strip())]   # 구분선(---)은 조각이 아니다 — 3자짜리 조각이 생겼었다
    units = []
    for p in paras:
        if len(p) <= max_chars:
            units.append(p)
        else:                                    # 문단이 너무 길면 문장으로
            cur = ""
            for s in re.split(r"(?<=[.!?])\s+", p):
                if len(cur) + len(s) > max_chars and cur:
                    units.append(cur.strip()); cur = ""
                cur += s + " "
            if cur.strip():
                units.append(cur.strip())

    out, cur = [], ""
    for u in units:
        if len(cur) + len(u) + 1 > max_chars and len(cur) >= min_chars:
            out.append(cur.strip())
            tail = cur[-int(len(cur) * overlap):] if overlap else ""   # 겹침
            cur = tail + "\n"
        cur += u + "\n"
    if cur.strip():
        if out and len(cur.strip()) < min_chars // 2:   # 꼬리가 너무 짧으면 합친다
            out[-1] += "\n" + cur.strip()
        else:
            out.append(cur.strip())
    return out or [text]


# ── 검색 ────────────────────────────────────────────────────────────
def _ngrams(s, n=2):
    s = re.sub(r"\s+", "", s)
    return [s[i:i + n] for i in range(max(0, len(s) - n + 1))]


def _semantic(q, d):
    """자리표시자 — 문자 n-gram 코사인. 실제로는 임베딩 유사도로 교체한다."""
    a, b = Counter(_ngrams(q)), Counter(_ngrams(d))
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b.get(k, 0) for k in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


_TOK = re.compile(r"[A-Za-z0-9가-힣]+")


def _keyword(q, d):
    """고유명사·제품코드·숫자를 잡는다. 의미 검색이 약한 자리다(Ch25 §4)."""
    qt = set(_TOK.findall(q.lower()))
    dt = set(_TOK.findall(d.lower()))
    if not qt:
        return 0.0
    exact = len(qt & dt) / len(qt)
    # 숫자·영문 코드가 그대로 있으면 가산 — 이게 하이브리드의 핵심 이득
    codes = {t for t in qt if re.search(r"\d", t)}
    bonus = 0.5 * (len(codes & dt) / len(codes)) if codes else 0.0
    return min(1.0, exact + bonus)


def search(chunks, q, k=3, alpha=0.6):
    """하이브리드 — 의미 alpha, 키워드 (1-alpha)."""
    scored = []
    for c in chunks:
        s = alpha * _semantic(q, c["text"]) + (1 - alpha) * _keyword(q, c["text"])
        scored.append((round(s, 4), c))
    scored.sort(key=lambda x: -x[0])
    return scored[:k]


SAMPLE = """# 홈트 가이드

## 1. 시작하기

운동을 시작하기 전에 준비운동을 합니다. 준비운동은 부상을 막고 근육을 데웁니다.
가볍게 팔을 돌리고 목을 좌우로 천천히 움직입니다.

관절이 뻣뻣하면 더 길게 합니다. 특히 아침에는 몸이 굳어 있으므로 평소보다 두 배로 잡으세요.

## 2. 스쿼트

### 2.1 기본 자세

발을 어깨너비로 벌리고 발끝을 살짝 바깥으로 돌립니다. 무릎이 발끝을 넘지 않게 합니다.
허리는 곧게 펴고 시선은 정면을 봅니다. 내려갈 때 숨을 마시고 올라올 때 내쉽니다.

### 2.2 무릎이 아플 때

통증이 있으면 즉시 멈춥니다. 반만 앉는 하프 스쿼트로 바꾸고, 그래도 아프면 전문가를 찾으세요.

## 3. 회원 등급

| 등급 | 코드 | 월 이용료 | 혜택 |
|---|---|---|---|
| 기본 | B-100 | 9900원 | 영상 열람 |
| 프로 | P-200 | 19900원 | 개인 피드백 |
| 마스터 | M-300 | 39900원 | 1:1 코칭 |
"""


def _demo():
    cs = chunk(SAMPLE)
    print(f"  조각 {len(cs)}개\n")
    for c in cs:
        print(f"  {c['id']}  {c['kind']:<6}{len(c['body']):>4}자  "
              f"{' > '.join(c['path'])[:34]:<36}{c['part'][0]}/{c['part'][1]}")
    print("\n  ── 검색 ──")
    for q in ["무릎 아프면 어떻게 해요", "P-200 요금", "준비운동"]:
        print(f"\n  Q: {q}")
        for s, c in search(cs, q):
            print(f"    {s:<8}{' > '.join(c['path'])[:30]:<32}{c['body'][:28]}…")
    print()


if __name__ == "__main__":
    _demo()

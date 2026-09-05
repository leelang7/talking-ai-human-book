# -*- coding: utf-8 -*-
"""
Ch03 §7 — 숫자·단위·약어를 한글로 읽게 만드는 텍스트 정규화(TN)

TTS 엔진 대부분은 '3.5' 를 제멋대로 읽고 'AI' 를 '아이' 로 읽는다. 저자의 음성 서비스에서
Chatterbox 앞단에 붙여 운영하던 규칙을 그대로 옮겼다. 다섯 단계, 순서가 중요하다.

    ① 천 단위 쉼표 제거 · % → 퍼센트
    ② 단위 사전            5km → 5 킬로미터
    ③ 로마자 약어 → 낱자    AI → 에이아이, USB → 유에스비
    ④ 수분류사 분기         10개 → 열 개(고유어) · 15분 → 십오분(한자어)
    ⑤ 남은 숫자 → 한자어    1,234 → 천이백삼십사 · 3.5 → 삼점오 · 1만 → 만
    (⑥ 영단어 음차 — g2pkk + cmudict 가 있으면 cloud → 클라우드, 없으면 건너뛴다)

    python normalize_ko.py "AI 가 10개를 3.5배 빠르게, 1,000원에"
"""
import re
import sys

_AB = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
               "에이,비,씨,디,이,에프,지,에이치,아이,제이,케이,엘,엠,엔,오,피,큐,알,에스,티,유,브이,더블유,엑스,와이,지".split(",")))
_TND = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]
_TNU1 = ["", "십", "백", "천"]
_TNU2 = ["", "만", "억", "조", "경"]
_NT1 = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"]
_NT10 = ["", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"]
_UNITS = dict(zip("km,kg,cm,mm,ml,kb,mb,gb,tb".split(","),
                  "킬로미터,킬로그램,센티미터,밀리미터,밀리리터,킬로바이트,메가바이트,기가바이트,테라바이트".split(",")))
# 고유어 수사를 쓰는 수분류사 — 여기 없으면 한자어로 읽는다 (분·초·배·원·년·월·일 …)
_NATC = ("개(?!월)|명|마리|번(?!지)|살|잔|장|권|병|대|벌|켤레|그루|송이|군데|가지|봉지|통|판|줄|끼|곡|척|채|편|"
         "다발|시간|시(?![스속절점])")


def num_ko(s: str) -> str:
    """한자어 수사. 만 단위로 묶고, 소수는 '점', 0 은 '영', 1만 은 '만'."""
    if "." in s:
        a, b = s.split(".", 1)
        return num_ko(a) + "점" + "".join(_TND[int(c)] if c != "0" else "영" for c in b)
    n = int(s)
    if n == 0:
        return "영"
    grp = []
    while n > 0:
        grp.append(n % 10000)
        n //= 10000
    parts = []
    for gi in range(len(grp) - 1, -1, -1):
        g = grp[gi]
        if not g:
            continue
        seg = ""
        for pi in (3, 2, 1, 0):
            dg = (g // (10 ** pi)) % 10
            if dg:
                seg += ("" if (dg == 1 and pi > 0) else _TND[dg]) + _TNU1[pi]
        if gi == 1 and seg == "일":
            seg = ""                                   # 1만 → 만 (일만 아님). 1억·1조는 일억·일조
        parts.append(seg + (_TNU2[gi] if gi < len(_TNU2) else ""))
    return "".join(parts)


def nat_ko(n: int) -> str:
    """고유어 수사 관형형(1~99): 한/두/세 … 열/스무/서른."""
    if n == 20:
        return "스무"
    return _NT10[n // 10] + _NT1[n % 10]


def _eng():
    try:
        from nltk.corpus import cmudict
        from g2pkk.english import convert_eng
        cmu = cmudict.dict()
        return lambda t: convert_eng(t, cmu)
    except Exception:
        return None


_ENG = _eng()


def normalize(t: str, english: bool = True) -> str:
    t = re.sub(r"(?<=\d),(?=\d)", "", t)                                            # ① 1,000 → 1000
    t = re.sub(r"(\d)\s*(km|kg|cm|mm|ml|kb|mb|gb|tb)(?![A-Za-z])",
               lambda m: m.group(1) + " " + _UNITS[m.group(2).lower()], t, flags=re.I)   # ② 단위
    t = t.replace("%", "퍼센트")
    t = re.sub(r"[A-Z][A-Z]+", lambda m: "".join(_AB[c] for c in m.group(0)), t)   # ③ AI → 에이아이
    t = re.sub(r"(?<![A-Za-z])[A-Z](?![A-Za-z])", lambda m: _AB[m.group(0)], t)     #    단독 대문자

    def _nc(m):                                                                     # ④ 수분류사
        n = int(m.group(1))
        if 0 < n < 100:
            return nat_ko(n) + " " + m.group(2)
        return num_ko(m.group(1)) + m.group(2)
    t = re.sub(r"(?<![\d.])(\d+)\s*(" + _NATC + ")", _nc, t)
    t = re.sub(r"(?<![\d.])1(?=만)", "", t)                                          #    글자 "1만" 도 "만"
    t = re.sub(r"\d+(?:\.\d+)?", lambda m: num_ko(m.group(0)), t)                   # ⑤ 나머지 숫자
    if english and _ENG is not None:
        try:
            t = _ENG(t)                                                             # ⑥ cloud → 클라우드
        except Exception:
            pass
    return t


if __name__ == "__main__":
    s = " ".join(sys.argv[1:]) or "AI 가 10개를 3.5배 빠르게, 1,000원에 15분 만에. 20살, 5km, 50%, 1만 명"
    print(" ", s)
    print(" ", normalize(s, english=False))

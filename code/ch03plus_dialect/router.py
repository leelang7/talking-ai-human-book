# -*- coding: utf-8 -*-
"""
Ch03+ §3 — 어댑터 핫스왑의 라우팅

GPU 가 필요한 부분(베이스 모델 · LoRA 가중치)은 여기 없다. 여기 있는 것은
**요청의 `dialect` 값이 어느 어댑터로 가는가** 와 **어댑터를 어댑터인 채로
유지하는가** 다. 둘 다 GPU 없이 검사할 수 있고, 둘 다 실제로 틀렸던 자리다.

    ① 라우팅   모르는 코드 · 빈 값 · 대소문자 · 공백을 어떻게 다루나
    ② 핫스왑   다섯을 **동시에** 얹고 하나만 활성. 병합(merge)은 거절한다

②가 15.0GB 와 3.2GB 를 가른다(Ch03+ §3). 병합하면 어댑터가 가중치에 녹아
다시 떼어낼 수 없다 — 전환이 불가능해진다. 그래서 `merge()` 는 예외를 낸다.

    python router.py       요청 몇 개를 라우팅해 본다
"""
# 팔도 사투리 어댑터 — 코드는 Ch03+ §1 의 표 그대로 **다섯** 이다.
# (처음에 '통합(multi)' 을 여섯째로 넣었다가 뺐다. 책의 표에도, ATL 소스에도 없었다.
#  기억으로 지어낸 것이었다 — 자기비판 D14.)
ADAPTERS = {"gs": "경상", "jl": "전라", "gw": "강원", "cc": "충청", "jj": "제주"}
DEFAULT = None             # 값이 없거나 모르면 **어댑터 없음** = 베이스 모델의 표준어
ALIASES = {"경상": "gs", "전라": "jl", "강원": "gw", "충청": "cc", "제주": "jj",
           "gyeongsang": "gs", "jeolla": "jl", "gangwon": "gw",
           "chungcheong": "cc", "jeju": "jj"}


def select(dialect):
    """요청의 `dialect` 값 → 어댑터 코드, 또는 None(표준어).

    빈 값·None·모르는 값은 None 으로. 서버가 요청마다 예외를 내면 안 되고,
    없는 어댑터를 지어내서도 안 된다 — **베이스 모델이 곧 표준어** 다.
    한글 이름과 영문 이름도 받는다 — 프론트가 무엇을 보낼지 서버가 정하지 못한다.
    """
    if dialect is None:
        return DEFAULT
    key = str(dialect).strip().lower()
    if not key:
        return DEFAULT
    if key in ADAPTERS:
        return key
    return ALIASES.get(key, DEFAULT)


class MergedError(RuntimeError):
    """어댑터를 베이스에 녹였다. 이제 전환할 수 없다."""


class HotSwap:
    """베이스 하나에 어댑터 여럿을 얹고, 활성 하나만 바꾼다.

    실제 로더는 첫 어댑터로 모델을 감싸며 이름을 붙이고, 나머지는 그 위에
    이름만 추가로 얹는다(Ch03+ §3). 여기서는 그 상태 전이만 흉내낸다.
    """

    def __init__(self, base_gb: float = 3.0, adapter_mb: float = 22.5):
        self.base_gb, self.adapter_mb = base_gb, adapter_mb
        self.loaded: list[str] = []
        self.active: str | None = None
        self.merged = False

    def load(self, code: str):
        if code not in ADAPTERS:
            raise KeyError(f"모르는 어댑터: {code}")
        if self.merged:
            raise MergedError("병합된 모델에는 어댑터를 얹을 수 없다")
        if code not in self.loaded:
            self.loaded.append(code)
        if self.active is None:
            self.active = code
        return self

    def activate(self, code):
        """전환. **로드된 것 중에서만**, 그리고 병합 전에만.

        `None` 은 어댑터를 전부 끈다 — 베이스 모델의 표준어로 돌아간다.
        """
        if self.merged:
            raise MergedError("병합했으므로 전환할 수 없다 — 이것이 15.0GB 로 가는 길이다")
        if code is not None and code not in self.loaded:
            raise KeyError(f"로드되지 않은 어댑터: {code}")
        self.active = code
        return code

    def merge(self):
        """어댑터를 가중치에 녹인다. 추론이 조금 빨라지는 대신 **전환이 영원히 안 된다.**"""
        self.merged = True
        self.loaded = [self.active] if self.active else []
        return self

    def vram_gb(self) -> float:
        """이 인스턴스가 차지하는 VRAM 어림 — 베이스 하나 + 어댑터들."""
        return self.base_gb + len(self.loaded) * self.adapter_mb / 1024


def deploy_separately(codes, base_gb: float = 3.0) -> float:
    """어댑터마다 베이스를 따로 띄우면 — 15.0GB 로 가는 셈법. base_gb 3.0 은 Chatterbox 다국어 실측(_work/vram_probe.json)."""
    return base_gb * len(codes)


def _demo():
    print()
    for req in ("gs", "JJ", " 경상 ", "gyeongsang", "", None, "표준어", "xx"):
        code = select(req)
        print(f"  dialect={req!r:14} → {str(code):5}  ({ADAPTERS.get(code, '어댑터 없음 = 표준어')})")
    print()
    hs = HotSwap()
    for c in ("gs", "jl", "gw", "cc", "jj"):
        hs.load(c)
    print(f"  핫스왑  : 어댑터 {len(hs.loaded)}개 · VRAM {hs.vram_gb():.2f}GB · 활성 {hs.active}")
    print(f"  개별배포: VRAM {deploy_separately(hs.loaded):.1f}GB")
    hs.activate("jj")
    print(f"  전환 → {hs.active}  (로드 없이 즉시)")
    hs.merge()
    try:
        hs.activate("gs")
    except MergedError as e:
        print(f"  병합 후 전환: 거절 — {e}")
    print()


if __name__ == "__main__":
    _demo()

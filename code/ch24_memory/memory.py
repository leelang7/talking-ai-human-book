# -*- coding: utf-8 -*-
"""
Ch24 — 기억 3층 + 이벤트 원장

층마다 성격이 다르다. 섞으면 반드시 샌다.

    단기   최근 턴 그대로.   **턴이 아니라 토큰으로 자른다.**
    요약   버려지는 턴을 압축. 되돌릴 수 없다.
    장기   사실 단위 + 감쇠.  중복을 합치고 오래된 것을 내린다.
    원장   일어난 일을 구조화. **요약과 달리 다시 집계할 수 있다.**

그리고 이 책의 고유 항목 둘:
    · 캐릭터 자기 기억 — 자기모순이 인격을 가장 빠르게 무너뜨린다
    · 부재 기억       — 답 못 준 질문. 성공만 로깅하면 영원히 못 꺼낸다

실행:  python memory.py        (대화 시뮬레이션)
       python test_memory.py   (회귀 테스트)
"""
import re
import time


def toklen(s):
    """한국어는 글자당 토큰이 영어보다 많다. 여기서는 글자 수로 근사한다."""
    return len(s or "")


class ShortTerm:
    """단기 — **턴이 아니라 토큰 예산으로 자른다**(Ch24 §2).

    턴 수로 자르면 사용자가 긴 문장 하나를 넣었을 때 예산이 터진다.
    """

    def __init__(self, budget=1200, max_turn=None):
        self.budget, self.turns = budget, []
        # 한 턴 상한 — 실험(_work/experiment.json)에서 2,016자짜리 발화 하나가 예산 1,200 을
        # 2,049 로 뚫었다. 예산은 '최소 2턴' 을 보장하므로 턴 하나가 예산보다 크면 못 막는다.
        # 그래서 턴 자체를 먼저 자른다. 잘린 앞부분은 요약 층으로 넘긴다.
        self.max_turn = max_turn if max_turn is not None else budget // 2

    def add(self, role, text):
        overflow = []
        if toklen(text) > self.max_turn:
            overflow = [{"role": role, "text": text[:-self.max_turn], "ts": time.time()}]
            text = "…" + text[-self.max_turn:]
        self.turns.append({"role": role, "text": text, "ts": time.time()})
        return overflow + self._trim()

    def _trim(self):
        dropped = []
        while sum(toklen(t["text"]) for t in self.turns) > self.budget and len(self.turns) > 2:
            dropped.append(self.turns.pop(0))
        return dropped                      # 버려진 것은 요약 층으로 넘긴다

    def render(self, system=None):
        """시스템 프롬프트는 **항상 맨 앞**. 길어져도 페르소나가 유지된다."""
        head = [{"role": "system", "text": system}] if system else []
        return head + self.turns


class Summary:
    """요약 — 버려지는 턴에서 **다시 필요할 정보만** 남긴다.

    요약은 되돌릴 수 없다. 그래서 원장(Ledger)을 따로 둔다.
    """

    def __init__(self, budget=400):
        self.budget, self.text = budget, ""

    def absorb(self, turns, summarizer=None):
        if not turns:
            return self.text
        raw = " ".join(t["text"] for t in turns)
        piece = summarizer(raw) if summarizer else _naive_summary(raw)
        self.text = (self.text + " " + piece).strip()
        if toklen(self.text) > self.budget:          # 요약도 다시 요약된다
            self.text = self.text[-self.budget:]
        return self.text


_FACT = re.compile(r"(?:제 |내 |저는 |나는 )?(이름은|이름이)\s*([가-힣A-Za-z]{2,10})|"
                   r"(저는|나는|제가)\s*([가-힣]{2,12}(?:을|를|이|가)?\s*(?:좋아|싫어|해요|합니다|있어요))")


def _naive_summary(text):
    """LLM 없이 도는 자리표시자. 실제로는 요약 모델을 붙인다."""
    s = re.sub(r"\s+", " ", text)
    return s[:120] + ("…" if len(s) > 120 else "")


class LongTerm:
    """장기 — 사실 단위 저장 + 중복 병합 + 감쇠 + 사용자 삭제.

    **잊는 것도 설계다**(Ch24 §5). 모든 것을 기억하면 불쾌해진다.
    """

    def __init__(self, half_life_days=30.0):
        self.facts = {}                     # key -> {text, weight, ts, hits}
        self.half_life = half_life_days * 86400

    def remember(self, key, text, weight=1.0, now=None):
        now = now or time.time()
        f = self.facts.get(key)
        if f:                               # 중복은 갱신 — 같은 사실이 여러 번 쌓이면 검색이 오염된다
            f.update(text=text, ts=now, hits=f["hits"] + 1,
                     weight=min(3.0, f["weight"] + 0.5))
        else:
            self.facts[key] = {"text": text, "weight": weight, "ts": now, "hits": 1}
        return self.facts[key]

    def forget(self, key):
        """'그건 잊어줘' 가 동작해야 한다. 기능이 아니라 의무에 가깝다."""
        return self.facts.pop(key, None) is not None

    def score(self, key, now=None):
        f = self.facts[key]
        age = (now or time.time()) - f["ts"]
        return f["weight"] * (0.5 ** (age / self.half_life))

    def recall(self, k=3, now=None, threshold=0.05):
        ranked = sorted(self.facts, key=lambda x: -self.score(x, now))
        return [(x, self.facts[x]["text"], round(self.score(x, now), 3))
                for x in ranked if self.score(x, now) >= threshold][:k]


class SelfMemory:
    """캐릭터 자기 기억 — 사용자가 아니라 **캐릭터 자신**에 대한 것.

    어제 "커피 좋아해" 라던 캐릭터가 오늘 "커피 안 마셔" 라고 하면 인격이 무너진다.
    자주 놓치는 층이다(Ch24 §6).
    """

    def __init__(self):
        self.claims = {}

    def assert_(self, topic, value):
        """이미 말한 것과 다르면 **모순을 반환** 한다. 덮어쓰지 않는다."""
        prev = self.claims.get(topic)
        if prev is not None and prev != value:
            return {"conflict": True, "topic": topic, "before": prev, "now": value}
        self.claims[topic] = value
        return {"conflict": False, "topic": topic, "value": value}


class Ledger:
    """이벤트 원장 — 일어난 일을 구조화해 적는다.

    요약은 압축이라 되돌릴 수 없지만, 원장은 **언제든 다시 집계** 할 수 있다.
    그리고 **일어나지 않은 일**도 여기서 나온다.
    """

    def __init__(self):
        self.rows = []

    def log(self, kind, **meta):
        self.rows.append({"kind": kind, "ts": time.time(), **meta})

    def unanswered(self):
        """부재 기억 — 물었는데 답 못 준 것(Ch24 §6).

        성공만 로깅하는 시스템에서는 영원히 꺼낼 수 없는 정보다.
        """
        asked = {r["topic"] for r in self.rows if r["kind"] == "asked" and "topic" in r}
        answered = {r["topic"] for r in self.rows if r["kind"] == "answered" and "topic" in r}
        return sorted(asked - answered)

    def counts(self):
        c = {}
        for r in self.rows:
            c[r["kind"]] = c.get(r["kind"], 0) + 1
        return c


class Memory:
    """네 층을 묶은 파사드. 대화 한 턴이 들어오면 알아서 흐른다."""

    def __init__(self, system=None, budget=1200):
        self.system = system
        self.short, self.summary = ShortTerm(budget), Summary()
        self.long, self.me, self.ledger = LongTerm(), SelfMemory(), Ledger()

    def user(self, text, topic=None):
        dropped = self.short.add("user", text)
        if dropped:
            self.summary.absorb(dropped)     # 버려지는 것은 요약으로
        if topic:
            self.ledger.log("asked", topic=topic)
        return dropped

    def bot(self, text, topic=None, answered=True):
        dropped = self.short.add("bot", text)
        if dropped:
            self.summary.absorb(dropped)
        if topic and answered:
            self.ledger.log("answered", topic=topic)
        return dropped

    def context(self):
        """LLM 에 넘길 컨텍스트. 시스템 → 요약 → 장기 → 최근 턴 순."""
        parts = []
        if self.system:
            parts.append(("system", self.system))
        if self.summary.text:
            parts.append(("summary", self.summary.text))
        if (r := self.long.recall()):
            parts.append(("facts", " / ".join(t for _, t, _ in r)))
        parts += [(t["role"], t["text"]) for t in self.short.turns]
        return parts


def _demo():
    m = Memory(system="너는 홈트 코치다. 요체로 짧게 답한다.", budget=260)
    m.long.remember("name", "사용자 이름은 지훈")
    m.long.remember("knee", "사용자는 무릎이 안 좋음", weight=2.0)
    m.user("스쿼트 알려줘", topic="스쿼트")
    m.bot("무릎 조심해서 반만 앉아 봐요.", topic="스쿼트")
    m.user("어제 몇 세트 했지?", topic="지난기록")
    m.bot("그건 제가 알 수 없어요.", topic="지난기록", answered=False)
    for i in range(6):
        m.user(f"질문 {i} 입니다 " * 4)
        m.bot(f"대답 {i} 예요.")
    print("  ── 컨텍스트 ──")
    for role, txt in m.context():
        print(f"  {role:<8} {txt[:58]}")
    print(f"\n  단기 턴 {len(m.short.turns)}개 · 요약 {len(m.summary.text)}자")
    print(f"  장기 회상: {[(k, s) for k, _, s in m.long.recall()]}")
    print(f"  원장 {m.ledger.counts()}")
    print(f"  ▸ 답 못 준 것: {m.ledger.unanswered()}  ← 부재 기억")
    c = m.me.assert_("좋아하는것", "커피")
    c2 = m.me.assert_("좋아하는것", "녹차")
    print(f"  ▸ 자기모순 감지: {c2['conflict']} ({c2.get('before')} → {c2.get('now')})\n")


if __name__ == "__main__":
    _demo()

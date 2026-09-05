# -*- coding: utf-8 -*-
"""
Ch28 §5·§6 — 최소 잡 큐

**디렉터리 하나와 상태 파일** 이 전부다. 데이터베이스도 브로커도 없다.
렌더 잡은 초당 하나씩 들어오는 것이 아니라 몇 분에 하나 들어오므로,
그 규모에는 이것으로 충분하고 고장날 곳이 적다.

여기에 두 가지가 더 붙어 있다.

  ① **예상 시간**   Ch06 의 "영상 1초당 21.5초" 를 써서 대기 시간을 말해 준다
  ② **배치 규칙**   ★ 민감한 입력은 **남의 GPU 로 나가지 않는다** (§6)

②가 이 파일에서 제일 중요하다. Ch29 의 동의와 §6 의 책임은 문서로 두면
지켜지지 않는다. **잡을 집는 함수가 거절해야 지켜진다.**

    python jobqueue.py       큐 하나를 돌려 본다
"""
import json
import os
import uuid

# Ch06 실측 — 10.67초 영상에 230초. 부록 C 의 분해에서 나온 값이다.
SECONDS_PER_SECOND = 230.4 / 10.67

PENDING, RUNNING, DONE, FAILED = "pending", "running", "done", "failed"
LOCAL_ONLY, ANYWHERE = "local_only", "anywhere"

# 이 태그가 붙으면 무조건 내 GPU 에서만 돈다 (§6 · Ch29)
SENSITIVE_TAGS = ("deceased", "minor", "medical", "legal", "no_consent_scope")


class Queue:
    """상태 파일 하나로 도는 큐. `now` 를 주입받아 테스트가 시계에 안 흔들린다."""

    def __init__(self, root, clock=None):
        self.root = root
        self.path = os.path.join(root, "state.json")
        self.clock = clock or (lambda: 0.0)
        os.makedirs(os.path.join(root, "in"), exist_ok=True)
        os.makedirs(os.path.join(root, "out"), exist_ok=True)
        self.jobs = self._load()

    # ── 저장 ────────────────────────────────────────────────────────
    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        return []

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.jobs, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)          # 쓰다 죽어도 이전 상태가 남는다

    # ── 제출 ────────────────────────────────────────────────────────
    def submit(self, audio_seconds, tags=(), owner="anon"):
        """순서는 **시계가 아니라 순번(seq)** 으로 정한다.

        같은 초에 두 건이 들어오면 시각이 같아진다. 시각으로 정렬하면
        그 둘의 앞뒤가 없어져 대기 순번이 둘 다 1 로 나온다.
        실제로 시연에서 세 건이 전부 "순번 1" 로 찍혔다.
        """
        tags = tuple(tags)
        seq = max((j.get("seq", 0) for j in self.jobs), default=0) + 1
        job = {"id": uuid.uuid4().hex[:8], "seq": seq, "owner": owner,
               "audio_seconds": float(audio_seconds), "tags": list(tags),
               "placement": placement_for(tags),
               "state": PENDING, "worker": None,
               "at": self.clock(), "started": None, "finished": None,
               "attempts": 0, "error": None}
        self.jobs.append(job)
        self.save()
        return job["id"]

    def get(self, jid):
        return next((j for j in self.jobs if j["id"] == jid), None)

    # ── 집기 ────────────────────────────────────────────────────────
    def claim(self, worker, remote=False):
        """워커가 잡 하나를 집는다. **원격 워커에게는 민감 잡을 안 준다.**

        `remote=True` 는 남의 GPU 다. 이 한 줄이 §6 의 책임 조항이다.
        """
        for j in sorted(self.jobs, key=lambda x: x["seq"]):
            if j["state"] != PENDING:
                continue
            if remote and j["placement"] == LOCAL_ONLY:
                continue                     # ★ 민감 잡은 건너뛴다 — 밖으로 안 나간다
            j.update(state=RUNNING, worker=worker, started=self.clock(),
                     attempts=j["attempts"] + 1)
            self.save()
            return j
        return None

    def complete(self, jid, out=None):
        j = self.get(jid)
        j.update(state=DONE, finished=self.clock(), error=None)
        if out:
            j["out"] = out
        self.save()
        return j

    def fail(self, jid, error, retry=True, max_attempts=3):
        j = self.get(jid)
        if retry and j["attempts"] < max_attempts:
            j.update(state=PENDING, worker=None, started=None, error=error)
        else:
            j.update(state=FAILED, finished=self.clock(), error=error)
        self.save()
        return j

    # ── 회수 ────────────────────────────────────────────────────────
    def recover(self, stale_seconds):
        """워커가 죽으면 잡이 `running` 인 채로 영원히 남는다.

        **큐가 멈추는 가장 흔한 이유** 이고, 로그만 봐서는 안 보인다 —
        "처리 중" 이라고 표시되기 때문이다. 주기적으로 회수해야 한다.
        """
        now, back = self.clock(), []
        for j in self.jobs:
            if j["state"] == RUNNING and now - (j["started"] or 0) > stale_seconds:
                j.update(state=PENDING, worker=None, started=None,
                         error="워커 무응답 — 회수됨")
                back.append(j["id"])
        if back:
            self.save()
        return back

    # ── 사용자에게 보여줄 것 (§5) ────────────────────────────────────
    def position(self, jid):
        """대기 순번. 1 이면 다음 차례다. 처리 중이면 0."""
        j = self.get(jid)
        if j["state"] != PENDING:
            return 0 if j["state"] == RUNNING else -1
        ahead = [x for x in self.jobs if x["state"] == PENDING
                 and x["seq"] < j["seq"]]
        return len(ahead) + 1

    def eta(self, jid, workers=1):
        """예상 대기 시간(초). Ch06 의 어림값을 여기서 쓴다.

        *"약 4분 남았습니다"* 라고 말할 수 있으면 4분이 훨씬 짧게 느껴진다.
        """
        j = self.get(jid)
        if j["state"] in (DONE, FAILED):
            return 0.0
        ahead = [x for x in self.jobs
                 if x["state"] == PENDING and x["seq"] < j["seq"]]
        running = [x for x in self.jobs if x["state"] == RUNNING]
        work = sum(x["audio_seconds"] for x in ahead) * SECONDS_PER_SECOND
        for x in running:
            done_for = self.clock() - (x["started"] or self.clock())
            work += max(0.0, x["audio_seconds"] * SECONDS_PER_SECOND - done_for)
        if j["state"] == PENDING:
            work += j["audio_seconds"] * SECONDS_PER_SECOND
        else:
            done_for = self.clock() - (j["started"] or self.clock())
            work = max(0.0, j["audio_seconds"] * SECONDS_PER_SECOND - done_for)
            return work
        return work / max(1, workers)

    def counts(self):
        c = {PENDING: 0, RUNNING: 0, DONE: 0, FAILED: 0}
        for j in self.jobs:
            c[j["state"]] += 1
        return c


def placement_for(tags) -> str:
    """태그를 보고 어디서 돌릴지 정한다. **판단을 한 곳에 모은다.**"""
    return LOCAL_ONLY if any(t in SENSITIVE_TAGS for t in tags) else ANYWHERE


def human_eta(seconds: float) -> str:
    if seconds < 60:
        return f"약 {int(seconds)}초"
    if seconds < 3600:
        return f"약 {round(seconds / 60)}분"
    return f"약 {seconds / 3600:.1f}시간"


def _demo():
    import tempfile
    t = [0.0]
    with tempfile.TemporaryDirectory() as d:
        q = Queue(d, clock=lambda: t[0])
        a = q.submit(10.67, owner="수업")
        b = q.submit(30.0, tags=["deceased"], owner="추모")
        c = q.submit(5.0, owner="수업")

        print()
        print("  제출 3건 —")
        for jid, label in ((a, "10.67초 일반"), (b, "30초 · deceased"), (c, "5초 일반")):
            j = q.get(jid)
            print(f"    {jid}  {label:16} 배치={j['placement']:10}"
                  f" 순번 {q.position(jid)}  {human_eta(q.eta(jid))}")

        print()
        print("  원격 워커가 집으려 하면 —")
        j = q.claim("remote-1", remote=True)
        print(f"    집은 것: {j['id']} (tags={j['tags']})  ← deceased 를 건너뛰었다")
        print(f"    민감 잡 {b} 상태: {q.get(b)['state']}  — 여전히 대기")
        print()
        print("  내 GPU 가 집으면 —")
        j2 = q.claim("local-0", remote=False)
        print(f"    집은 것: {j2['id']} (tags={j2['tags']})")
        print()

        t[0] = 400.0
        back = q.recover(stale_seconds=300)
        print(f"  300초 무응답 회수: {back}  → {q.counts()}")
        print()


if __name__ == "__main__":
    _demo()

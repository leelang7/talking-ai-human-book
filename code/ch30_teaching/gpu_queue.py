# -*- coding: utf-8 -*-
"""
Ch30 §5 — GPU 를 공유 자원으로: 수업용 잡 큐

*"학생들이 자기가 만든 큐에 자기 잡을 넣는 구조는 그 자체로 좋은 교육이다."*
Ch28 의 잡 큐(`ch28_deploy/jobqueue.py`)를 그대로 쓰고, 수업에서만 필요한 둘을 얹는다.

    ① 공평한 순서    한 학생이 잡 열 개를 넣어도 다른 학생 차례를 막지 못한다
                    — 제출 순이 아니라 **학생별로 돌아가며** 집는다
    ② 수업 시간 창    예약된 시간 밖의 잡은 대기한다. GPU 한 장을 반 전체가 쓴다

둘 다 GPU 없이 검사된다. Ch28 §6 의 민감 잡 규칙(원격 금지)은 그대로 상속된다.

    python gpu_queue.py      학생 셋이 잡을 섞어 넣고 누가 먼저 도는지 본다
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "ch28_deploy"))
from jobqueue import PENDING, RUNNING, Queue  # noqa: E402


class ClassQueue(Queue):
    """Ch28 큐 + 공평한 순서 + 수업 시간 창."""

    def __init__(self, root, clock=None, window=None):
        super().__init__(root, clock)
        self.window = window          # (시작, 끝) 초 — None 이면 항상 열림

    def open_now(self) -> bool:
        if not self.window:
            return True
        s, e = self.window
        return s <= self.clock() <= e

    def claim(self, worker, remote=False):
        """**학생별로 돌아가며** 집는다.

        기준: 이미 돌았거나 도는 중인 잡이 가장 적은 학생의 가장 오래된 잡.
        같으면 제출 순. 열 개를 한꺼번에 넣은 학생은 열 번 중 한 번만 차례가 온다.
        """
        if not self.open_now():
            return None
        pending = [j for j in sorted(self.jobs, key=lambda x: x["seq"])
                   if j["state"] == PENDING and not (remote and j["placement"] == "local_only")]
        if not pending:
            return None
        served = {}
        for j in self.jobs:
            if j["state"] != PENDING:
                served[j["owner"]] = served.get(j["owner"], 0) + 1
        pick = min(pending, key=lambda j: (served.get(j["owner"], 0), j["seq"]))
        pick.update(state=RUNNING, worker=worker, started=self.clock(),
                    attempts=pick["attempts"] + 1)
        self.save()
        return pick

    def by_owner(self) -> dict:
        out = {}
        for j in self.jobs:
            out.setdefault(j["owner"], {"pending": 0, "running": 0, "done": 0, "failed": 0})
            out[j["owner"]][j["state"]] += 1
        return out


def _demo():
    import tempfile
    t = [0.0]
    with tempfile.TemporaryDirectory() as d:
        q = ClassQueue(d, clock=lambda: t[0], window=(0, 3600))
        for _ in range(4):
            q.submit(10.0, owner="지민")          # 한 명이 넷을 한꺼번에
        q.submit(10.0, owner="서준")
        q.submit(10.0, owner="하은")
        print()
        print("  제출: 지민×4 → 서준 → 하은   (제출 순이면 지민이 넷을 먼저 다 쓴다)")
        order = []
        for i in range(6):
            j = q.claim(f"gpu-0"); q.complete(j["id"]); order.append(j["owner"])
        print("  실제 순서:", " → ".join(order))
        t[0] = 5000.0
        q.submit(10.0, owner="지민")
        print(f"  수업 시간 밖(t={t[0]:.0f}): claim → {q.claim('gpu-0')}")
        print()


if __name__ == "__main__":
    _demo()

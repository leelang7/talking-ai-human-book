# -*- coding: utf-8 -*-
"""
Ch28 회귀 테스트

가장 중요한 것은 **민감한 잡이 남의 GPU 로 나가지 않는가** 다 (§6 · Ch29).
윤리 조항은 문서에 두면 지켜지지 않는다. 잡을 집는 함수가 거절해야 지켜지고,
거절하는지는 테스트가 지킨다.

    python test_deploy.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jobqueue import (ANYWHERE, DONE, FAILED, LOCAL_ONLY, PENDING,  # noqa: E402
                      RUNNING, SECONDS_PER_SECOND, SENSITIVE_TAGS, Queue,
                      human_eta, placement_for)
from preflight import (BAD_DOCKER, BAD_ENTRY, CRIT, GOOD_DOCKER,  # noqa: E402
                       GOOD_ENTRY, INFO, check_consent, check_container,
                       check_service, verdict)

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def main() -> int:
    print("\n  ── Ch28 배포 · 잡 큐 ──")
    t = [0.0]

    with tempfile.TemporaryDirectory() as d:
        q = Queue(d, clock=lambda: t[0])
        a = q.submit(10.67)
        b = q.submit(30.0, tags=["deceased"])
        c = q.submit(5.0)

        # ── ★ §6 민감 잡은 밖으로 안 나간다 ────────────────────────
        ok(q.get(b)["placement"] == LOCAL_ONLY,
           "★ deceased 태그가 붙으면 local_only 로 배치된다 (§6 · Ch29)")
        ok(all(placement_for([t2]) == LOCAL_ONLY for t2 in SENSITIVE_TAGS),
           "민감 태그 전부가 local_only 다", " · ".join(SENSITIVE_TAGS))
        ok(placement_for(["promo", "deceased"]) == LOCAL_ONLY,
           "태그가 섞여 있어도 하나라도 민감하면 local_only")
        ok(placement_for([]) == ANYWHERE, "일반 잡은 어디서든 돈다")

        got = q.claim("remote-1", remote=True)
        ok(got["id"] == a, "원격 워커는 순번 1 을 집는다", got["id"][:8])
        got2 = q.claim("remote-2", remote=True)
        ok(got2["id"] == c,
           "★ 원격 워커가 민감 잡을 건너뛰고 그 다음을 집는다",
           "순번 2 가 민감 잡인데 순번 3 을 집었다")
        ok(q.get(b)["state"] == PENDING, "민감 잡은 여전히 대기 중이다")
        ok(q.claim("remote-3", remote=True) is None,
           "★ 남은 것이 민감 잡뿐이면 원격 워커는 빈손으로 돌아간다")
        ok(q.claim("local-0", remote=False)["id"] == b,
           "내 GPU 는 그 잡을 집는다")

        # ── §5 순번과 예상 시간 ────────────────────────────────────
        q2 = Queue(os.path.join(d, "q2"), clock=lambda: t[0])
        j1, j2, j3 = q2.submit(10.0), q2.submit(10.0), q2.submit(10.0)
        ok([q2.position(x) for x in (j1, j2, j3)] == [1, 2, 3],
           "같은 시각에 들어와도 순번이 1·2·3 으로 갈린다",
           "정렬을 시계가 아니라 순번으로 한다")
        ok(q2.get(j1)["seq"] < q2.get(j2)["seq"] < q2.get(j3)["seq"],
           "순번은 단조 증가한다")

        e1, e3 = q2.eta(j1), q2.eta(j3)
        ok(abs(e1 - 10.0 * SECONDS_PER_SECOND) < 1,
           "첫 잡의 예상 시간이 Ch06 어림값과 맞는다",
           f"{e1:.0f}초 · 10초 영상 × {SECONDS_PER_SECOND:.1f}")
        ok(abs(e3 - 3 * e1) < 1, "뒤 잡은 앞의 것을 다 기다린다", f"{e3:.0f}초")
        ok(q2.eta(j1, workers=3) < e1, "워커가 늘면 예상 시간이 준다")

        ok(human_eta(230) == "약 4분", "230초를 사람 말로", human_eta(230))
        ok(human_eta(45).endswith("초") and human_eta(7200).endswith("시간"),
           "초·분·시간을 알아서 고른다", f"{human_eta(45)} / {human_eta(7200)}")

        # ── 회수 — 큐가 멈추는 가장 흔한 이유 ──────────────────────
        q3 = Queue(os.path.join(d, "q3"), clock=lambda: t[0])
        x = q3.submit(5.0)
        q3.claim("worker-dead")
        ok(q3.get(x)["state"] == RUNNING, "집으면 running 이 된다")
        ok(q3.recover(300) == [], "아직 멀쩡한 잡은 회수하지 않는다")
        t[0] = 999.0
        ok(q3.recover(300) == [x], "★ 무응답 워커의 잡을 회수한다",
           "회수가 없으면 running 인 채로 영원히 남는다")
        ok(q3.get(x)["state"] == PENDING and q3.get(x)["worker"] is None,
           "회수된 잡은 대기로 돌아가고 워커가 지워진다")
        ok(q3.claim("worker-2")["attempts"] == 2, "재시도 횟수가 쌓인다")

        # 무한 재시도를 막는다
        q4 = Queue(os.path.join(d, "q4"), clock=lambda: t[0])
        y = q4.submit(5.0)
        for _ in range(5):
            q4.claim("w")
            q4.fail(y, "GPU OOM")
        ok(q4.get(y)["state"] == FAILED,
           "★ 계속 실패하는 잡은 결국 포기한다 — 무한 재시도로 큐를 막지 않는다",
           f"attempts={q4.get(y)['attempts']}")
        ok(q4.claim("w") is None, "포기한 잡은 다시 집히지 않는다")

        # 상태 파일이 실제로 남는가
        q5 = Queue(os.path.join(d, "q5"), clock=lambda: t[0])
        z = q5.submit(1.0, tags=["minor"])
        q5.complete(z, out="a.mp4")
        again = Queue(os.path.join(d, "q5"), clock=lambda: t[0])
        ok(again.get(z)["state"] == DONE, "프로세스를 다시 띄워도 상태가 남아 있다")
        ok(again.get(z)["placement"] == LOCAL_ONLY, "배치 결정도 함께 남는다")
        ok(os.path.exists(os.path.join(d, "q5", "state.json")),
           "상태 파일 하나가 전부다 — DB 도 브로커도 없다")

    # ── §4 컨테이너 점검 ───────────────────────────────────────────
    good = check_container(GOOD_DOCKER, [GOOD_ENTRY])
    bad = check_container(BAD_DOCKER, [BAD_ENTRY])
    ok(verdict(good) == INFO, "잘 만든 컨테이너는 통과한다")
    ok(verdict(bad) == CRIT, "흔한 컨테이너는 치명으로 잡힌다")
    whys = " ".join(r[1] for r in bad)
    ok("latest" in whys, ":latest 베이스를 잡는다 — 내일 다른 이미지가 된다")
    ok("내려받" in whys, "★ 실행 중 모델을 내려받는 것을 잡는다 (§4)",
       "이게 있으면 워커가 인터넷 없이 못 돈다")

    svc_bad = check_service([BAD_ENTRY, "@app.get('/chat')"])
    ok(verdict(svc_bad) == CRIT, "키가 박힌 코드를 치명으로 잡는다")
    ok(any("헬스체크" in r[1] and r[0] == CRIT for r in svc_bad),
       "헬스체크 없는 서비스를 잡는다 — 없으면 죽은 줄도 모른다")
    ok(verdict(check_service(["@app.get('/health')", "timeout=5"])) == INFO,
       "헬스체크와 타임아웃이 있으면 통과")

    # ── 검사가 대상의 종류를 아는가 ────────────────────────────────
    #
    # 저자의 실제 잡 컨테이너를 점검했더니 "헬스체크 없음 — 치명" 이 나왔다.
    # 렌더 잡에는 엔드포인트가 없는 것이 정상이다. **오탐이었다.**
    from preflight import CACHE_CLEANED, OFFLINE_HINTS, looks_like_service  # noqa: E402
    job_src = "import subprocess\nsubprocess.run(['python', 'inference.py'])\n"
    svc_src = "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/chat')\n"
    ok(not looks_like_service([job_src]), "★ 배치 잡을 서비스로 오해하지 않는다")
    ok(looks_like_service([svc_src]), "서비스는 서비스로 알아본다")
    ok(verdict(check_service([job_src])) == INFO,
       "★ 배치 잡에는 헬스체크를 요구하지 않는다",
       "엔드포인트가 없는 것이 정상이다")
    ok(verdict(check_service([svc_src])) == CRIT,
       "서비스인데 헬스체크가 없으면 여전히 잡는다")

    # apt 정리를 알아보는가 — 캐시를 지우는 방법은 도구마다 다르다
    clean = ("FROM x:1\nCOPY a /a\nENV B=1\n"
             "RUN apt-get update && apt-get install -y ffmpeg && "
             "rm -rf /var/lib/apt/lists/*\n")
    dirty = "FROM x:1\nCOPY a /a\nENV B=1\nRUN apt-get install -y ffmpeg\n"
    ok(not any("설치 캐시" in r[1] for r in check_container(clean, [])),
       "★ `rm -rf /var/lib/apt/lists` 로 지운 것을 지적하지 않는다",
       "pip 플래그만 알면 apt 를 오해한다")
    ok(any("설치 캐시" in r[1] for r in check_container(dirty, [])),
       "안 지운 것은 여전히 짚는다")
    ok(len(CACHE_CLEANED) >= 3, "정리 방법을 여러 개 안다", f"{len(CACHE_CLEANED)}가지")

    # 오프라인 선언
    ok(any("오프라인" in r[1] and r[0] == INFO
           for r in check_container("FROM x:1\nENV HF_HUB_OFFLINE=1\nCOPY a /a\n", [])),
       "오프라인 선언을 알아본다", " · ".join(OFFLINE_HINTS[:2]))
    ok(any("오프라인" in r[1] and r[0] != INFO for r in check_container(dirty, [])),
       "선언이 없으면 참고로 남긴다")

    # ── §6 동의서 항목을 기술 점검표에 같이 둔다 ───────────────────
    ok(verdict(check_consent(["보관 기간"])) == CRIT,
       "★ 동의서에 '어디서 처리되는가' 가 없으면 배포를 막는다 (§6)")
    ok(verdict(check_consent(["어디서 처리되는가", "보관 기간", "철회 방법"])) == INFO,
       "세 항목이 다 있으면 통과")

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())

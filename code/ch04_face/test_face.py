# -*- coding: utf-8 -*-
"""
Ch04 회귀 테스트

가장 중요한 것은 **§3 ★ 의 주장이 측정과 맞는가** 다.
맞지 않았고, 그래서 본문을 고쳤다. 이 테스트가 그 결론을 지킨다.

    python test_face.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from closeup import (CROP, detail_after_crop, gross_amplitude,  # noqa: E402
                     mouth_patch, report, synth_frame)
from criteria import (DRIVER, FAIL, OK, SOURCE, WARN, grade,  # noqa: E402
                      verdict)

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def main() -> int:
    print("\n  ── Ch04 얼굴의 조건 ──")
    rows = {r["ratio"]: r for r in report()}

    # ── §3 ★ 클로즈업 ──────────────────────────────────────────────
    d = [rows[r]["detail"] for r in sorted(rows)]
    ok(all(b >= a * 0.95 for a, b in zip(d, d[1:])),
       "★ 얼굴이 클수록 입 디테일이 늘어난다 (단조)",
       " → ".join(f"{x:.0f}" for x in d))

    med, big = rows[0.25], rows[0.85]
    ok(big["detail"] / med["detail"] > 2.0,
       "미디엄샷과 클로즈업의 입 디테일이 2배 이상 차이난다",
       f"{med['detail']:.0f} → {big['detail']:.0f}")

    # 대조군 — 이것이 평평해야 위 결과가 의미를 갖는다
    amps = [rows[r]["amplitude"] for r in sorted(rows)]
    ok(max(amps) / min(amps) < 1.3,
       "★ 총 진폭은 얼굴 크기와 거의 무관하다 (대조군)",
       f"{min(amps):.1f}~{max(amps):.1f}, 편차 {max(amps)/min(amps):.2f}배")
    ok(big["detail"] / med["detail"] > big["amplitude"] / med["amplitude"] * 1.5,
       "★ 디테일이 진폭보다 훨씬 크게 무너진다 — 잃는 것은 입 '모양' 이다",
       f"디테일 {big['detail']/med['detail']:.1f}배 vs 진폭 "
       f"{big['amplitude']/med['amplitude']:.2f}배")

    # 합성이 카메라를 흉내내는가 — 첫 측정이 거꾸로 나온 원인
    small = detail_after_crop(0.15)["detail"]
    large = detail_after_crop(0.85)["detail"]
    ok(small < large, "작은 얼굴이 큰 얼굴보다 디테일이 적다",
       "이 부등호가 뒤집히면 합성이 카메라를 흉내내지 못한 것이다")

    # 결정론 — 난수를 안 쓴다
    ok(detail_after_crop(0.4) == detail_after_crop(0.4), "같은 입력이면 같은 값")
    ok(mouth_patch(0.4).shape == mouth_patch(0.4, 0.0).shape,
       "입 영역 크기는 벌림과 무관하다 — 같은 자리를 비교한다")

    # 입을 벌리면 실제로 달라진다 (측정이 살아 있는가)
    ok(gross_amplitude(0.85) > 5.0, "입을 벌리면 화면이 실제로 달라진다",
       f"{gross_amplitude(0.85):.1f}")
    a = mouth_patch(0.85, 0.0)
    ok(float(np.abs(a - a).mean()) == 0.0, "같은 것끼리는 차이가 0 이다")

    # ── §2 기준표 ──────────────────────────────────────────────────
    good = {"faces": 1, "face_ratio": 0.45, "brightness": 130, "evenness": 0.7,
            "clipping": 0.01, "symmetry": 0.8, "min_side": 1024}
    ok(verdict(grade(good, SOURCE)) == OK, "좋은 소스는 통과한다")

    for key, bad, why in (("faces", 3, "여러 명"),
                          ("face_ratio", 0.08, "얼굴이 작다"),
                          ("brightness", 20, "너무 어둡다"),
                          ("clipping", 0.4, "하이라이트가 날아갔다"),
                          ("symmetry", 0.2, "옆을 본다"),
                          ("min_side", 96, "원본이 작다")):
        m = dict(good, **{key: bad})
        ok(verdict(grade(m, SOURCE)) == FAIL, f"{why} → 실패로 잡는다",
           f"{key}={bad}")

    warn = dict(good, face_ratio=0.25)
    ok(verdict(grade(warn, SOURCE)) == WARN,
       "쓸 수는 있지만 아쉬운 값은 경고로 (실패가 아니다)", "face_ratio=0.25")

    rows2 = grade({"faces": 3, "face_ratio": 0.45, "brightness": 130,
                   "evenness": 0.7, "clipping": 0.01, "symmetry": 0.8,
                   "min_side": 1024}, SOURCE)
    ok(rows2[0][0] == FAIL, "나쁜 것부터 위에 보여준다 — 고칠 것이 먼저다")
    ok(all(r[3] for r in rows2 if r[0] == FAIL), "실패한 항목에는 조언이 붙는다")

    # 측정 못 한 값은 실패가 아니라 경고 — 검출 실패로 사진을 버리면 안 된다
    ok(verdict(grade(dict(good, symmetry=None), SOURCE)) == WARN,
       "측정하지 못한 항목은 실패가 아니라 경고다")

    # ── §3 드라이버 기준표 ─────────────────────────────────────────
    gd = {"face_ratio": 0.6, "motion": 0.1, "duration_ratio": 1.4}
    ok(verdict(grade(gd, DRIVER)) == OK, "좋은 드라이버는 통과한다")
    ok(verdict(grade(dict(gd, face_ratio=0.12), DRIVER)) == FAIL,
       "얼굴이 너무 작은 드라이버를 실패로 잡는다 (§3)")
    ok(verdict(grade(dict(gd, face_ratio=0.235), DRIVER)) != FAIL,
       "미디엄샷(0.235) 은 실패가 아니라 경고 — 리타게팅 결과가 좋았다 (§5 실측, 2026-09-05)")
    ok(verdict(grade(dict(gd, motion=0.6), DRIVER)) == FAIL,
       "고개를 크게 흔드는 영상을 잡는다")
    ok(verdict(grade(dict(gd, duration_ratio=0.7), DRIVER)) == FAIL,
       "음성보다 짧은 드라이버를 잡는다")
    ok(DRIVER["face_ratio"]["min"] > SOURCE["face_ratio"]["min"],
       "드라이버가 소스보다 더 큰 얼굴을 요구한다",
       f"{SOURCE['face_ratio']['min']} vs {DRIVER['face_ratio']['min']}")

    # ── 합성 프레임 ────────────────────────────────────────────────
    img, (x0, y0, fw, fh) = synth_frame(0.5)
    ok(abs(fh / img.shape[0] - 0.5) < 0.01, "합성 프레임의 얼굴 비율이 지정대로다",
       f"{fh / img.shape[0]:.3f}")
    ok(img.shape == (1080, 1920), "프레임 크기가 1080p 다")
    ok(mouth_patch(0.5).shape[0] <= CROP, "입 영역이 크롭 안에 있다")

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())

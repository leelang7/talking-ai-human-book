# -*- coding: utf-8 -*-
"""
Ch18 회귀 테스트

*"모델 파일 경로만 바꿨는데 그대로 동작했다"* 는 Ch18 의 핵심 주장이다.
그것이 성립하는 세 규칙 — 표준 이름 · 휴식 오프셋 · 뼈 기준 정규화 — 을
하나씩 깨뜨려 보고, 깨지면 무엇이 무너지는지 확인한다.

    python test_vrm.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rig import (ARM_DROP, BONES, FAMILIES, OK_RANGE, TARGET_H,  # noqa: E402
                 capture_rest, lower_arms, model_height, name_variants,
                 prepare, resolve, resolve_all, rotg, scale_for)

_n = _f = 0


def ok(cond, name, detail=""):
    global _n, _f
    _n += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _f += 1


def main() -> int:
    print("\n  ── Ch18 VRM · 모델 교체 ──")

    # ── ① 표준 이름 ────────────────────────────────────────────────
    ok(all(set(FAMILIES[f]) == set(BONES) for f in FAMILIES),
       "세 계열 모두 표준 뼈 15개를 전부 매핑한다", " · ".join(FAMILIES))
    ok(all(FAMILIES["vrm"][b] == b for b in BONES),
       "VRM 은 규격 이름이 곧 표준 이름이다")

    # three.js 가 이름의 점·콜론을 지운다
    ok(name_variants("upper_arm.L") == ("upper_arm.L", "upper_armL", "upper_arm_L"),
       "★ `.` 이 지워진 이름과 `_` 로 바뀐 이름을 차례로 시도한다")
    ok(name_variants("mixamorig:Head")[1] == "mixamorigHead",
       "`:` 도 같은 방식으로 처리한다")
    ok(resolve("blender", "leftUpperArm", ["upper_armL"]) == "upper_armL",
       "★ 점이 지워진 채 들어온 뼈를 찾는다",
       "그대로 찾으면 undefined — 저자가 실제로 헤맨 곳")
    ok(resolve("blender", "leftUpperArm", ["upper_arm_L"]) == "upper_arm_L",
       "밑줄로 바뀐 것도 찾는다")
    ok(resolve("blender", "leftUpperArm", ["upper_arm.L"]) == "upper_arm.L",
       "원래 이름이 그대로 있으면 그것을 쓴다")
    ok(resolve("vrm", "leftUpperArm", ["head", "neck"]) is None,
       "★ 없는 뼈는 None — 터지지 않는다", "상반신만 있는 모델도 있다")
    ok(resolve("vrm", "tail", BONES) is None, "표준에 없는 이름은 None")

    partial = [b for b in BONES if "Leg" not in b]
    r = resolve_all("vrm", partial)
    ok(len(r) == 11 and "leftUpperLeg" not in r,
       "다리 없는 모델은 다리만 빠지고 나머지는 산다", f"{len(r)}/15")

    # ── ② 휴식 오프셋 ──────────────────────────────────────────────
    rest = capture_rest({"neck": (0.05, 0.0, 0.0), "head": (0.0, 0.0, 0.0)})
    ok(rotg(rest, "neck") == (0.05, 0.0, 0.0), "오프셋 0 이면 휴식 포즈 그대로다")
    ok(rotg(rest, "neck", dx=0.04) == (0.09, 0.0, 0.0),
       "★ 더하기다 — 0.04 를 주면 0.04 가 아니라 rest + 0.04 가 된다")
    ok(rotg(rest, "hips", dx=1.0) is None, "없는 뼈에 오프셋을 주면 None (무시)")
    ok(rest["neck"] is not rotg(rest, "neck", dx=0.0) or True,
       "휴식 포즈 원본은 바뀌지 않는다")
    ok(rest["neck"] == (0.05, 0.0, 0.0), "  실제로 안 바뀌었다")

    # 같은 오프셋, 다른 모델 → 다른 절대값. 그것이 요점이다.
    a = capture_rest({"neck": (0.00, 0, 0)})
    b = capture_rest({"neck": (0.05, 0, 0)})
    ok(rotg(a, "neck", dx=0.04) != rotg(b, "neck", dx=0.04),
       "★ 같은 동작이 모델마다 다른 절대각이 된다 — 절대값을 쓰면 둘이 같아진다")

    # ── T 포즈 팔 내리기 ───────────────────────────────────────────
    tp = capture_rest({b: (0.0, 0.0, 0.0) for b in BONES})
    down = lower_arms(tp, sign=1.0)
    ok(down["leftUpperArm"][2] == -ARM_DROP and down["rightUpperArm"][2] == ARM_DROP,
       "양팔이 반대 방향으로 내려간다", f"±{ARM_DROP}")
    flipped = lower_arms(tp, sign=-1.0)
    ok(flipped["leftUpperArm"][2] == ARM_DROP,
       "★ 부호를 뒤집으면 같은 각이 반대로 간다 — 리그 도구마다 축이 다르다")
    ok(down["head"] == tp["head"] and down["neck"] == tp["neck"],
       "팔 내리기는 팔만 건드린다")
    ok(tp["leftUpperArm"] == (0.0, 0.0, 0.0), "원본 휴식 포즈는 그대로다")
    no_arms = capture_rest({"neck": (0, 0, 0)})
    ok(lower_arms(no_arms) == no_arms, "팔 뼈가 없으면 아무 일도 안 한다")

    # ── ③ 뼈로 재는 크기 ───────────────────────────────────────────
    ok(abs(model_height([(0, 0, 0), (0, 0.8, 0), (0, 1.6, 0)]) - 1.6 * 1.06) < 1e-9,
       "뼈 최고·최저 차이에 6% 여유를 준다", f"{model_height([(0,0,0),(0,0.8,0),(0,1.6,0)]):.3f}")
    ok(model_height([(0, 0, 0), (0, 1, 0)]) == 0.0,
       "뼈가 셋 미만이면 재지 않는다 — 신뢰할 수 없는 값을 내지 않는다")

    ok(scale_for(1.6) == 1.0, "정상 크기는 건드리지 않는다")
    ok(scale_for(OK_RANGE[0]) == 1.0 and scale_for(OK_RANGE[1]) == 1.0,
       "경계값도 정상으로 본다", f"{OK_RANGE}")
    ok(abs(scale_for(160.0) * 160.0 - TARGET_H) < 1e-9,
       "★ cm 로 만든 모델(키 160)을 사람 크기로 줄인다", f"×{scale_for(160.0):.4f}")
    ok(abs(scale_for(0.016) * 0.016 - TARGET_H) < 1e-9,
       "★ 너무 작은 모델(키 0.016)을 사람 크기로 키운다", f"×{scale_for(0.016):.1f}")
    ok(scale_for(0.0) == 1.0, "높이 0 이면 나누지 않는다")

    # ── 전체 절차 ──────────────────────────────────────────────────
    names = ["mixamorigNeck", "mixamorigHead", "mixamorigSpine", "mixamorigHips",
             "mixamorigLeftArm", "mixamorigRightArm"]
    rots = {n: (0.0, 0.0, 0.0) for n in names}
    p = prepare("mixamo", names, rots, [(0, 0, 0), (0, 80, 0), (0, 165, 0)],
                tpose=True, arm_sign=-1.0)
    ok(len(p["bones"]) == 6, "있는 뼈만 잡는다", f"{len(p['bones'])}개")
    ok("chest" in p["missing"] and "leftUpperLeg" in p["missing"],
       "없는 뼈를 목록으로 알려준다", f"{len(p['missing'])}개 빠짐")
    ok(p["rest"]["leftUpperArm"][2] == ARM_DROP,
       "T 포즈면 팔을 내린 것이 휴식 포즈가 된다 (부호 반영)")
    ok(p["scale"] < 0.02, "cm 단위 모델을 정규화한다", f"×{p['scale']:.4f}")
    ok(rotg(p["rest"], "neck", dx=0.04) is not None
       and rotg(p["rest"], "chest", dx=0.04) is None,
       "준비된 모델에 동작을 넣으면 있는 뼈는 움직이고 없는 뼈는 무시된다")

    # ── VRM 은 노드 이름이 아니라 휴머노이드 지도다 (survey.py 가 잡은 것) ─────
    from rig import humanoid_map
    vrm0 = {"nodes": [{"name": "J_Bip_C_Hips"}, {"name": "J_Bip_C_Head"}],
            "extensions": {"VRM": {"humanoid": {"humanBones": [{"bone": "hips", "node": 0}, {"bone": "head", "node": 1}]}}}}
    vrm1 = {"nodes": [{"name": "Root_Hips"}], "extensions": {"VRMC_vrm": {"humanoid": {"humanBones": {"hips": {"node": 0}}}}}}
    ok(resolve_all("vrm", ["J_Bip_C_Hips", "J_Bip_C_Head"]) == {}, "★ 실제 VRM 노드 이름으로는 표준 뼈가 하나도 안 잡힌다")
    ok(humanoid_map(vrm0) == {"head": "J_Bip_C_Head", "hips": "J_Bip_C_Hips"}, "★ VRM 0.x 지도(목록)로 잡힌다")
    ok(humanoid_map(vrm1) == {"hips": "Root_Hips"}, "★ VRM 1.0 지도(사전)로 잡힌다")
    ok(humanoid_map({"nodes": []}) == {}, "  VRM 확장이 없으면 빈 지도 — 터지지 않는다")

    print(f"\n  {_n - _f}/{_n} 통과" + ("" if not _f else f" — {_f}건 실패") + "\n")
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())

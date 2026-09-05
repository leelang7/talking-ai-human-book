# -*- coding: utf-8 -*-
"""
Ch18 — 모델을 바꿔도 코드가 그대로인 이유

브라우저에서 눈으로 봐야 하는 부분은 `viewer.html` 에 있다.
이 파일은 **모델 교체를 가능하게 하는 세 가지 규칙** 을 순수 함수로 떼어낸 것이다.
저자의 실제 뷰어(VRM · Blender glb · Mixamo glb 세 계열을 한 코드로 돌린다)에서
그대로 옮겼다.

    ① 뼈 이름은 표준 이름 하나로 부른다 — 계열마다 다른 이름은 표 한 장으로 흡수
    ② 회전은 절대값이 아니라 **휴식 포즈로부터의 오프셋** 이다 (Ch19 §2)
    ③ 모델 크기는 메시가 아니라 **뼈 위치** 로 재고, 단위가 이상하면 정규화한다

셋 중 하나라도 빠지면 "모델 파일 경로만 바꿨는데 그대로 동작한다" 가 깨진다.

    python rig.py      세 계열 모델에 같은 동작을 넣어 본다
"""
import re

# ── ① 표준 뼈 이름 (VRM 휴머노이드 규격) ──────────────────────────────
BONES = ("neck", "head", "spine", "chest", "hips",
         "leftShoulder", "rightShoulder",
         "leftUpperArm", "rightUpperArm", "leftLowerArm", "rightLowerArm",
         "leftUpperLeg", "rightUpperLeg", "leftLowerLeg", "rightLowerLeg")

# 계열마다 다른 이름을 표준 이름으로. **코드는 표준 이름만 안다.**
FAMILIES = {
    "vrm": {b: b for b in BONES},            # VRM 은 규격 자체가 표준 이름이다
    "blender": {
        "neck": "neck", "head": "head", "spine": "spine", "chest": "chest", "hips": "hips",
        "leftShoulder": "shoulder.L", "rightShoulder": "shoulder.R",
        "leftUpperArm": "upper_arm.L", "rightUpperArm": "upper_arm.R",
        "leftLowerArm": "lower_arm.L", "rightLowerArm": "lower_arm.R",
        "leftUpperLeg": "upper_leg.L", "rightUpperLeg": "upper_leg.R",
        "leftLowerLeg": "lower_leg.L", "rightLowerLeg": "lower_leg.R",
    },
    "mixamo": {
        "neck": "mixamorig:Neck", "head": "mixamorig:Head", "spine": "mixamorig:Spine",
        "chest": "mixamorig:Spine2", "hips": "mixamorig:Hips",
        "leftShoulder": "mixamorig:LeftShoulder", "rightShoulder": "mixamorig:RightShoulder",
        "leftUpperArm": "mixamorig:LeftArm", "rightUpperArm": "mixamorig:RightArm",
        "leftLowerArm": "mixamorig:LeftForeArm", "rightLowerArm": "mixamorig:RightForeArm",
        "leftUpperLeg": "mixamorig:LeftUpLeg", "rightUpperLeg": "mixamorig:RightUpLeg",
        "leftLowerLeg": "mixamorig:LeftLeg", "rightLowerLeg": "mixamorig:RightLeg",
    },
}


def name_variants(rig_name: str):
    """three.js 는 노드 이름에서 `.` 과 `:` 을 지운다. **그래서 그대로 찾으면 없다.**

    `upper_arm.L` 로 찾으면 못 찾고, `upper_armL` 이나 `upper_arm_L` 로 들어 있다.
    저자가 실제로 여기서 한참 헤맸다 — 뼈가 분명히 있는데 `getObjectByName` 이
    `undefined` 를 돌려줬다. 세 가지 표기를 차례로 시도한다.
    """
    return (rig_name,
            re.sub(r"[:.]", "", rig_name),
            re.sub(r"[:.]", "_", rig_name))


def resolve(family: str, std: str, node_names) -> str | None:
    """표준 이름 → 그 모델 안의 실제 노드 이름. 없으면 None (**터지지 않는다**).

    없는 뼈는 그냥 건너뛴다. 하반신이 없는 상반신 모델도 있고, 어깨 뼈가 없는
    모델도 있다. 하나 없다고 전체가 죽으면 교체가 안 된다.
    """
    rig = FAMILIES[family].get(std)
    if not rig:
        return None
    names = set(node_names)
    for v in name_variants(rig):
        if v in names:
            return v
    return None


def humanoid_map(gltf: dict) -> dict:
    """VRM 파일의 휴머노이드 뼈 지도 → {표준 이름: 노드 이름}.

    실제 VRM 파일 아홉을 열어 보니(survey.py) **노드 이름으로는 표준 뼈가 0/15** 였다 —
    노드는 "J_Bip_C_Hips" 같은 제작 도구의 이름이고, 표준 이름은 확장 블록의
    humanBones 지도에만 있다. 브라우저에서 "vrm 계열은 이름이 그대로" 로 보였던 것은
    three-vrm 이 이 지도를 읽어 정규화된 뼈를 내주기 때문이다. 지도가 진짜 규격이다.
    VRM 0.x 는 목록(bone·node), VRM 1.0 은 사전({이름: {node}}) — 모양이 다르다.
    """
    nodes = gltf.get("nodes", [])
    ext = gltf.get("extensions", {})
    out = {}
    if "VRMC_vrm" in ext:
        for std, v in ext["VRMC_vrm"]["humanoid"]["humanBones"].items():
            out[std] = nodes[v["node"]].get("name", str(v["node"]))
    elif "VRM" in ext:
        for b in ext["VRM"]["humanoid"]["humanBones"]:
            out[b["bone"]] = nodes[b["node"]].get("name", str(b["node"]))
    return {b: out[b] for b in BONES if b in out}


def resolve_all(family: str, node_names) -> dict:
    out = {}
    for b in BONES:
        n = resolve(family, b, node_names)
        if n:
            out[b] = n
    return out


# ── ② 휴식 포즈 오프셋 ──────────────────────────────────────────────
def capture_rest(rotations: dict) -> dict:
    """로드 직후의 회전값을 복사해 둔다. 이 값이 이후 모든 동작의 **원점** 이다."""
    return {b: tuple(r) for b, r in rotations.items()}


def rotg(rest: dict, bone: str, dx=0.0, dy=0.0, dz=0.0):
    """휴식 포즈에 **더하기만** 한다. 절대값을 쓰지 않는다 (Ch19 §2).

    모델마다 기본 자세가 다르다 — 어떤 모델은 팔이 더 벌어져 있고 어떤 모델은
    고개가 숙여져 있다. 절대값 `(0.04, 0, 0)` 을 쓰면 그 모델의 자세를 지운다.
    """
    r = rest.get(bone)
    if r is None:
        return None
    return (r[0] + dx, r[1] + dy, r[2] + dz)


ARM_DROP = 1.2          # T 포즈에서 팔을 내리는 각(라디안) — 저자 실측값
FOREARM_DROP = 0.15


def lower_arms(rest: dict, sign: float = 1.0) -> dict:
    """T 포즈로 로드된 모델의 팔을 내려 휴식 포즈를 다시 정한다.

    **`sign` 이 있는 이유** — 같은 각도인데 어떤 모델은 팔이 내려가고 어떤 모델은
    올라간다. 리그를 만든 도구에 따라 회전축 방향이 뒤집혀 있기 때문이다.
    모델마다 부호 하나를 정해 두면 된다. 그것 말고는 전부 같다.
    """
    L = ARM_DROP * sign
    new = dict(rest)
    for bone, dx, dz in (("leftUpperArm", 0.08, -L), ("rightUpperArm", 0.08, L),
                         ("leftLowerArm", 0.0, -FOREARM_DROP * sign),
                         ("rightLowerArm", 0.0, FOREARM_DROP * sign)):
        if bone in rest:
            r = rest[bone]
            new[bone] = (r[0] + dx, r[1], r[2] + dz)
    return new


# ── ③ 크기 정규화 — 뼈로 잰다 ──────────────────────────────────────
TARGET_H = 1.6          # 사람 키(m). 이 근처로 맞춘다
OK_RANGE = (0.5, 4.0)   # 이 밖이면 단위가 다른 것이다 (cm 로 만든 모델 = 160)


def model_height(bone_positions) -> float:
    """**메시가 아니라 뼈 위치로** 키를 잰다.

    스킨드 메시의 바운딩 박스는 애니메이션 상태·모디파이어에 따라 흔들린다.
    뼈의 월드 좌표는 실제 몸의 범위를 정확히 준다. 뼈는 표면보다 조금 안쪽이라
    6% 여유를 준다 — 저자 뷰어의 값 그대로다.
    """
    ys = [p[1] for p in bone_positions]
    if len(ys) < 3:
        return 0.0
    h = max(ys) - min(ys)
    return h * 1.06


def scale_for(height: float) -> float:
    """단위가 이상한 모델만 고친다. 정상 범위면 건드리지 않는다.

    cm 로 만든 모델은 키가 160 으로 들어오고, 어떤 것은 0.016 으로 들어온다.
    둘 다 화면에서 안 보인다 — 하나는 너무 커서, 하나는 너무 작아서.
    """
    if height <= 0:
        return 1.0
    if OK_RANGE[0] <= height <= OK_RANGE[1]:
        return 1.0
    return TARGET_H / height


# ── 모델 하나를 준비하는 절차 전체 ───────────────────────────────────
def prepare(family: str, node_names, rotations: dict, bone_positions,
            tpose: bool, arm_sign: float = 1.0) -> dict:
    """로드 직후 한 번. 이 함수가 하는 일이 '모델 교체' 의 전부다."""
    bones = resolve_all(family, node_names)
    rest = capture_rest({b: rotations[n] for b, n in bones.items() if n in rotations})
    if tpose:
        rest = lower_arms(rest, arm_sign)
    h = model_height(bone_positions)
    return {"bones": bones, "rest": rest, "height": h, "scale": scale_for(h),
            "missing": [b for b in BONES if b not in bones]}


def _demo():
    import math
    print()
    # 세 계열의 '파일 안 노드 이름' 을 흉내낸다. Blender 는 점이 지워진 채로 들어온다.
    models = {
        "vrm":     ([b for b in BONES], 1.62, False, 1.0),
        "blender": (["neck", "head", "spine", "chest", "hips", "shoulderL", "shoulderR",
                     "upper_armL", "upper_armR", "lower_armL", "lower_armR",
                     "upper_legL", "upper_legR", "lower_legL", "lower_legR"],
                    165.0, False, 1.0),                       # ← cm 단위
        "mixamo":  (["mixamorigNeck", "mixamorigHead", "mixamorigSpine", "mixamorigSpine2",
                     "mixamorigHips", "mixamorigLeftShoulder", "mixamorigRightShoulder",
                     "mixamorigLeftArm", "mixamorigRightArm", "mixamorigLeftForeArm",
                     "mixamorigRightForeArm", "mixamorigLeftUpLeg", "mixamorigRightUpLeg",
                     "mixamorigLeftLeg"],                     # ← 뼈 하나 없음
                    1.75, True, -1.0),                        # ← T 포즈 · 부호 반전
    }
    # 모델마다 기본 자세가 다르다 — 목이 곧은 것, 살짝 숙인 것, 젖힌 것
    NECK_REST = {"vrm": 0.0, "blender": 0.05, "mixamo": -0.03}
    for fam, (names, h, tpose, sign) in models.items():
        rots = {n: (0.0, 0.0, 0.0) for n in names}
        rots[names[0]] = (NECK_REST[fam], 0.0, 0.0)
        pos = [(0, 0, 0), (0, h * 0.5, 0), (0, h * 0.94, 0)]
        p = prepare(fam, names, rots, pos, tpose, sign)
        nod = rotg(p["rest"], "neck", dx=0.04)
        print(f"  {fam:8} 뼈 {len(p['bones']):>2}/15  키 {p['height']:>7.2f}  "
              f"배율 {p['scale']:.4f}  빠진 뼈 {p['missing'] or '없음'}")
        print(f"           고개 끄덕임(+0.04) → neck = {tuple(round(v, 3) for v in nod)}")
    print()
    print("  같은 `rotg('neck', dx=0.04)` 인데 결과가 모델마다 다르다 — 각자의 휴식 포즈")
    print("  위에 더했기 때문이다. 절대값 0.04 를 썼다면 셋 다 같은 자세로 굳었을 것이다.")
    print()


if __name__ == "__main__":
    _demo()

# -*- coding: utf-8 -*-
"""
Ch18 §7 — 실제 모델 파일에 세 규칙을 대 본다.

저자 폴더의 VRM·glb 파일을 열어(외부 라이브러리 없이 glTF JSON 청크만 읽는다)
  ① 노드 이름으로 세 계열 중 어느 표가 뼈를 몇 개 잡는지
  ② VRM 이면 휴머노이드 뼈 지도(humanBones)가 있는지 — 있으면 노드 이름이 규격과 달라도 된다
  ③ 메시 좌표 범위로 잰 키(m)와 scale_for() 가 내는 배율
을 적는다.

    python survey.py    → _work/survey.json
"""
import glob, json, os, struct
from rig import FAMILIES, BONES, resolve_all, scale_for, humanoid_map
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import where   # noqa: E402

ROOTS = (os.path.join(where("avatar"), "images"), os.path.join(where("avatar"), "rigged"))


def gltf_json(path):
    with open(path, "rb") as f:
        magic, ver, length = struct.unpack("<4sII", f.read(12))
        assert magic == b"glTF", magic
        clen, ctype = struct.unpack("<II", f.read(8))
        return json.loads(f.read(clen).decode("utf-8"))


def height_m(g):
    ys = []
    for a in g.get("accessors", []):
        if a.get("type") == "VEC3" and "min" in a and "max" in a and a.get("componentType") == 5126:
            ys.append((a["min"][1], a["max"][1]))
    if not ys:
        return None
    return round(max(y[1] for y in ys) - min(y[0] for y in ys), 3)


def humanoid_bones(g):
    ext = g.get("extensions", {})
    if "VRMC_vrm" in ext:                                   # VRM 1.0
        return "VRM1", sorted(ext["VRMC_vrm"]["humanoid"]["humanBones"].keys())
    if "VRM" in ext:                                        # VRM 0.x
        return "VRM0", sorted(b["bone"] for b in ext["VRM"]["humanoid"]["humanBones"])
    return None, []


def main():
    out = []
    print(f"  {'파일':22s} {'계열(잡힌 뼈)':30s} {'휴머노이드':10s} {'키':>6s}  배율")
    for root in ROOTS:
        for p in sorted(glob.glob(os.path.join(root, "*.vrm")) + glob.glob(os.path.join(root, "*.glb"))):
            g = gltf_json(p)
            names = [n.get("name", "") for n in g.get("nodes", [])]
            hits = {fam: len(resolve_all(fam, names)) for fam in FAMILIES}
            hits["vrm_humanoid"] = len(humanoid_map(g))
            best = max(hits, key=hits.get)
            kind, hb = humanoid_bones(g)
            h = height_m(g)
            rec = {"file": os.path.relpath(p, where("avatar")).replace("\\", "/"), "size_MB": round(os.path.getsize(p) / 2**20, 1),
                   "nodes": len(names), "hits": hits, "best_family": best, "vrm": kind,
                   "humanoid_bones": len(hb), "height_m": h, "scale": None if h is None else scale_for(h)}
            out.append(rec)
            print(f"  {rec['file']:22s} {best}({hits[best]}/{len(BONES)}) {str(hits):18s} {str(kind):5s}{rec['humanoid_bones']:>3}   {str(h):>6s}  {rec['scale']}")
    json.dump({"measured": "2026-09-03", "bones": len(BONES), "models": out}, open(os.path.join("_work", "survey.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  → _work/survey.json")


if __name__ == "__main__":
    main()

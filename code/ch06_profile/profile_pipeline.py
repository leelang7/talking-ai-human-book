# -*- coding: utf-8 -*-
"""
Ch06 — 파이프라인 계측기 (부록 C 재현)

이 책의 가장 무거운 주장을 독자가 **자기 장비에서** 확인하게 하는 도구다.

    영상 1초당 약 21초 · 병목의 85% 가 립싱크 한 단계

저자의 수치는 **단일 케이스**(RTX 4070 SUPER · 512×512 · 10.67초)에서 나왔다.
그 한 점으로 책 전체를 받치고 있으므로, 다른 조건의 측정이 모일수록 주장이 단단해진다.

실행:
    python profile_pipeline.py --demo                     # 도구 자체 점검(모델 불필요)
    python profile_pipeline.py --config stages.json       # 실제 파이프라인 계측

출력은 그대로 이슈에 붙일 수 있는 표 형식이다.
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
try:
    import media
except Exception:
    media = None


def env_info():
    """보고에 반드시 함께 적어야 하는 것들 (부록 C §7)."""
    info = {"os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(), "gpu": "없음/미확인",
            "vram_gb": None, "torch": None}
    try:
        import torch
        info["torch"] = torch.__version__
        if torch.cuda.is_available():
            p = torch.cuda.get_device_properties(0)
            info["gpu"] = p.name
            info["vram_gb"] = round(p.total_memory / 1024**3, 1)
    except Exception:
        pass
    return info


def run_stage(name, cmd, cwd=None):
    """한 단계를 실행하고 벽시계 시간을 잰다. 출력은 흘려보낸다(Ch28 §4)."""
    print(f"  ▶ {name} …", flush=True)
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str))
    dt = time.perf_counter() - t0
    print(f"    {name} {dt:.1f}초 (종료 {p.returncode})", flush=True)
    return {"name": name, "sec": round(dt, 2), "rc": p.returncode}


def report(stages, audio_sec, env, note=""):
    total = sum(s["sec"] for s in stages)
    print("\n" + "=" * 64)
    print("부록 C 형식 보고 — 그대로 복사해 이슈에 붙이세요")
    print("=" * 64 + "\n")
    print(f"환경 : {env['gpu']}"
          + (f" {env['vram_gb']}GB" if env['vram_gb'] else "")
          + f" · torch {env['torch']} · {env['os']} · Python {env['python']}")
    if note:
        print(f"조건 : {note}")
    print(f"입력 : 음성 {audio_sec:.2f}초\n")
    print(f"| {'단계':<22} | {'소요(초)':>9} | {'비중':>6} |")
    print(f"|{'-'*24}|{'-'*11}|{'-'*8}|")
    for s in stages:
        share = s["sec"] / total * 100 if total else 0
        print(f"| {s['name']:<22} | {s['sec']:>9.1f} | {share:>5.0f}% |")
    print(f"| {'**합계**':<22} | {total:>9.1f} | {'100%':>6} |")

    rt = total / audio_sec if audio_sec else 0
    top = max(stages, key=lambda s: s["sec"]) if stages else None
    print(f"\n**실시간 배수 : {rt:.1f}×**  (영상 1초당 {rt:.0f}초)")
    if top:
        share = top["sec"] / total * 100
        print(f"**병목 : {top['name']} — 전체의 {share:.0f}%**")
        rest = total - top["sec"]
        print("\n" + ("→ 병목이 한쪽에 쏠려 있습니다. 나머지를 전부 0으로 만들어도 "
                      f"{rest:.1f}초({100-share:.0f}%)밖에 못 줄입니다(Ch06 §2)."
                      if share > 60 else
                      "→ 병목이 분산돼 있습니다. 저자 환경(85% 쏠림)과 다른 양상입니다 — "
                      "보고해 주시면 부록 C 에 함께 싣습니다."))
    print()
    return {"env": env, "audio_sec": audio_sec, "stages": stages,
            "total_sec": round(total, 2), "rt_factor": round(rt, 2), "note": note}


def demo():
    """모델 없이 도구 자체를 점검한다. 가짜 부하로 85% 쏠림을 재현."""
    print("데모 — 저자 환경의 비율을 가짜 부하로 재현합니다\n")
    plan = [("TTS", 0.05), ("신경망 립싱크", 1.96), ("표정 리타게팅", 0.32), ("ffmpeg mux", 0.02)]
    stages = []
    for name, sec in plan:
        print(f"  ▶ {name} …", flush=True)
        t0 = time.perf_counter()
        time.sleep(sec)
        dt = time.perf_counter() - t0
        print(f"    {name} {dt:.2f}초", flush=True)
        stages.append({"name": name, "sec": round(dt, 2), "rc": 0})
    # 실제 230초를 2.3초로 축약했으므로 음성 길이도 같은 비율로
    return report(stages, 10.67 / 100, env_info(), note="데모(가짜 부하 · 1/100 축약)")


def main():
    ap = argparse.ArgumentParser(description="파이프라인 계측기 (Ch06)")
    ap.add_argument("--demo", action="store_true", help="모델 없이 도구 점검")
    ap.add_argument("--config", help='단계 정의 JSON: [{"name":..,"cmd":..,"cwd":..}, …]')
    ap.add_argument("--audio", help="입력 음성 파일(길이 자동 측정)")
    ap.add_argument("--audio-sec", type=float, help="음성 길이 직접 지정")
    ap.add_argument("--note", default="", help="해상도·배치 등 조건 메모")
    ap.add_argument("--out", default="profile.json")
    a = ap.parse_args()

    if a.demo or not a.config:
        if not a.demo:
            print("--config 가 없어 데모로 실행합니다.\n")
        res = demo()
    else:
        sec = a.audio_sec
        if sec is None and a.audio and media:
            sec = media.probe(a.audio)["duration"]
        if not sec:
            print("음성 길이를 알 수 없습니다. --audio 또는 --audio-sec 을 주세요.")
            return 1
        cfg = json.load(open(a.config, encoding="utf-8"))
        stages = [run_stage(s["name"], s["cmd"], s.get("cwd")) for s in cfg]
        bad = [s for s in stages if s["rc"] != 0]
        if bad:
            print(f"\n  ! 실패한 단계: {', '.join(s['name'] for s in bad)}")
            print("    시간은 기록했지만 결과는 신뢰할 수 없습니다.\n")
        res = report(stages, sec, env_info(), a.note)

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f"저장: {a.out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

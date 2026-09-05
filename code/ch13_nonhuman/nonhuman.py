# -*- coding: utf-8 -*-
"""
Ch13 — 사람이 아닌 얼굴: 사람 드라이버 경유 파이프라인

Ch13 §3 의 층 분리를 그대로 잇는다. 두 실행기는 Ch11·Ch12 의 것을 부른다.

    ① 립싱크    사람 드라이버 + 음성  → 말하는 사람      (ch11_musetalk.musetalk_run)
    ② 리타게팅  말하는 사람 + 동물 사진 → 말하는 동물     (ch12_liveportrait.lp_run, animal)
    ③ mux       결과 + 음성 → 최종                        (_lib/media.mux — Ch14 §4)
    ④ 채점      Ch09 의 세 지표                            (ch09_verify/metrics)

저자 환경에서 실제로 돈 결과(고양이 s39 · 상담사 드라이버 · 6.072초 음성):

    ① 176프레임 · 108초        ② 176프레임 · 512² · 28초 · **29fps**
    ③ 29→30000/1001 재해석 시 0.2초 부족 — ①이 6프레임 덜 냈기 때문 (Ch14 §2 의 실물)
    ④ 적중률 67% · 우연 대비 1.43배 · **조용한 구간 77%** → 실패 — 말이 끝나도 입이 안 닫힌다

④의 실패가 이 파일의 이유다. **출하 설정(배율 3.0 · lip)이 이 책의 자기 게이트에서
떨어진다.** 배율 스윕(`lp_run.py --sweep`)과 §4 의 재타이밍(`--retime`)이 그 다음이다.

    python nonhuman.py --plan
    python nonhuman.py --photo cat.jpg --audio v.wav [--driver d.mp4] [--multiplier 3.0]
    python nonhuman.py --retime                       §4 — 동물 자기 클립의 입 모양 + 사람 타이밍
"""
import argparse
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_lib"))
from paths import where   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for sub in ("_lib", "ch11_musetalk", "ch12_liveportrait", "ch09_verify"):
    sys.path.insert(0, os.path.join(ROOT, sub))

AVATAR = os.environ.get("AVATAR_DIR", where("avatar"))
# Ch13 §4 — 픽셀이 아니라 모션을, 음량이 아니라 발음 타이밍을, 외삽 없이. 저자의 실제 스크립트.
RETIME = {"모션 단조 DTW":        "retime_talking.py",
          "발음 타이밍(사람 드라이버)": "retime_talking_phoneme.py",
          "외삽 없는 두-프레임 보간":  "retime_talking_precise.py"}


def stage1(driver, audio, out, log):
    from musetalk_run import run
    return run(driver, audio, os.path.join(out, "mt"), log)


def stage2(photo, talking, out, multiplier, log):
    from lp_run import run
    return run(photo, talking, os.path.join(out, "lp"), True, multiplier, "lip", log)


def stage3(video, audio, out, log):
    from media import FPS, check_lengths, mux
    before = check_lengths(video, audio)
    final = mux(video, audio, os.path.join(out, "final.mp4"), fps=FPS)
    after = check_lengths(final, audio)
    log(f"[mux] 재해석 전 {before['video_fps']} diff={before['diff']}s "
        f"부족 {before['shortfall_s']}s → 후 {after['video_fps']} diff={after['diff']}s")
    if after["shortfall_s"] and abs(after["shortfall_s"]) > 0.1:
        log("[mux] ⚠ 프레임이 모자란다 — 컨테이너 fps 로는 못 고친다. 상류(①)가 덜 낸 것이다")
    return final, after


def stage4(final, audio, log):
    from metrics import evaluate, explain
    from verify_sync import mouth_activity, speech_spans
    spans = speech_spans(audio)
    acts, fps = mouth_activity(final)
    r = evaluate(acts, fps, spans, top=15, duration=len(acts) / fps)
    log(explain(r))
    return r


def pipeline(photo, audio, driver, out, multiplier=3.0, log=print):
    os.makedirs(out, exist_ok=True)
    r1 = stage1(driver, audio, out, log)
    if not r1["ok"]:
        return {"ok": False, "stage": "lipsync"}
    r2 = stage2(photo, r1["output"], out, multiplier, log)
    if not r2["ok"]:
        return {"ok": False, "stage": "retarget"}
    final, chk = stage3(r2["output"], audio, out, log)
    score = stage4(final, audio, log)
    return {"ok": score["pass"], "stage": "done", "final": final, "concat": r2.get("concat"),
            "lengths": chk, "score": score}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--photo"); ap.add_argument("--audio"); ap.add_argument("--driver")
    ap.add_argument("--multiplier", type=float, default=3.0)
    ap.add_argument("--out", default=os.path.join(HERE, "_work"))
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--retime", action="store_true")
    a = ap.parse_args()

    if a.retime:
        print("\n  Ch13 §4 — 동물 클립이 있을 때. 사진 한 장으로는 안 된다.")
        for k, f in RETIME.items():
            p = os.path.join(AVATAR, f)
            print(f"    {k:22} {f:32} {'있음' if os.path.exists(p) else '없음'}")
        print("  셋 중 마지막(외삽 없음)이 저자가 정착한 것이다 — 혀가 안 나온다.\n")
        return 0

    photo = a.photo or os.path.join(AVATAR, "LivePortrait/assets/examples/source/s39.jpg")
    audio = a.audio or os.path.join(AVATAR, "MuseTalk/data/audio/_script.wav")
    driver = a.driver or os.path.join(AVATAR, "MuseTalk/data/video/driver_therapist.mp4")
    if a.plan or not (a.photo and a.audio):
        print("\n  ① 립싱크    ", os.path.basename(driver), "+", os.path.basename(audio))
        print("  ② 리타게팅  ", os.path.basename(photo), "· animal · lip · 배율", a.multiplier)
        print("  ③ mux       -r 30000/1001 재해석 + 프레임 수 검산")
        print("  ④ 채점      적중률 · 우연 기준선 · 조용한 구간")
        print("\n  실측(저자 환경): ④ 에서 실패 — 조용한 구간 77%. 출하 설정도 게이트를 못 넘는다.\n")
        return 0
    r = pipeline(photo, audio, driver, a.out, a.multiplier)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

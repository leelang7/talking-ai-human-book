# -*- coding: utf-8 -*-
"""
전체 게이트 러너 — 한 명령으로 원고와 코드를 함께 검사한다.

지금까지 여섯 개의 명령을 손으로 돌리고 있었다. 그러면 결국 안 돌리게 된다.
Ch27 §5 가 "게이트는 종료 코드로 전달하라" 고 했으니 그 규칙을 여기에도 적용한다.

실행:  python scripts/gates.py           (전부)
       python scripts/gates.py --quick   (원고만 · 코드 테스트 생략)
"""
import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

MANUSCRIPT = [
    ("원고 QC", "scripts/qc.py", ROOT),
    ("교재 적합성", "scripts/book_review.py", ROOT),
    ("인사이트 감사", "scripts/insight_audit.py", ROOT),
    ("조판 배치", "scripts/build_html.py --check", ROOT),
    ("도판 검사", "scripts/check_figures.py", ROOT),
    ("조판 검수", "scripts/type_qa.py --max-stretch 3", ROOT),
    ("잉여 감사", "scripts/prune_audit.py", ROOT),
    ("강의 자산 대조", "scripts/lecture_audit.py", ROOT),
    ("코드 참조 대조", "scripts/code_refs.py", ROOT),
]
CODE = [
    ("문장 청킹", "test_chunker.py", "code/ch07_latency"),
    ("fps·mux", "test_mux.py", "code/ch14_mux"),
    ("지연 숨기기", "test_hide.py", "code/ch08_hide"),
    ("STT·끼어들기", "test_stt.py", "code/ch23_stt"),
    ("멀티 아바타", "test_multi.py", "code/ch26_multi"),
    ("얼굴의 조건", "test_face.py", "code/ch04_face"),
    ("배포·잡 큐", "test_deploy.py", "code/ch28_deploy"),
    ("사다리 결정", "test_ladder.py", "code/ch05_ladder"),
    ("싱크 검증 지표", "test_verify.py", "code/ch09_verify"),
    ("VRM 모델 교체", "test_vrm.py", "code/ch18_vrm"),
    ("파츠 파라미터", "test_params.py", "code/ch16_parts"),
    ("사투리 라우팅", "test_router.py", "code/ch03plus_dialect"),
    ("파이프라인 재개", "test_pipeline.py", "code/ch15_pipeline"),
    ("실시간 턴", "test_turn.py", "code/ch21_realtime"),
    ("생성 로그·철회", "test_responsibility.py", "code/ch29_responsibility"),
    ("수업 인프라", "test_teaching.py", "code/ch30_teaching"),
    ("운영자 콘솔", "test_admin.py", "code/ch28plus_admin"),
    ("텍스트 정규화", "test_normalize.py", "code/ch03_tts"),
    ("실시간 통역", "test_interpreter.py", "code/ch23plus_interpreter"),
    ("평가 채점기", "test_eval.py", "code/ch27_eval"),
    ("프로파일 보고", "test_profile.py", "code/ch06_profile"),
    ("음량 구동", "test_mouth.py", "code/ch17_volume"),
    ("생명감", "test_alive.py", "code/ch19_alive"),
    ("제스처·태그", "test_gesture.py", "code/ch20_gesture"),
    ("기억 3층", "test_memory.py", "code/ch24_memory"),
    ("도구 호출", "test_tools.py", "code/ch24_memory"),
    ("페르소나", "test_persona.py", "code/ch22_persona"),
    ("청킹·검색", "test_rag.py", "code/ch25_rag"),
]
SMOKE = [
    ("환경 점검", "doctor.py", "code/ch02_setup"),
    ("음량 실측", "measure.py", "code/ch17_volume"),
    ("기억 실험", "experiment.py", "code/ch24_memory"),
    ("도구 호출 시연", "tools.py", "code/ch24_memory"),
    ("모델 조사", "survey.py", "code/ch18_vrm"),
    ("발언권 분포", "turns.py", "code/ch26_multi"),
    ("생성 로그 규모", "measure.py --quick", "code/ch29_responsibility"),
    ("수업 큐 공평성", "fairness.py", "code/ch30_teaching"),
    ("출간본 조판", "../../scripts/build_book.py --html", "code/ch01_stack"),
    ("리그 3계열", "rig.py", "code/ch18_vrm"),
    ("파이프라인 계획", "pipeline.py", "code/ch15_pipeline"),
    ("Wav2Lip 점검", "wav2lip_run.py --plan", "code/ch10_wav2lip"),
    ("MuseTalk 계획", "musetalk_run.py --plan", "code/ch11_musetalk"),
    ("LivePortrait 계획", "lp_run.py --plan", "code/ch12_liveportrait"),
    ("비사람 파이프라인", "nonhuman.py --plan", "code/ch13_nonhuman"),
    ("생성 로그 시연", "genlog.py", "code/ch29_responsibility"),
    ("공평 GPU 큐", "gpu_queue.py", "code/ch30_teaching"),
    ("계측기", "profile_pipeline.py --demo", "code/ch06_profile"),
    ("파츠 분할", "split_parts.py --demo", "code/ch16_parts"),
    ("평가 하네스", "score.py --demo", "code/ch27_eval"),
    ("mux 명령 검사", "mux_lint.py --self", "code/ch14_mux"),
    ("아이들 루프", "idle_loop.py --plan", "code/ch08_hide"),
    ("더블버퍼 시뮬", "hide.py", "code/ch08_hide"),
    ("VAD 보정", "vad.py", "code/ch23_stt"),
    ("끼어들기 판정", "bargein.py", "code/ch23_stt"),
    ("누출 검사", "engine.py", "code/ch26_multi"),
    ("병렬 호출", "schedule.py", "code/ch26_multi"),
    ("클로즈업 측정", "closeup.py", "code/ch04_face"),
    ("잡 큐", "jobqueue.py", "code/ch28_deploy"),
    ("배포 점검", "preflight.py", "code/ch28_deploy"),
    ("사다리 시나리오", "ladder.py", "code/ch05_ladder"),
    ("2D 합성 성능", "render_2d.py", "code/ch05_ladder"),
    ("적중률 채점", "metrics.py", "code/ch09_verify"),
    ("경보 판정", "alerts.py", "code/ch28plus_admin"),
]


def run(name, script, cwd):
    t0 = time.perf_counter()
    p = subprocess.run([PY, *script.split()], cwd=os.path.join(ROOT, cwd),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=ENV)
    dt = time.perf_counter() - t0
    return p.returncode, dt, (p.stdout or "") + (p.stderr or "")


def count_pass(out):
    return out.count("[PASS]"), out.count("[FAIL]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="원고 검사만")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    # 컴패니언 저장소에는 원고(draft/)가 없다 — 그때는 원고 게이트를 통째로 건너뛰고
    # 코드 회귀 테스트만 돌린다. 독자가 받은 저장소에서도 `python scripts/gates.py` 한 줄이 돌아야 한다.
    has_draft = os.path.isdir(os.path.join(ROOT, "draft"))
    groups = [("원고", MANUSCRIPT)] if has_draft else []
    if not has_draft:
        print("\n  (원고 폴더가 없습니다 — 코드 회귀 테스트만 돌립니다)")
    if not a.quick:
        # 원고를 읽는 스모크(조판)는 컴패니언 저장소에서 돌 수 없다 — 빼고 돌린다
        smoke = SMOKE if has_draft else [s for s in SMOKE if "build_book" not in s[1]]
        groups += [("회귀 테스트", CODE), ("스모크", smoke)]
    if not groups:
        print("  돌릴 것이 없습니다 — --quick 은 원고가 있을 때만 의미가 있습니다\n")
        return 0

    bad, total_pass, total_fail = [], 0, 0
    print()
    for gname, items in groups:
        print(f"■ {gname}")
        for name, script, cwd in items:
            if not os.path.exists(os.path.join(ROOT, cwd)):
                print(f"   [skip] {name} — 폴더 없음")
                continue
            rc, dt, out = run(name, script, cwd)
            # ★ PASS/FAIL 집계는 회귀 테스트에서만 한다.
            #   원고 도구의 [FAIL] 은 '보고된 지적'이지 게이트 실패가 아니다.
            #   초판은 이걸 섞어 세서 '2건 실패'와 '전부 통과'가 동시에 나왔다.
            p = f = 0
            if gname == "회귀 테스트":
                p, f = count_pass(out)
                total_pass += p; total_fail += f
            findings = out.count("[FAIL]") if gname == "원고" else 0
            detail = (f"  ({p}건 통과)" if p and not f else
                      f"  ({f}건 실패)" if f else
                      f"  (지적 {findings}건)" if findings else "")
            print(f"   [{'OK ' if rc == 0 else 'FAIL'}] {name:<14}{dt:>6.1f}s{detail}")
            if rc != 0:
                bad.append(name)
                if a.verbose:
                    print("\n".join("        " + l for l in out.strip().split("\n")[-8:]))
        print()

    # 원고 핵심 수치를 한 줄로 (원고가 있을 때만)
    rc, _, out = run("_", "scripts/book_review.py", ROOT) if has_draft else (0, 0, "")
    for key in ("합계", "약속한 폴더"):
        for line in out.split("\n"):
            if key in line:
                print("  " + line.strip())
    print(f"\n  회귀 테스트 {total_pass}건 통과"
          + (f" · {total_fail}건 실패" if total_fail else ""))
    if bad:
        print(f"  ✗ 실패한 게이트: {', '.join(bad)}\n")
        return 1
    print("  ✓ 전부 통과\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

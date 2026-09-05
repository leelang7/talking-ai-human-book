# -*- coding: utf-8 -*-
"""
Ch15 §4 — 네 단계를 하나로 묶는 스크립트의 뼈대

GPU 가 필요한 부분(립싱크 · 리타게팅 실행)은 여기 없다. 여기 있는 것은
**단계를 어떤 순서로, 어떤 조건에서 돌리고, 언제 멈추고, 어디서 다시 시작하는가** 다.
그 판단은 GPU 없이 전부 검사할 수 있고, 그래서 여기 모아 두었다.

Ch15 §4 의 원칙 넷에 하나를 더한다.

    ① 환경을 절대 경로로 호출한다        — 단계 함수를 밖에서 주입한다
    ② 출력을 실시간으로 흘린다           — 단계마다 시각·소요를 찍는다
    ③ 단계마다 검증하고 즉시 멈춘다      — 게이트가 떨어지면 다음 단계로 안 간다
    ④ 한글 경로를 자동으로 회피한다      — 입력을 ASCII 이름으로 복사해 쓴다
    ⑤ **끝난 단계는 다시 하지 않는다**    — 입력이 안 바뀌었으면 건너뛰고,
                                          실패하면 그 단계부터 다시 시작한다

⑤가 없으면 mux 가 실패했을 때 195초짜리 립싱크(Ch06)를 처음부터 다시 돈다.
저자의 배포용 잡 스크립트가 실제로 그랬다.

    python pipeline.py --plan       무엇을 돌릴지만 본다
"""
import hashlib
import json
import os
import shutil
import sys
import time

# 단계 순서는 Ch15 §2 그대로. 각 단계는 (입력 이름들, 출력 이름) 이다.
STAGES = (
    ("tts",      ("script",),           "voice.wav"),
    ("lipsync",  ("voice.wav", "driver"), "driver_talking.mp4"),
    ("retarget", ("driver_talking.mp4", "photo"), "raw.mp4"),
    ("mux",      ("raw.mp4", "voice.wav"), "final.mp4"),
)
ORDER = tuple(s[0] for s in STAGES)


def _sha(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


class Pipeline:
    """네 단계를 돌린다. 단계 함수와 게이트 함수는 **밖에서 준다.**

    runners[name](inputs: dict[str, path], output: path) -> None
    gates[name](output: path) -> (ok: bool, msg: str)     # 없으면 파일 존재·크기만 본다
    """

    def __init__(self, workdir: str, runners: dict, gates: dict | None = None,
                 log=print, clock=time.time):
        self.work = workdir
        self.runners, self.gates = runners, gates or {}
        self.log, self.clock = log, clock
        os.makedirs(workdir, exist_ok=True)
        self.manifest_path = os.path.join(workdir, "manifest.json")
        self.manifest = self._load()

    # ── ④ 한글 경로 회피 ─────────────────────────────────────────────
    def stage_inputs(self, script: str, photo: str, driver: str) -> dict:
        """원본을 작업 폴더에 ASCII 이름으로 복사한다. 원본은 건드리지 않는다."""
        out = {}
        for key, src in (("script", script), ("photo", photo), ("driver", driver)):
            ext = os.path.splitext(src)[1].lower() or ".bin"
            dst = os.path.join(self.work, f"in_{key}{ext}")
            if not os.path.exists(dst) or _sha(dst) != _sha(src):
                shutil.copyfile(src, dst)
            out[key] = dst
        return out

    # ── ⑤ 매니페스트 — 무엇을 어떤 입력으로 만들었나 ─────────────────
    def _load(self):
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save(self):
        tmp = self.manifest_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.manifest, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.manifest_path)

    def _path(self, name: str, files: dict) -> str:
        return files[name] if name in files else os.path.join(self.work, name)

    def _fingerprint(self, inputs, files) -> str:
        return "+".join(f"{n}:{_sha(self._path(n, files))}" for n in inputs)

    def plan(self, files: dict) -> list:
        """돌릴 단계와 이유. **돌리지 않는다.**"""
        rows, dirty = [], False
        for name, inputs, output in STAGES:
            out_path = self._path(output, files)
            fp = self._fingerprint(inputs, files) if all(
                os.path.exists(self._path(n, files)) for n in inputs) else None
            done = self.manifest.get(name)
            if dirty:
                why = "앞 단계가 다시 돌아서"
            elif fp is None:
                why = "입력이 아직 없어서"
            elif not os.path.exists(out_path):
                why = "산출물이 없어서"
            elif done and done.get("inputs") == fp and done.get("ok"):
                rows.append((name, "건너뜀", "입력이 안 바뀌었다")); continue
            elif done and done.get("inputs") == fp and not done.get("ok"):
                why = "지난번에 여기서 실패해서"
            else:
                why = "입력이 바뀌어서"
            dirty = True
            rows.append((name, "실행", why))
        return rows

    # ── ②③ 실행 — 흘리고, 검증하고, 멈춘다 ──────────────────────────
    def run(self, files: dict, dry_run: bool = False) -> dict:
        report = {"ran": [], "skipped": [], "failed": None, "seconds": {}}
        for name, action, why in self.plan(files):
            if action == "건너뜀":
                report["skipped"].append(name)
                self.log(f"[{name:8}] 건너뜀 — {why}")
                continue
            if dry_run:
                report["ran"].append(name)
                self.log(f"[{name:8}] (dry-run) {why}")
                continue

            inputs = next(s[1] for s in STAGES if s[0] == name)
            output = next(s[2] for s in STAGES if s[0] == name)
            in_paths = {n: self._path(n, files) for n in inputs}
            out_path = self._path(output, files)
            fp = self._fingerprint(inputs, files)

            t0 = self.clock()
            self.log(f"[{name:8}] 시작 — {why}")
            try:
                self.runners[name](in_paths, out_path)
                ok, msg = self._gate(name, out_path)
            except Exception as e:                       # 단계 함수가 터져도 기록은 남긴다
                ok, msg = False, f"예외: {e}"
            dt = self.clock() - t0
            report["seconds"][name] = dt
            self.manifest[name] = {"inputs": fp, "ok": ok, "msg": msg, "at": self.clock()}
            self._save()

            if not ok:
                self.log(f"[{name:8}] 실패 {dt:.1f}s — {msg}  → 여기서 멈춘다")
                report["failed"] = name
                return report
            self.log(f"[{name:8}] 완료 {dt:.1f}s — {msg}")
            report["ran"].append(name)
        return report

    def _gate(self, name, out_path):
        """③ 없으면 존재·크기만. 있으면 그 단계의 게이트(Ch09 적중률 · Ch14 길이 대조)."""
        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            return False, "산출물이 없거나 비어 있다"
        g = self.gates.get(name)
        if g is None:
            return True, f"{os.path.getsize(out_path):,} bytes"
        return g(out_path)


def _demo():
    import tempfile
    print()
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src"); os.makedirs(src)
        for n, body in (("대본.txt", "안녕"), ("하늘이.jpg", "img"), ("driver.mp4", "vid")):
            with open(os.path.join(src, n), "w", encoding="utf-8") as f:
                f.write(body)

        def fake(inp, out):
            with open(out, "w") as f:
                f.write("x" * 10)
        runners = {n: fake for n in ORDER}
        p = Pipeline(os.path.join(d, "work"), runners, log=lambda s: print("  " + s))
        files = p.stage_inputs(os.path.join(src, "대본.txt"), os.path.join(src, "하늘이.jpg"),
                               os.path.join(src, "driver.mp4"))
        print("  ── 1회차 ──"); p.run(files)
        print("  ── 2회차 (아무것도 안 바뀜) ──"); p.run(files)
        with open(files["script"], "w", encoding="utf-8") as f:
            f.write("안녕 바뀜")
        print("  ── 3회차 (대본만 바뀜) ──"); p.run(files)
    print()


def main() -> int:
    """인자 없이 부르면 시연. `--plan` 은 계획만, `--only tts` 는 그 단계까지만.

    실제 실행기(립싱크·리타게팅)는 GPU 환경에서 주입한다. 여기서는 TTS 만
    로컬에서 돌릴 수 있으므로 `--only tts` 가 원격 제출 전의 첫 걸음이다(run_remote.py).
    """
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--script"); ap.add_argument("--photo"); ap.add_argument("--driver")
    ap.add_argument("--work", default="_work")
    ap.add_argument("--plan", action="store_true", help="계획만 출력")
    ap.add_argument("--only", choices=ORDER, help="이 단계까지만 (그 뒤는 계획에서 뺀다)")
    a = ap.parse_args()
    if not (a.script and a.photo and a.driver):
        _demo(); return 0

    def not_wired(name):
        def _run(inp, out):
            raise RuntimeError(f"{name} 실행기가 주입되지 않았다 — GPU 환경에서 넣는다")
        return _run
    runners = {n: not_wired(n) for n in ORDER}
    p = Pipeline(a.work, runners, log=lambda s: print("  " + s))
    files = p.stage_inputs(a.script, a.photo, a.driver)
    rows = p.plan(files)
    if a.only:
        rows = rows[:ORDER.index(a.only) + 1]
    for name, action, why in rows:
        print(f"  {name:8} {action:4}  {why}")
    if not a.plan and not a.only:
        p.run(files)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
Ch08 §5 실측 — 진짜 브라우저(헤드리스 크로미움)에서 빈 프레임을 센다.

player.html 의 더블 버퍼(canplay 뒤에 앞으로 올림)와, 같은 요소에 src 를 바로 갈아끼우는
단일 버퍼를 각각 3회 교체(idle→reply→idle…)하며, 매 애니메이션 프레임마다
**앞 요소가 그릴 프레임이 있는가**(readyState ≥ 2 · 재생 중)를 기록한다.

    python measure_browser.py    → _work/browser.json   (playwright + chromium 필요)
"""
import json, os, pathlib
from playwright.sync_api import sync_playwright
HERE = pathlib.Path(__file__).resolve().parent

SINGLE = """
<video id="v" muted playsinline autoplay style="width:320px;height:320px"></video>
<script>
const v = document.getElementById('v');
window.__front = () => v;
window.show = (src, o={}) => new Promise(r => { v.loop = !!o.loop; v.src = src; v.play().catch(()=>{}); r(v); });
</script>"""

PROBE = """
() => new Promise(done => {
  const stats = { frames: 0, blank: 0, swaps: 0 };
  let running = true;
  function tick() {
    if (!running) return;
    const f = (window.__front ? window.__front() : document.querySelector('video.front'));
    stats.frames++;
    if (!f || f.readyState < 2 || f.paused || f.videoWidth === 0) stats.blank++;
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
  (async () => {
    for (let i = 0; i < 3; i++) {
      await window.show('reply.mp4', { loop: false }); stats.swaps++;
      await new Promise(r => setTimeout(r, 900));
      await window.show('idle_loop.mp4', { loop: true }); stats.swaps++;
      await new Promise(r => setTimeout(r, 900));
    }
    running = false; done(stats);
  })();
})"""


def run(page_html, label):
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        pg = b.new_page(viewport={"width": 400, "height": 400})
        pg.goto(page_html.as_uri()); pg.wait_for_timeout(1200)          # 아이들이 먼저 돈다 (§2)
        s = pg.evaluate(PROBE)
        b.close()
    s["blank_ratio"] = round(s["blank"] / max(1, s["frames"]), 3)
    print(f"  {label:10s} 프레임 {s['frames']:4d} · 빈 프레임 {s['blank']:3d} ({s['blank_ratio']:.1%}) · 교체 {s['swaps']}회")
    return s


def main():
    single = HERE / "_work" / "single.html"
    single.write_text(SINGLE + "<script>show('idle_loop.mp4',{loop:true})</script>", encoding="utf-8")
    # 단일 버퍼 페이지는 _work 에 있으므로 미디어 경로를 맞춘다
    for m in ("idle_loop.mp4", "reply.mp4"):
        dst = HERE / "_work" / m
        if not dst.exists():
            dst.write_bytes((HERE / m).read_bytes())
    out = {"double_buffer": run(HERE / "player.html", "더블 버퍼"), "single_buffer": run(single, "단일 버퍼")}
    json.dump({"measured": "2026-09-03", "browser": "chromium (playwright, headless)", "cycles": 3, **out},
              open(HERE / "_work" / "browser.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  → _work/browser.json")


if __name__ == "__main__":
    main()

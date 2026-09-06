# -*- coding: utf-8 -*-
"""
도판 생성기 — 데이터에서 그림을 만든다

손으로 그린 그래프는 **숫자가 바뀌면 거짓말이 된다.** 부록 C 의 실측이 갱신되거나
`ch20_gesture` 의 엔벨로프 상수가 바뀌면, 그림도 따라 바뀌어야 한다.

그래서 수치가 들어가는 도판은 **코드가 그린다.** 데이터를 바꾸고 다시 돌리면 끝이다.

만드는 것:
    F3  230초의 분해        — 부록 C 실측
    F7  제스처 엔벨로프       — code/ch20_gesture 의 실제 함수
    F10 fps 드리프트         — code/ch14_mux 의 실제 fps_math
    F11 음량 처리 전후        — code/ch17_volume 의 실제 MouthDriver
    F12 미세 움직임 여섯 진동수 — code/ch19_alive 의 실제 상수

실행:  python scripts/gen_figures.py
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "draft", "figures")
sys.path.insert(0, os.path.join(ROOT, "code", "ch20_gesture"))
sys.path.insert(0, os.path.join(ROOT, "code", "ch19_alive"))
sys.path.insert(0, os.path.join(ROOT, "code", "ch17_volume"))

HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        'font-family="Noto Sans KR, sans-serif" role="img" aria-label="{alt}">\n'
        '<style>'
        '.lbl{{font-size:12px;fill:#16181d}} .sub{{font-size:10px;fill:#5b6472}}'
        '.num{{font-size:11px;fill:#16181d;font-weight:600}}'
        '.ttl{{font-size:13px;font-weight:700;fill:#16181d}}'
        '.ax{{stroke:#98a0ad;stroke-width:1}} .gd{{stroke:#c9cfd8;stroke-width:.7;stroke-dasharray:3 3}}'
        '.ln{{fill:none;stroke:#16181d;stroke-width:1.8}}'
        '.bx{{stroke:#16181d;stroke-width:1.1}}'
        '</style>\n'
        '<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)"><rect width="3" height="6" fill="#000" opacity=".18"/>'
        '</pattern></defs>\n')


def save(name, body, w, h, alt):
    os.makedirs(FIG, exist_ok=True)
    p = os.path.join(FIG, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(HEAD.format(w=w, h=h, alt=alt) + body + "\n</svg>\n")
    return p


# ── F3 : 230초의 분해 (부록 C 실측) ──────────────────────────────────
STAGES = [("신경망 립싱크", 195.8), ("표정 리타게팅", 32.1), ("ffmpeg mux", 1.5)]
TTS_NOTE = "TTS 는 수 초 — 기계가 아니라 제공자에 달려 있어 위 합계에 넣지 않았다."


def f3():
    W, H, x0, bw = 512, 248, 96, 320
    total = sum(s for _, s in STAGES)
    o = ['<text class="ttl" x="8" y="22">10.67초 영상 한 편 = 230초</text>',
         '<text class="sub" x="8" y="40">RTX 4070 SUPER 12GB · 512×512 · 30fps · 320프레임</text>']
    y = 62
    for name, sec in STAGES:
        w = max(2.0, bw * sec / total)
        share = sec / total * 100
        fill = "url(#hatch)" if share > 50 else "#fff"
        o.append('<text class="lbl" x="%d" y="%d" text-anchor="end">%s</text>'
                 % (x0 - 10, y + 20, name))
        o.append('<rect class="bx" x="%d" y="%d" width="%.1f" height="26" fill="%s"/>'
                 % (x0, y, w, fill))
        o.append('<text class="num" x="%.1f" y="%d">%.1f초 · %.0f%%</text>'
                 % (x0 + w + 8, y + 18, sec, share))
        y += 38
    o.append('<line class="ax" x1="%d" y1="%d" x2="%d" y2="%d"/>' % (x0, y - 6, x0 + bw, y - 6))
    top = max(STAGES, key=lambda s: s[1])
    rest = total - top[1]
    o.append('<text class="num" x="8" y="%d">병목의 %.0f%%가 한 단계에 있다</text>'
             % (y + 22, top[1] / total * 100))
    o.append('<text class="sub" x="8" y="%d">나머지를 전부 0으로 만들어도 %.0f초밖에 못 줄인다. '
             '실시간 대비 21배.</text>' % (y + 42, rest))
    o.append('<text class="sub" x="8" y="%d">%s</text>' % (y + 60, TTS_NOTE))
    return save("f03_breakdown.svg", "\n".join(o), W, H,
                "230초 중 195.8초가 립싱크 한 단계에 몰려 있다")


# ── F7 : 제스처 엔벨로프 (실제 함수에서) ─────────────────────────────
def f7():
    from gesture import DUR, envelope, pose
    W, H, x0, y0, pw, ph = 512, 258, 48, 42, 420, 148
    name = "wave"
    dur = DUR[name]
    o = ['<text class="ttl" x="8" y="22">엔벨로프 한 줄이 동작 13종의 시작·끝을 처리한다</text>']
    # 축
    o.append('<line class="ax" x1="%d" y1="%d" x2="%d" y2="%d"/>' % (x0, y0 + ph, x0 + pw, y0 + ph))
    o.append('<line class="ax" x1="%d" y1="%d" x2="%d" y2="%d"/>' % (x0, y0, x0, y0 + ph))
    for frac, lab in ((0, "0"), (0.5, "%.1fs" % (dur / 2)), (1, "%.1fs" % dur)):
        x = x0 + pw * frac
        o.append('<line class="gd" x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>' % (x, y0, x, y0 + ph))
        o.append('<text class="sub" x="%.1f" y="%d" text-anchor="middle">%s</text>'
                 % (x, y0 + ph + 16, lab))

    N = 240
    env_pts, raw_pts = [], []
    for i in range(N + 1):
        t = dur * i / N
        env = envelope(t, dur)
        p = pose(name, t)
        raw = abs(p.get("ruz", 0)) / 0.95 if p else 0.0     # 엔벨로프 적용된 값
        env_pts.append((x0 + pw * i / N, y0 + ph - ph * env))
        raw_pts.append((x0 + pw * i / N, y0 + ph - ph * raw))
    o.append('<polyline class="ln" style="stroke-dasharray:5 4;stroke-width:1.2" points="%s"/>'
             % " ".join("%.1f,%.1f" % p for p in env_pts))
    o.append('<polyline class="ln" points="%s"/>'
             % " ".join("%.1f,%.1f" % p for p in raw_pts))

    o.append('<text class="sub" x="%d" y="%d">엔벨로프 (점선)</text>' % (x0 + 8, y0 + 14))
    o.append('<text class="sub" x="%d" y="%d">적용 후 팔 각도 (실선)</text>' % (x0 + 8, y0 + 30))
    o.append('<text class="num" x="8" y="%d">env = min(1, min(t, dur − t) / 0.3)</text>' % (H - 34))
    o.append('<text class="sub" x="8" y="%d">양 끝 0.3초에서 0 으로 접힌다 — '
             '동작마다 페이드를 따로 짤 필요가 없다.</text>' % (H - 14))
    return save("f07_envelope.svg", "\n".join(o), W, H,
                "엔벨로프가 동작의 시작과 끝 0.3초를 0으로 접는다")


# ── F12 : 미세 움직임 여섯 주기 (실제 상수에서) ──────────────────────
def f12():
    from alive import AMPS, PERIODS
    W, H, x0, y0, pw, ph = 512, 266, 40, 44, 452, 156
    secs = 30
    o = ['<text class="ttl" x="8" y="22">진동수가 서로 어긋나 있어 겹친 파형이 오래 반복되지 않는다</text>']
    o.append('<line class="ax" x1="%d" y1="%.1f" x2="%d" y2="%.1f"/>'
             % (x0, y0 + ph / 2, x0 + pw, y0 + ph / 2))
    for s in (0, 10, 20, 30):
        x = x0 + pw * s / secs
        o.append('<line class="gd" x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>' % (x, y0, x, y0 + ph))
        o.append('<text class="sub" x="%.1f" y="%d" text-anchor="middle">%d초</text>'
                 % (x, y0 + ph + 16, s))

    N = 600
    amax = sum(AMPS.values())
    pts = []
    for i in range(N + 1):
        t = secs * i / N
        v = sum(math.sin(t * PERIODS[k]) * AMPS[k] for k in PERIODS)
        pts.append((x0 + pw * i / N, y0 + ph / 2 - (v / amax) * (ph / 2 - 6)))
    o.append('<polyline class="ln" points="%s"/>' % " ".join("%.1f,%.1f" % p for p in pts))

    o.append('<text class="sub" x="8" y="%d">진동수(rad/s) %s — 공통 주기 약 126초</text>'
             % (H - 36, " · ".join("%.2f" % v for v in sorted(PERIODS.values()))))
    o.append('<text class="num" x="8" y="%d">호흡 진폭 0.012 라디안 — 약 0.7도. '
             '끄면 즉시 알아챈다.</text>' % (H - 14))
    return save("f12_micro.svg", "\n".join(o), W, H,
                "서로 어긋난 여섯 진동수를 겹치면 파형이 오래 반복되지 않는다")


# ── F10 : fps 드리프트 (code/_lib/media.py 의 실제 상수로) ────────────
def f10():
    from fractions import Fraction

    # 도판이 자기 계산을 따로 갖지 않는다 — 그 장의 코드를 그대로 부른다.
    sys.path.insert(0, os.path.join(ROOT, "code", "ch14_mux"))
    from fps_math import NTSC as FPS, drift_seconds, noticeable_after

    W, H = 512, 252
    x0, y0, pw, ph = 46, 36, 454, 150
    XMAX, YMAX = 120.0, 0.5                     # 영상 길이(초) · 누적 어긋남(초)
    THRESH = 0.1                                # 사람이 인식하는 입-소리 차이

    cases = [("29", Fraction(29), "stroke-width:1.8"),
             ("30", Fraction(30), "stroke-width:1.4;stroke-dasharray:5 4;stroke:#7b8494")]

    def px(t):
        return x0 + pw * t / XMAX

    def py(d):
        return y0 + ph - ph * min(d, YMAX) / YMAX

    o = ['<text class="ttl" x="4" y="17">틀린 fps 로 뽑으면 어긋남이 시간에 비례해 쌓인다</text>']
    o.append('<line class="ax" x1="%d" y1="%d" x2="%d" y2="%d"/>' % (x0, y0 + ph, x0 + pw, y0 + ph))
    o.append('<line class="ax" x1="%d" y1="%d" x2="%d" y2="%d"/>' % (x0, y0, x0, y0 + ph))
    for d in (0.0, 0.1, 0.3, 0.5):
        o.append('<text class="sub" x="%d" y="%.1f" text-anchor="end">%.1f</text>'
                 % (x0 - 5, py(d) + 4, d))
    for t in (0, 30, 60, 90, 120):
        o.append('<line class="gd" x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>' % (px(t), y0, px(t), y0 + ph))
        o.append('<text class="sub" x="%.1f" y="%d" text-anchor="middle">%d</text>'
                 % (px(t), y0 + ph + 16, t))
    o.append('<text class="sub" x="4" y="%d">어긋남(초)</text>' % (y0 - 6))
    o.append('<text class="sub" x="%d" y="%d" text-anchor="end">영상 길이(초)</text>'
             % (x0 + pw, y0 + ph + 16))

    o.append('<line class="gd" x1="%d" y1="%.1f" x2="%d" y2="%.1f" '
             'style="stroke:#16181d;stroke-dasharray:2 3"/>' % (x0, py(THRESH), x0 + pw, py(THRESH)))
    o.append('<text class="sub" x="%d" y="%.1f">사람이 알아채는 100ms</text>' % (x0 + 6, py(THRESH) - 6))

    notes = []
    for name, made, style in cases:
        cross = noticeable_after(made, FPS, THRESH)      # ch14_mux/fps_math.py
        rate = drift_seconds(made, FPS, 1.0)             # 1초당 어긋남 = 비율
        pts = []
        t = 0.0
        while t <= XMAX + 0.01:
            pts.append((px(t), py(drift_seconds(made, FPS, t))))
            if drift_seconds(made, FPS, t) >= YMAX:
                break
            t += 1.0
        o.append('<polyline class="ln" style="%s" points="%s"/>'
                 % (style, " ".join("%.1f,%.1f" % q for q in pts)))
        notes.append((name, rate * 100, cross))

    o.append('<text class="num" x="%.1f" y="%d">%sfps 로 뽑음</text>'
             % (px(notes[0][2]) + 10, y0 + 26, notes[0][0]))
    o.append('<text class="num" x="%.1f" y="%d" text-anchor="end">%sfps 로 뽑음</text>'
             % (x0 + pw - 4, y0 + ph - 16, notes[1][0]))

    o.append('<text class="num" x="4" y="%d">%sfps → %.1f%% 어긋남 · %.0f초에서 티가 난다   |   '
             '%sfps → %.2f%% · %.0f초에서 티가 난다</text>'
             % (H - 30, notes[0][0], notes[0][1], notes[0][2],
                notes[1][0], notes[1][1], notes[1][2]))
    o.append('<text class="sub" x="4" y="%d">둘 다 재생은 29.97fps(30000/1001). '
             '30 은 짧은 클립에서 멀쩡해 보여서 더 위험하다.</text>' % (H - 12))
    return save("f10_fpsdrift.svg", "\n".join(o), W, H,
                "틀린 fps 로 뽑으면 어긋남이 영상 길이에 비례해 쌓인다")


# ── F11 : 날것 음량 vs 네 처리 후 (실제 MouthDriver 로) ───────────────
#
# 신호를 **무음으로 시작** 시키는 것이 핵심이다. 회귀 테스트가 잡은 결함이
# 그 조건에서만 나타나기 때문이다 — 새 드라이버의 동적 천장은 최저값(0.05)이라
# 0.004 짜리 잡음이 천장 대비 '큰 소리' 로 계산된다. 소리가 한 번 난 뒤의
# 무음에서는 천장이 아직 높아 같은 잡음이 묻힌다. 그래서 두 무음을 다 그린다.
def f11():
    from mouth import MouthDriver
    W, H, x0, pw = 512, 274, 8, 496
    FPS, SECS = 30, 3.4
    N = int(FPS * SECS)
    SILS = ((0.0, 0.8), (2.0, 2.6))        # 시작 무음 · 중간 무음

    def raw(t):
        """합성 음량. 난수를 쓰지 않아 결과가 매번 같다."""
        for a, b in SILS:
            if a <= t < b:
                return 0.004               # 무음의 미세 잡음
        amp = 0.9 if t < SILS[1][0] else 0.45   # 뒷부분 절반 음량 — 동적 천장 확인
        env = 0.4 + 0.6 * abs(math.sin(2 * math.pi * 3.1 * t))
        return amp * env * (0.55 + 0.45 * math.sin(2 * math.pi * 7.3 * t + 1.1))

    lv = [max(0.0, raw(SECS * i / N)) for i in range(N + 1)]
    dg, dn = MouthDriver(), MouthDriver(noise_gate=0.0)
    with_gate = [dg.feed(v) for v in lv]
    no_gate = [dn.feed(v) for v in lv]

    def band(y, h):
        return "".join(
            '<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="#000" opacity=".05"/>'
            % (x0 + pw * s / SECS, y, pw * (e - s) / SECS, h) for s, e in SILS)

    def poly(vals, y, h, style=""):
        pts = " ".join("%.1f,%.1f" % (x0 + pw * i / N, y + h - h * v)
                       for i, v in enumerate(vals))
        return '<polyline class="ln" %s points="%s"/>' % (style, pts)

    o = ['<text class="ttl" x="4" y="17">날것의 음량은 못 쓴다 — 다섯 처리를 거친다</text>']

    o.append('<text class="sub" x="4" y="36">① 날것 RMS</text>')
    o.append(band(42, 54))
    o.append('<line class="ax" x1="%d" y1="96" x2="%d" y2="96"/>' % (x0, x0 + pw))
    o.append(poly([v / 0.95 for v in lv], 42, 54, 'style="stroke-width:1.1"'))

    o.append('<text class="sub" x="4" y="122">② MouthDriver 출력 — 입 벌림 0~1</text>')
    o.append(band(128, 74))
    o.append('<line class="ax" x1="%d" y1="202" x2="%d" y2="202"/>' % (x0, x0 + pw))
    o.append(poly(no_gate, 128, 74,
                  'style="stroke-width:1.2;stroke-dasharray:4 3;stroke:#7b8494"'))
    o.append(poly(with_gate, 128, 74))

    for sec in (0, 1, 2, 3):
        x = x0 + pw * sec / SECS
        o.append('<text class="sub" x="%.1f" y="216" text-anchor="middle">%d초</text>' % (x, sec))
    for (s, e), lab in zip(SILS, ("시작 무음", "무음")):
        o.append('<text class="sub" x="%.1f" y="140" text-anchor="middle">%s</text>'
                 % (x0 + pw * (s + e) / 2 / SECS, lab))

    i0, i1 = 0, int(FPS * SILS[0][1])
    bad, good = max(no_gate[i0:i1]), max(with_gate[i0:i1])
    o.append('<text class="num" x="4" y="238">점선 = 노이즈 게이트를 끈 것 — '
             '시작 무음에서 %.2f 까지 열린다 (게이트 있으면 %.2f).</text>' % (bad, good))
    o.append('<text class="sub" x="4" y="254">새 드라이버의 동적 천장은 최저값이라 '
             '0.004 짜리 잡음이 천장 대비 큰 소리가 된다.</text>')
    o.append('<text class="sub" x="4" y="268">두 번째 무음에서는 천장이 아직 높아 '
             '같은 잡음이 묻힌다 — 상대 기준만으로는 못 막는다.</text>')
    return save("f11_volume.svg", "\n".join(o), W, H,
                "노이즈 게이트가 없으면 시작 무음에서 입이 달싹인다")


def main():
    print()
    for fn in (f3, f7, f10, f11, f12):
        p = fn()
        print("  생성  %-22s %5d bytes" % (os.path.basename(p), os.path.getsize(p)))
    print("\n  → %s\n" % FIG)
    return 0


if __name__ == "__main__":
    sys.exit(main())

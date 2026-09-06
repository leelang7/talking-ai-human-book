# -*- coding: utf-8 -*-
"""HTML 한 벌을 PDF 한 번 찍는다 — 조판기(build_book.py)가 렌더마다 새 프로세스로 부른다.

한 프로세스에서 크로미움을 16회 돌리면 중간에 드라이버가 끊긴다(2026-09-06, 세 번).
sync API 는 한 프로세스에서 다시 start() 할 수도 없어서 복구가 안 된다.
그래서 **렌더 한 번 = 프로세스 한 번**. 3초쯤 더 들지만 15분짜리 조판이 통째로 날아가지 않는다.

    python scripts/_render_one.py <html> <pdf> <머리글:1|0> <가로mm> <세로mm> <위> <아래> <좌> <우> <제목>
"""
import sys


def main(argv):
    html, pdf, header = argv[1], argv[2], argv[3] == "1"
    w, h, mt, mb, ml, mr = argv[4:10]
    title = argv[10]
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--disable-gpu", "--disable-dev-shm-usage"])
        pg = b.new_page()
        try:
            pg.goto("file:///" + html.replace("\\", "/"))
            pg.wait_for_timeout(500)
            pg.pdf(path=pdf, width=w + "mm", height=h + "mm", print_background=True,
                   margin={"top": mt + "mm", "bottom": mb + "mm", "left": ml + "mm", "right": mr + "mm"},
                   display_header_footer=header,
                   header_template='<div style="font-size:7pt;color:#888;width:100%;text-align:center;'
                                   'font-family:serif">' + title + '</div>',
                   footer_template='<div style="font-size:8pt;color:#444;width:100%;text-align:center;'
                                   'font-family:serif"><span class="pageNumber"></span></div>')
        finally:
            # 크로미움을 닫는 도중에 드라이버 연결이 끊기는 일이 잦다(2026-09-06).
            # PDF 는 이미 다 써진 뒤라 여기서 죽으면 안 된다 — 닫기 실패는 삼킨다.
            for _c in (pg.close, b.close):
                try:
                    _c()
                except Exception:
                    pass
    return 0


def _ok(pdf):
    try:
        import fitz
        return fitz.open(pdf).page_count > 0
    except Exception:
        import os
        return os.path.exists(pdf) and os.path.getsize(pdf) > 1000


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as e:                       # 렌더 도중 끊김 — 산출물이 멀쩡하면 성공으로 본다
        if not _ok(sys.argv[2]):
            raise
        print("  (닫는 중 끊겼지만 PDF 는 정상: %s)" % type(e).__name__)
    sys.exit(0 if _ok(sys.argv[2]) else 1)

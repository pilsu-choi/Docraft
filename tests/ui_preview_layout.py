"""Isolated browser regression for preview fit, zoom, resize and overlays."""

import os
import tempfile
from pathlib import Path

import fitz
from playwright.sync_api import sync_playwright


def fixtures(directory):
    pdf = fitz.open()
    page = pdf.new_page(width=600, height=900)
    page.draw_rect(fitz.Rect(60, 90, 240, 150), color=(1, 0, 0), fill=(1, 0.9, 0.9))
    page.insert_text((70, 125), "Synthetic preview")
    pdf_path = directory / "source.pdf"
    image_path = directory / "source.png"
    pdf.save(pdf_path)
    page.get_pixmap(matrix=fitz.Matrix(5, 5)).save(image_path)
    pdf.close()
    return pdf_path.read_bytes(), image_path.read_bytes()


def geometry(page):
    return page.locator(".preview-scroll").evaluate("node => ({client: node.clientWidth, scroll: node.scrollWidth, left: node.scrollLeft})")


def check_fit(page, kind):
    source = page.locator(".page-image")
    source.wait_for()
    page.locator(".bbox").first.wait_for()
    if "image" in kind:
        page.wait_for_function("document.querySelector('.page-image img')?.naturalWidth > 0 && document.querySelector('.page-image').getBoundingClientRect().width > 100")
    else:
        page.wait_for_function("document.querySelector('.page-image canvas')?.getBoundingClientRect().width > 100 && Math.abs(document.querySelector('.page-image canvas').getBoundingClientRect().width - document.querySelector('.page-image').getBoundingClientRect().width) < 2")
    page.wait_for_function("document.querySelector('.page-image').getBoundingClientRect().width > 100")
    frame = page.locator(".preview-scroll").bounding_box()
    image = source.bounding_box()
    assert image["width"] <= frame["width"] - 35, (kind, frame, image)
    assert image["x"] >= frame["x"] + 15, (kind, frame, image)
    assert geometry(page)["scroll"] <= geometry(page)["client"] + 1, (kind, geometry(page))
    box = page.locator(".bbox").first.bounding_box()
    assert abs((box["x"] - image["x"]) / image["width"] - 0.1) < 0.015, (kind, box, image)
    assert abs((box["y"] - image["y"]) / image["height"] - 0.1) < 0.015, (kind, box, image, page.locator(".bbox").first.get_attribute("style"))
    return image


def main():
    with tempfile.TemporaryDirectory() as temp:
        pdf_bytes, png_bytes = fixtures(Path(temp))
        docs = [
            {"id": "d-pdf", "project_id": "preview", "filename": "source.pdf", "media_type": "application/pdf", "size": len(pdf_bytes), "status": "parsed", "blocks": [{"type": "text", "page": 1, "bbox": [60, 90, 240, 150], "page_size": [600, 900], "text": "Synthetic preview"}], "groundings": []},
            {"id": "d-image", "project_id": "preview", "filename": "source.png", "media_type": "image/png", "size": len(png_bytes), "status": "parsed", "blocks": [{"type": "text", "page": 1, "bbox": [300, 450, 1200, 750], "page_size": [3000, 4500], "text": "Synthetic preview"}], "groundings": []},
        ]
        errors = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
            page.on("pageerror", lambda error: errors.append(str(error)))

            def api(route):
                request = route.request
                assert request.method == "GET", f"Unexpected mutation: {request.method} {request.url}"
                path = request.url.split("/api", 1)[1].split("?", 1)[0]
                if path == "/projects":
                    payload = [{"id": "preview", "name": "Preview fixture", "created_at": "2026-09-21T00:00:00"}]
                elif path == "/projects/preview":
                    payload = {"id": "preview", "name": "Preview fixture", "created_at": "2026-09-21T00:00:00"}
                elif path == "/projects/preview/documents":
                    payload = docs
                elif path == "/projects/preview/schemas":
                    payload = []
                elif path.startswith("/documents/") and path.endswith("/file"):
                    content = pdf_bytes if "d-pdf" in path else png_bytes
                    route.fulfill(status=200, body=content, content_type="application/pdf" if "d-pdf" in path else "image/png")
                    return
                elif path.startswith("/documents/"):
                    payload = next(doc for doc in docs if doc["id"] == path.split("/")[2])
                else:
                    raise AssertionError(f"Unexpected API: {path}")
                route.fulfill(status=200, json=payload)

            page.route("**/api/**", api)
            base = os.environ.get("DOCRAFT_UI_URL", "http://127.0.0.1:5175").rstrip("/")
            page.goto(base, wait_until="networkidle")
            page.screenshot(path="/tmp/docraft-preview-home.png")
            page.goto(f"{base}/projects", wait_until="networkidle")
            page.screenshot(path="/tmp/docraft-preview-projects.png")
            page.get_by_role("button", name="새 프로젝트").last.click()
            assert page.get_by_placeholder("프로젝트 이름 (선택)").is_visible()
            page.get_by_role("button", name="프로젝트 목록").click()
            page.locator(".project-open").first.click()
            assert page.locator(".detail-grid").is_visible()
            page.goto(f"{base}/projects/preview", wait_until="networkidle")
            page.get_by_role("button", name="02 스키마 설계").click()
            prompt = page.get_by_placeholder("예: 거래처, 날짜, 금액과 품목별 내역")
            prompt.fill("Mock prompt retained")
            page.get_by_role("button", name="작업 패널 접기").click()
            page.get_by_role("button", name="작업 패널 펼치기").click()
            assert prompt.input_value() == "Mock prompt retained"
            page.get_by_role("button", name="03 데이터 추출").click()
            assert page.get_by_role("button", name="03 데이터 추출").get_attribute("aria-current") == "step"
            page.get_by_role("button", name="01 문서 분석").click()
            pdf = check_fit(page, "PDF desktop DPR2")
            canvas = page.locator("canvas").evaluate("node => ({intrinsic: node.width, css: node.getBoundingClientRect().width})")
            assert abs(canvas["intrinsic"] / canvas["css"] - 2) < 0.03, canvas
            page.screenshot(path="/tmp/docraft-preview-pdf-fit.png")

            page.locator(".preview-toolbar button").last.click()
            page.locator(".preview-toolbar button").last.click()
            page.wait_for_function("document.querySelector('.page-image').getBoundingClientRect().width > document.querySelector('.preview-scroll').clientWidth")
            assert geometry(page)["scroll"] > geometry(page)["client"]
            page.locator(".preview-scroll").evaluate("node => node.scrollLeft = node.scrollWidth")
            assert geometry(page)["left"] > 0
            page.screenshot(path="/tmp/docraft-preview-pdf-zoom.png")

            page.locator(".preview-toolbar button").nth(2).click()
            page.locator(".preview-toolbar button").nth(2).click()
            page.wait_for_function("document.querySelector('.preview-toolbar')?.textContent.includes('100%')")
            before_collapse = page.locator("canvas").bounding_box()["width"]
            page.get_by_role("button", name="작업 패널 접기").click()
            page.wait_for_function("document.querySelector('.preview-scroll').clientWidth > 900")
            page.wait_for_function("document.querySelector('canvas')?.getBoundingClientRect().width > 100")
            page.get_by_role("button", name="작업 패널 펼치기").click()
            page.wait_for_function("document.querySelector('.preview-scroll').clientWidth < 800")
            page.wait_for_function("width => Math.abs(document.querySelector('canvas')?.getBoundingClientRect().width - width) < 3", arg=before_collapse)
            page.reload(wait_until="networkidle")
            assert abs(check_fit(page, "PDF after panel reopen")["width"] - pdf["width"]) < 3

            page.get_by_role("button", name="source.png").click()
            check_fit(page, "image desktop")
            page.screenshot(path="/tmp/docraft-preview-image-fit.png")
            page.set_viewport_size({"width": 800, "height": 900})
            check_fit(page, "image narrow")
            page.get_by_role("button", name="source.pdf").click()
            check_fit(page, "PDF narrow")
            page.screenshot(path="/tmp/docraft-preview-narrow.png")
            page.set_viewport_size({"width": 390, "height": 844})
            check_fit(page, "PDF mobile 390")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "390px body horizontal overflow"
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path="/tmp/docraft-preview-mobile-390.png")
            browser.close()
        assert not errors, errors
    print("UI_PREVIEW_LAYOUT_OK /tmp/docraft-preview-{home,projects,pdf-fit,pdf-zoom,image-fit,narrow,mobile-390}.png")


if __name__ == "__main__":
    main()

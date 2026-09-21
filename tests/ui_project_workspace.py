"""Manual-runnable Chrome E2E for project navigation and collapsible panels."""

import os
import tempfile
import time

import fitz
from playwright.sync_api import sync_playwright


def synthetic_pdf() -> str:
    path = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
    pdf = fitz.open()
    page = pdf.new_page(width=360, height=240)
    page.insert_text((40, 72), "Vendor: Synthetic Co")
    page.insert_text((40, 96), "Amount: 1200")
    pdf.save(path)
    pdf.close()
    return path


def main():
    fixture = synthetic_pdf()
    name = f"E2E project {time.time_ns()}"
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("response", lambda response: errors.append(f"{response.status} {response.url}") if response.status >= 400 else None)
        page.goto("http://127.0.0.1:5174/", wait_until="networkidle")
        page.get_by_placeholder("프로젝트 이름 (선택)").fill(name)
        page.get_by_role("button", name="프로젝트 만들기").click()
        page.locator(".detail-identity h1").filter(has_text=name).wait_for()

        source = page.get_by_role("button", name="원문 패널 접기")
        before = page.locator(".work-area").bounding_box()["width"]
        source.click()
        page.get_by_role("button", name="원문 패널 펼치기").wait_for()
        assert page.locator(".work-area").bounding_box()["width"] > before
        page.get_by_role("button", name="원문 패널 펼치기").click()

        page.locator("input[type=file]").first.set_input_files(fixture)
        page.get_by_text(os.path.basename(fixture), exact=True).first.wait_for()
        page.get_by_text("Vendor: Synthetic Co", exact=False).first.wait_for(timeout=20_000)
        bbox = page.locator(".bbox").first
        bbox.wait_for()
        geometry = bbox.bounding_box()
        assert geometry["width"] > 1 and geometry["height"] > 1
        assert page.evaluate("node => getComputedStyle(node).outlineColor", bbox.element_handle()) == "rgb(228, 59, 50)"

        page.get_by_role("button", name="02 스키마 설계").click()
        prompt = page.get_by_placeholder("예: 거래처, 날짜, 금액과 품목별 내역")
        prompt.fill("거래처와 금액")
        page.get_by_role("button", name="작업 패널 접기").click()
        page.get_by_role("button", name="작업 패널 펼치기").wait_for()
        page.get_by_role("button", name="작업 패널 펼치기").click()
        assert prompt.input_value() == "거래처와 금액"
        assert page.get_by_role("button", name="02 스키마 설계").get_attribute("aria-current") == "step"

        # A parsed source is mandatory, but a prompt is optional: make a real
        # provider-backed schema from the synthetic PDF context.
        prompt.fill("")
        page.get_by_role("button", name="참고 자료로 스키마 생성").click()
        page.locator(".toast").filter(has_text="스키마를 생성했습니다.").wait_for(timeout=120_000)
        page.get_by_role("button", name="새 버전으로 저장").click()
        page.locator(".toast").filter(has_text="스키마를 저장했습니다.").wait_for(timeout=30_000)
        assert page.get_by_role("combobox", name="저장된 스키마").locator("option").count() > 1
        page.get_by_role("button", name="03 데이터 추출").click()
        page.get_by_role("button", name="현재 파일 추출").click()
        page.locator(".toast").filter(has_text="추출을 시작했습니다.").wait_for(timeout=30_000)
        result = page.locator(".result-field").first
        result.wait_for(timeout=120_000)
        assert result.locator("b").inner_text().strip()
        result.get_by_role("button", name="수정").click()
        result.locator("textarea").fill('"Synthetic corrected"')
        result.get_by_role("button", name="저장").click()
        page.locator(".toast").filter(has_text="수정 내용을 저장했습니다.").wait_for(timeout=30_000)
        with page.expect_download(timeout=30_000):
            page.locator(".editor-actions").get_by_role("button", name="JSON 다운로드").click()

        # Closing the other panel reopens source first: never leave both panels closed.
        page.get_by_role("button", name="원문 패널 접기").click()
        page.get_by_role("button", name="작업 패널 접기").click()
        page.get_by_role("button", name="작업 패널 펼치기").wait_for()
        assert page.get_by_role("button", name="원문 패널 접기").is_visible()
        page.get_by_role("button", name="작업 패널 펼치기").click()
        assert page.locator(".result-field").first.is_visible()
        page.screenshot(path="/tmp/docraft-project-workspace-e2e.png", full_page=True)

        page.get_by_role("button", name="프로젝트 목록").click()
        page.get_by_text(name, exact=True).wait_for()
        page.on("dialog", lambda dialog: dialog.accept(f"{name} renamed") if dialog.type == "prompt" else dialog.accept())
        row = page.locator(".project-row").filter(has_text=name)
        row.get_by_role("button", name="이름 변경").click()
        page.get_by_text(f"{name} renamed", exact=True).wait_for()
        page.locator(".project-row").filter(has_text=f"{name} renamed").get_by_role("button", name="삭제").click()
        page.get_by_text(f"{name} renamed", exact=True).wait_for(state="detached")
        browser.close()
    os.unlink(fixture)
    assert not errors, errors
    print("UI_PROJECT_WORKSPACE_OK /tmp/docraft-project-workspace-e2e.png")


if __name__ == "__main__":
    main()

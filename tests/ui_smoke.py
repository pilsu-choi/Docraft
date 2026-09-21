"""Run against local backend :8000 and frontend :5173 using installed Chrome."""
import json
import os
import tempfile
import time

from playwright.sync_api import sync_playwright


def main():
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as fixture:
        fixture.write("Patient: Jane Doe\nAmount: 1200\n")
        fixture_path = fixture.name
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        key = os.getenv("DOCRAFT_UI_API_KEY", "")
        if key:
            page.add_init_script(f"sessionStorage.setItem('docraft_api_key', {json.dumps(key)})")
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("response", lambda response: errors.append(f"{response.status} {response.url}") if response.status >= 400 and not response.url.endswith("favicon.ico") else None)
        page.goto("http://127.0.0.1:5173", wait_until="networkidle")
        page.locator(".project-switch").click()
        page.get_by_placeholder("예: 의료 청구서").fill(f"UI Smoke {time.time_ns()}")
        page.get_by_role("button", name="프로젝트 생성").click()
        page.get_by_text("WORKSPACE / UI Smoke", exact=False).wait_for()
        page.locator("input[type=file]").first.set_input_files(fixture_path)
        page.get_by_text(os.path.basename(fixture_path), exact=True).wait_for()
        page.get_by_text(os.path.basename(fixture_path), exact=True).click()
        page.get_by_text("Patient: Jane Doe", exact=False).wait_for()
        page.get_by_role("button", name="스키마", exact=True).click()
        page.get_by_placeholder("예: 병원명, 환자명, 진료일자와 진료 내역을 추출해줘").fill("Patient, Amount")
        page.get_by_role("button", name="AI 스키마 생성").click()
        page.get_by_text("AI가 스키마 버전을 생성했습니다.").wait_for()
        page.locator("select").select_option(index=1)
        page.get_by_role("button", name="이 스키마로 추출 실행 →").click()
        page.get_by_role("button", name="추출 결과").click()
        patient = page.locator("article.field").filter(has_text="patient")
        patient.get_by_role("button", name="수정").click()
        patient.locator("textarea").fill('"Janet Doe"')
        patient.get_by_role("button", name="저장").click()
        page.get_by_text("수정 내용을 저장했습니다.").wait_for()
        page.get_by_role("button", name="승인", exact=True).click()
        page.get_by_text("문서를 승인했습니다.").wait_for()
        with page.expect_download() as download_info:
            page.get_by_role("button", name="JSON 다운로드").click()
        content = json.loads(open(download_info.value.path(), encoding="utf-8").read())
        assert content["patient"] == "Janet Doe"
        page.screenshot(path="/tmp/docraft-ui-smoke.png", full_page=True)
        browser.close()
    assert not errors, errors
    print("UI_SMOKE_OK /tmp/docraft-ui-smoke.png")


if __name__ == "__main__":
    main()

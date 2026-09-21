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
        name = f"UI Smoke {time.time_ns()}"
        page.get_by_placeholder("프로젝트 이름 (선택)").fill(name)
        page.get_by_role("button", name="프로젝트 만들기").click()
        page.locator(".detail-identity h1").filter(has_text=name).wait_for()
        page.locator("input[type=file]").first.set_input_files(fixture_path)
        page.locator(".file-list").get_by_text(os.path.basename(fixture_path), exact=True).wait_for()
        page.get_by_text("Patient: Jane Doe", exact=False).wait_for()
        page.get_by_role("button", name="02 스키마 설계").click()
        page.get_by_placeholder("예: 거래처, 날짜, 금액과 품목별 내역").fill("Patient, Amount")
        page.get_by_role("button", name="참고 자료로 스키마 생성").click()
        page.locator(".toast").filter(has_text="스키마를 생성했습니다.").wait_for(timeout=120_000)
        page.get_by_role("button", name="03 데이터 추출").click()
        page.get_by_role("button", name="현재 파일 추출").click()
        page.locator(".toast").filter(has_text="추출을 시작했습니다.").wait_for()
        patient = page.locator(".result-field").filter(has_text="patient")
        patient.wait_for(timeout=120_000)
        patient.get_by_role("button", name="수정").click()
        patient.locator("textarea").fill('"Janet Doe"')
        patient.get_by_role("button", name="저장").click()
        page.get_by_text("수정 내용을 저장했습니다.").wait_for()
        page.get_by_role("button", name="결과 승인").click()
        page.locator(".toast").filter(has_text="결과를 승인했습니다.").wait_for()
        with page.expect_download() as download_info:
            page.locator(".editor-actions").get_by_role("button", name="JSON 다운로드").click()
        content = json.loads(open(download_info.value.path(), encoding="utf-8").read())
        assert content["patient"] == "Janet Doe"
        page.screenshot(path="/tmp/docraft-ui-smoke.png", full_page=True)
        browser.close()
    assert not errors, errors
    print("UI_SMOKE_OK /tmp/docraft-ui-smoke.png")


if __name__ == "__main__":
    main()

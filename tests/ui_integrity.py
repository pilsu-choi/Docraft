"""Browser regression against a built preview; API replies are synthetic and never reach a backend."""
import argparse
import json
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18103")
    parser.add_argument("--browser")
    args = parser.parse_args()
    stamp = "2026-10-03T00:00:00Z"
    project = {"id": "integrity", "name": "부분 추출 검토", "created_at": stamp}
    schema = {"id": "schema", "name": "표", "version": 1, "json_schema": {"type": "object", "properties": {"name": {"type": "string"}}}}
    doc = {"id": "doc", "project_id": "integrity", "filename": "partial.txt", "media_type": "text/plain", "size": 5,
           "status": "needs_review", "result": {"name": "보존된 값"}, "schema_id": "schema", "created_at": stamp, "updated_at": stamp,
           "markdown": "원문", "blocks": [], "validation": [], "groundings": [],
           "completeness": {"partial": True, "pages": [1, 2, 3], "successful_pages": [1, 3], "failed_pages": [2]}}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, **({"executable_path": args.browser} if args.browser else {}))
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        def api(route):
            path = urlparse(route.request.url).path
            replies = {"/api/projects": [project], "/api/projects/integrity": project,
                       "/api/projects/integrity/documents": [doc], "/api/projects/integrity/schemas": [schema],
                       "/api/documents/doc": doc, "/api/ai/status": {"configured": False, "provider": None, "model": None, "mode": "local"}}
            if path == "/api/documents/doc/file":
                route.fulfill(status=200, content_type="text/plain", body="원문")
            else:
                assert path in replies, path
                route.fulfill(status=200, content_type="application/json", body=json.dumps(replies[path], ensure_ascii=False))
        page.route("**/api/**", api)
        page.goto(args.base_url + "/projects/integrity", wait_until="networkidle")
        page.get_by_role("button", name="03 데이터 추출").click()
        alert = page.get_by_role("alert").filter(has_text="일부 페이지 판독 실패")
        alert.wait_for()
        assert "2쪽" in alert.inner_text()
        assert page.get_by_role("button", name="결과 승인").is_disabled()
        page.get_by_role("tab", name="결과 표", exact=True).click()
        page.get_by_text("부분 결과 · 실패 2쪽", exact=True).wait_for()
        page.screenshot(path="/tmp/docraft-integrity-ui.png", full_page=True)
        for status, partial, disabled in (("queued", False, True), ("completed", False, False)):
            doc.update(status=status, completeness={"partial": partial})
            page.reload(wait_until="networkidle")
            page.get_by_role("button", name="03 데이터 추출").click()
            button = page.get_by_role("button", name="결과 승인")
            button.wait_for()
            assert button.is_disabled() is disabled
        browser.close()
    assert not errors, errors
    print("UI_INTEGRITY_OK /tmp/docraft-integrity-ui.png")


if __name__ == "__main__":
    main()

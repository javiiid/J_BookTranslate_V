from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    artifacts = Path(__file__).resolve().parents[1] / "ui" / "node_modules" / ".tmp" / "conversion"
    artifacts.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:5173/convert")
        expect(page.get_by_role("heading", name="تبدیل فایل", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="تبدیل فایل", exact=True)).to_have_attribute("aria-current", "page")
        expect(page.get_by_role("button", name="شروع تبدیل", exact=True)).to_be_disabled()
        page.locator('input[type="file"]').set_input_files({"name": "empty.txt", "mimeType": "text/plain", "buffer": b""})
        expect(page.get_by_role("alert")).to_contain_text("خالی")
        page.locator('input[type="file"]').set_input_files({
            "name": "persian-ui-test.txt",
            "mimeType": "text/plain",
            "buffer": "آزمایش تبدیل فایل از رابط کاربری.\n\nKALIMA conversion test.".encode("utf-8"),
        })
        for checkbox in page.get_by_role("checkbox").all():
            checkbox.check()
        page.get_by_role("button", name="شروع تبدیل", exact=True).click()
        page.get_by_role("link", name="کتابخانه", exact=True).click()
        page.get_by_role("link", name="تبدیل فایل", exact=True).click()
        expect(page.get_by_role("link", name="↓ دریافت Word", exact=True)).to_be_visible(timeout=60000)
        expect(page.locator('a[download]')).to_have_count(5)
        with page.expect_download() as download_info:
            page.get_by_role("link", name="↓ دریافت Word", exact=True).click()
        assert download_info.value.failure() is None
        page.screenshot(path=str(artifacts / "light.png"), full_page=True)
        page.get_by_role("button", name="روشن کردن حالت تاریک", exact=True).click()
        page.screenshot(path=str(artifacts / "dark.png"), full_page=True)
        page.get_by_role("button", name="عملیات این نشست", exact=False).click()
        expect(page.get_by_role("heading", name="persian-ui-test.txt", exact=True)).to_be_visible()
        assert not errors, errors
        print("PASS: route, navigation, empty-file validation, five outputs, route persistence, download, history, themes; no browser errors")
        print(f"Screenshots: {artifacts}")
        browser.close()


if __name__ == "__main__":
    main()

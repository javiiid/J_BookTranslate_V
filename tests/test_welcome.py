from app.welcome.page import welcome_page


def test_welcome_page_has_primary_user_paths():
    page = welcome_page()
    assert 'href="/workspace#new-translation"' in page
    assert 'href="/workspace#active-jobs"' in page
    assert 'href="/library"' in page


def test_welcome_page_uses_live_status_and_local_font():
    page = welcome_page()
    assert "fetch('/api/dashboard/summary')" in page
    assert "fetch('/api/jobs')" in page
    assert "fetch('/api/health')" in page
    assert "data:font/woff2;base64" in page
    assert "fonts.googleapis.com" not in page

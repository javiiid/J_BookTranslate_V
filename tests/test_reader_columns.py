from app.reader.page import reader_page


def test_reader_page_includes_columns_mode_option():
    page = reader_page("job-1")
    assert 'value="columns"' in page
    assert "renderColumns" in page
    assert ".columns2" in page
    assert "col-head" in page
    assert "sides.forEach" in page


def test_reader_page_keeps_existing_modes_and_sync_controls():
    page = reader_page("job-1")
    for value in ("translation", "bilingual", "columns", "original"):
        assert f'value="{value}"' in page
    assert "parallel-block" in page


def test_columns_layout_stacks_on_mobile():
    page = reader_page("job-1")
    assert "grid-template-columns:1fr" in page
    assert "columns2 .col{overflow:visible" in page


def test_columns_render_pairs_original_and_translation():
    page = reader_page("job-1")
    assert "col-original" in page
    assert "col-trans" in page
    assert "متن اصلی" in page
    assert "ترجمه" in page


def test_columns_has_user_friendly_header_toggle():
    page = reader_page("job-1")
    assert 'id="columns-btn"' in page
    assert "aria-pressed" in page
    assert "setMode" in page
    assert "lastMode" in page


def test_columns_supports_swapping_the_two_boxes():
    page = reader_page("job-1")
    assert 'id="cols-swap"' in page
    assert "cols-toolbar" in page
    assert "insertBefore" in page
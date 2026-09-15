from app.library.view import library_page
from app.storage.database import Database


def test_library_schema_migrates_and_page_exists(tmp_path):
    database = Database(tmp_path / "library.db")
    columns = {row["name"] for row in database.fetch_all("PRAGMA table_info(files)")}
    assert "book_id" in columns
    assert "checksum" in columns
    book_id = database.execute("INSERT INTO library_books(title, created_at, updated_at) VALUES (?, ?, ?)", ("Demo", "now", "now"))
    database.execute("INSERT INTO files(book_id, path, kind, display_name, extension, size_bytes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (book_id, "demo.epub", "original", "demo.epub", "epub", 10, "now"))
    assert database.fetch_one("SELECT title FROM library_books WHERE id=?", (book_id,))["title"] == "Demo"
    page = library_page()
    assert "کتابخانه" in page
    assert "/api/library" in page

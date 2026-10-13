# ============================================================
# Translation memory engine tests
# ============================================================
#
# Before any provider API call the engine exact-matches the chunk in
# translation_memory; on a hit the stored translation is served with zero
# API cost. After every successful chunk the pair is stored back.
#
# No real API request is sent. No API tokens are consumed.
#
# ============================================================

from app.storage.database import Database
from app.translation import memory
from app.translation import translator
from app.translation.translator import (
    process_translations,
    translate_chunk,
)


# ============================================================
# FAKES
# ============================================================

class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    """Count every API call; always succeed with fixed Persian text."""

    def __init__(self):
        self.calls = 0

    def create(self, model, messages, temperature, **kwargs):
        self.calls += 1
        return FakeResponse("متن ترجمه‌شده")


class FakeChat:
    def __init__(self, completions):
        self.completions = completions


class FakeClient:
    def __init__(self, completions):
        self.chat = FakeChat(completions)


def make_client():
    completions = FakeCompletions()
    return FakeClient(completions), completions


def make_database(tmp_path):
    return Database(tmp_path / "memory.db")


def make_paths(tmp_path):
    return {
        "job_dir": tmp_path,
        "translations_file": tmp_path / "translations.json",
    }


# ============================================================
# LOOKUP / STORE
# ============================================================

def test_lookup_miss_returns_none(tmp_path):
    database = make_database(tmp_path)
    assert memory.lookup(database, "Hello world.", "EN", "FA") is None
    # A miss writes nothing.
    assert database.fetch_all("SELECT * FROM translation_memory") == []


def test_store_then_lookup_hit_refreshes_last_used(tmp_path):
    database = make_database(tmp_path)
    memory.store(database, "Hello world.", "سلام دنیا.", "EN", "FA")
    row = database.fetch_one("SELECT source, confidence FROM translation_memory")
    assert row["source"] == "auto"
    assert row["confidence"] == 1.0
    database.execute("UPDATE translation_memory SET last_used_at='2000-01-01T00:00:00+00:00'")
    assert memory.lookup(database, "Hello world.", "EN", "FA") == "سلام دنیا."
    refreshed = database.fetch_one("SELECT last_used_at FROM translation_memory")
    assert refreshed["last_used_at"] != "2000-01-01T00:00:00+00:00"


def test_lookup_is_scoped_by_language_pair(tmp_path):
    database = make_database(tmp_path)
    memory.store(database, "Hello world.", "سلام دنیا.", "EN", "FA")
    assert memory.lookup(database, "Hello world.", "EN", "FA") == "سلام دنیا."
    assert memory.lookup(database, "Hello world.", "EN", "DE") is None
    assert memory.lookup(database, "Hello world.", "DE", "FA") is None


def test_store_upsert_updates_translation_on_conflict(tmp_path):
    database = make_database(tmp_path)
    memory.store(database, "Hello world.", "سلام دنیا.", "EN", "FA")
    memory.store(database, "Hello world.", "سلام دنیا!", "EN", "FA")
    rows = database.fetch_all("SELECT translated_text FROM translation_memory")
    assert [row["translated_text"] for row in rows] == ["سلام دنیا!"]
    assert memory.lookup(database, "Hello world.", "EN", "FA") == "سلام دنیا!"


def test_store_refuses_empty_inputs(tmp_path):
    database = make_database(tmp_path)
    memory.store(database, "", "سلام.", "EN", "FA")
    memory.store(database, "Hello.", "", "EN", "FA")
    assert database.fetch_all("SELECT * FROM translation_memory") == []


def test_lookup_failure_is_a_miss_not_a_crash(tmp_path):
    class BrokenDb:
        def fetch_one(self, sql, params=()):
            raise RuntimeError("disk gone")

    assert memory.lookup(BrokenDb(), "Hello world.", "EN", "FA") is None
    # And storing into it must not raise either.
    memory.store(BrokenDb(), "Hello world.", "سلام دنیا.", "EN", "FA")


# ============================================================
# TRANSLATE_CHUNK
# ============================================================

def test_translate_chunk_serves_from_memory_with_zero_api_calls(tmp_path):
    database = make_database(tmp_path)
    memory.store(database, "Hello world.", "سلام دنیا.", "EN", "FA")
    client, completions = make_client()
    record = []
    result = translate_chunk(
        client=client,
        text="Hello world.",
        chunk_id="chunk-0",
        from_lang="EN",
        to_lang="FA",
        model="gpt-5.6-luna",
        filetype="epub",
        memory_db=database,
        memory_record=record,
    )
    assert result == "سلام دنیا."
    assert completions.calls == 0
    assert record == ["chunk-0"]


def test_translate_chunk_writes_back_after_api_success(tmp_path):
    database = make_database(tmp_path)
    client, completions = make_client()
    result = translate_chunk(
        client=client,
        text="Hello world.",
        chunk_id="chunk-0",
        from_lang="EN",
        to_lang="FA",
        model="gpt-5.6-luna",
        filetype="epub",
        memory_db=database,
    )
    assert result == "متن ترجمه‌شده"
    assert completions.calls == 1
    assert memory.lookup(database, "Hello world.", "EN", "FA") == "متن ترجمه‌شده"


def test_test_mode_never_touches_memory(tmp_path):
    database = make_database(tmp_path)
    client, completions = make_client()
    result = translate_chunk(
        client=client,
        text="Hello world.",
        chunk_id="chunk-0",
        from_lang="EN",
        to_lang="FA",
        model="gpt-5.6-luna",
        filetype="epub",
        test_translations={"chunk-0": "ترجمهٔ آزمایشی"},
        memory_db=database,
    )
    assert result == "ترجمهٔ آزمایشی"
    assert completions.calls == 0
    assert database.fetch_all("SELECT * FROM translation_memory") == []


# ============================================================
# END TO END
# ============================================================

def test_memory_bypass_pays_for_fresh_and_writes_nothing(tmp_path):
    database = make_database(tmp_path)
    memory.store(database, "Hello world.", "سلام دنیا.", "EN", "FA")
    client, completions = make_client()
    result = translate_chunk(
        client=client,
        text="Hello world.",
        chunk_id="chunk-0",
        from_lang="EN",
        to_lang="FA",
        model="gpt-5.6-luna",
        filetype="epub",
        memory_db=False,
    )
    assert result == "متن ترجمه‌شده"
    assert completions.calls == 1
    translate_chunk(
        client=client,
        text="Brand new sentence.",
        chunk_id="chunk-1",
        from_lang="EN",
        to_lang="FA",
        model="gpt-5.6-luna",
        filetype="epub",
        memory_db=False,
    )
    assert completions.calls == 2
    assert memory.lookup(database, "Brand new sentence.", "EN", "FA") is None


def test_second_run_of_same_chunks_costs_zero_api_calls(tmp_path):
    database = make_database(tmp_path)
    from app.storage import database as database_module

    # Route the engine's lazy singleton at this test's database.
    previous, database_module.db = database_module.db, database
    try:
        client, completions = make_client()
        chunks = [(f"chunk-{i}", f"Repeated heading {i}.") for i in range(2)]
        first, _, _ = process_translations(
            client, chunks, {}, "resume", "EN", "FA",
            make_paths(tmp_path), model="gpt-5.6-luna", filetype="epub",
        )
        assert completions.calls == 2
        second, _, _ = process_translations(
            client, chunks, {}, "resume", "EN", "FA",
            make_paths(tmp_path), model="gpt-5.6-luna", filetype="epub",
        )
        assert completions.calls == 2
        assert second == first
    finally:
        database_module.db = previous


def test_concurrent_path_uses_memory(monkeypatch, tmp_path):
    database = make_database(tmp_path)
    from app.storage import database as database_module

    previous, database_module.db = database_module.db, database
    monkeypatch.setattr(translator, "_translation_concurrency", lambda: 4)
    monkeypatch.setattr(translator, "_build_rate_limiter", lambda concurrency: None)
    try:
        memory.store(database, "Repeated heading.", "تیتر تکراری.", "EN", "FA")
        client, completions = make_client()
        chunks = [
            ("chunk-0", "Repeated heading."),
            ("chunk-1", "Fresh sentence one."),
            ("chunk-2", "Fresh sentence two."),
        ]
        translations, _, _ = process_translations(
            client, chunks, {}, "fast", "EN", "FA",
            make_paths(tmp_path), model="gpt-5.6-luna", filetype="epub",
        )
        assert completions.calls == 2
        assert translations["chunk-0"] == "تیتر تکراری."
        assert translations["chunk-1"] == "متن ترجمه‌شده"
        assert translations["chunk-2"] == "متن ترجمه‌شده"
    finally:
        database_module.db = previous

"""Regression tests for three bugs found during the September audit.

1. Cross-origin writes. A local HTTP server with no origin check can be driven
   by any web page the user visits, because a cross-origin POST with
   `Content-Type: text/plain` is a CORS "simple request": the browser sends it
   with no preflight, so CORS cannot stop it. That would let a page spend the
   user's provider credits.

2. `to_lang` was never passed to `generate_outputs` at any of its three call
   sites in the pipeline. It defaulted to `""`, so every writer's
   `rtl = str(to_lang).upper() in {"FA","AR","UR","HE"}` was False and a Persian
   translation was laid out left-to-right in every PDF/DOCX export.

3. `save_partial_batch_results` called `save_translations(...)` without
   importing it. The NameError was swallowed by a broad `except` and the caller
   had already deleted the batch state file, so translations the provider had
   already billed for were dropped and the user was told "No batch state found."

4. `auto_extract` forced max_workers=1, so every default web job translated one
   chunk at a time despite concurrency being configurable, and glossary
   learning ran inline on the commit loop. `glossary_mode` now makes the
   tradeoff explicit: "deferred" (default) keeps chunks in flight and learns
   terms afterwards; "inline" keeps propagation and forces sequential.
"""
import io
import json
import socket
import sys
import tempfile
import threading
import time
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.output.formats import generate_outputs
from app.translation.batch import save_partial_batch_results
from app.web import _loopback_authority, _origin_permitted

PERSIAN = "این یک جملهٔ فارسی است که باید از راست به چپ رندر شود."


# --------------------------------------------------------------------------
# 1. Cross-origin / DNS-rebinding guard
# --------------------------------------------------------------------------

@pytest.mark.parametrize("origin", [
    "http://127.0.0.1:8765",
    "http://localhost:8765",
    "http://localhost:5173",   # Vite dev proxy
    "http://127.0.0.1:3000",   # another local dev tool
])
def test_loopback_origins_are_allowed(origin):
    assert _origin_permitted(origin) is True


@pytest.mark.parametrize("origin", [
    "https://attacker.example",
    "http://attacker.example",
    "null",
    "http://127.0.0.1.evil.com",      # suffix lookalike
    "http://localhost.evil.com",
    "http://127.0.0.1:8765.evil.com",  # port lookalike
    "file://",
    "",
])
def test_foreign_origins_are_refused(origin):
    assert _origin_permitted(origin) is False


@pytest.mark.parametrize("host,expected", [
    ("127.0.0.1:8765", True),
    ("localhost:8765", True),
    ("127.0.0.1", True),
    ("localhost", True),
    ("attacker.example", False),
    ("127.0.0.1.attacker.example", False),
    ("192.168.1.5:8765", False),
])
def test_host_authority_blocks_dns_rebinding(host, expected):
    assert _loopback_authority(host) is expected


@pytest.fixture
def live_server():
    """Run the real Handler on an ephemeral port.

    The success-path request really does insert a key, so the fixture removes
    anything it created. A test must not leave rows in the user's database.
    """
    from app.storage.database import db
    from app.web import Handler

    before = {row["name"] for row in db.fetch_all("SELECT name FROM account_api_keys")}
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        after = {row["name"] for row in db.fetch_all("SELECT name FROM account_api_keys")}
        for name in after - before:
            db.execute("DELETE FROM account_api_keys WHERE name=?", (name,))


def _raw_post(base, *, origin, content_type, host=None, body=b"{}"):
    """Send a request with headers urllib would otherwise rewrite."""
    import urllib.parse

    parsed = urllib.parse.urlparse(base)
    authority = host or f"{parsed.hostname}:{parsed.port}"
    head = [
        f"POST /api/account/api-keys HTTP/1.1",
        f"Host: {authority}",
        f"Content-Type: {content_type}",
        f"Content-Length: {len(body)}",
        "Connection: close",
    ]
    if origin is not None:
        head.append(f"Origin: {origin}")
    request = ("\r\n".join(head) + "\r\n\r\n").encode("utf-8") + body
    with socket.create_connection((parsed.hostname, parsed.port), timeout=5) as sock:
        sock.sendall(request)
        chunks = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
    return b"".join(chunks).split(b"\r\n", 1)[0].decode("latin-1")


def test_cross_origin_write_is_refused(live_server):
    """The exact request that used to return 201 Created."""
    status = _raw_post(
        live_server,
        origin="https://attacker.example",
        content_type="text/plain;charset=UTF-8",
        body=json.dumps({"name": "csrf-probe"}).encode(),
    )
    assert "403" in status, status


def test_same_origin_write_is_permitted(live_server):
    status = _raw_post(
        live_server,
        origin=None,
        content_type="application/json",
        body=json.dumps({"name": "legit-probe"}).encode(),
    )
    assert "201" in status, status


def test_foreign_host_is_refused_on_read(live_server):
    """DNS rebinding: a rebound page is same-origin to the attacker, so a GET
    response would be readable unless the Host header is checked."""
    import urllib.parse

    parsed = urllib.parse.urlparse(live_server)
    request = (
        "GET /api/jobs HTTP/1.1\r\n"
        "Host: attacker.example\r\n"
        "Connection: close\r\n\r\n"
    ).encode()
    with socket.create_connection((parsed.hostname, parsed.port), timeout=5) as sock:
        sock.sendall(request)
        chunks = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
    status = b"".join(chunks).split(b"\r\n", 1)[0].decode("latin-1")
    assert "403" in status, status


# --------------------------------------------------------------------------
# 2. to_lang must reach the output writers
# --------------------------------------------------------------------------

def _segments():
    return [{
        "id": "chunk-0",
        "source": "This is an English sentence.",
        "target": PERSIAN,
        "chapter": "OEBPS/ch01.xhtml",
        "chapter_title": "Chapter 1",
        "notes": [],
        "flagged": False,
    }]


def _write(lang, tmp_path):
    result = generate_outputs(
        _segments(),
        requested=["docx", "markdown"],
        output_dir=tmp_path,
        base_name="book",
        filetype="epub",
        title="Book",
        to_lang=lang,
    )
    return {name: Path(path) for name, path in (result.get("generated") or {}).items()}


def _bidi_paragraph_count(docx_path: Path) -> int:
    with zipfile.ZipFile(docx_path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    # <w:bidi/> also sits in the unconditional default styles, so count the
    # paragraph-level property that the writer adds only when rtl is true.
    return xml.count("<w:pPr><w:bidi/></w:pPr>")


def test_rtl_target_produces_bidi_paragraphs(tmp_path):
    fa_files = _write("FA", tmp_path / "fa")
    en_files = _write("EN", tmp_path / "en")
    fa_count = _bidi_paragraph_count(fa_files["docx"])
    en_count = _bidi_paragraph_count(en_files["docx"])
    assert fa_count > en_count, f"FA produced {fa_count} bidi paragraphs, EN produced {en_count}"


def test_to_lang_reaches_markdown_writer(tmp_path):
    files = _write("FA", tmp_path)
    assert "target language: FA" in files["markdown"].read_text(encoding="utf-8")


def test_pipeline_passes_to_lang_to_generate_outputs():
    """Guard the call sites themselves, not just the writers.

    A test that calls the writers directly would still pass if someone removed
    `to_lang=` from the pipeline again, which is exactly the original bug.
    """
    source = Path(__file__).resolve().parents[1] / "app" / "pipeline" / "pipeline.py"
    text = source.read_text(encoding="utf-8")
    calls = text.count("generate_outputs(")
    assert calls >= 3, f"expected 3 generate_outputs call sites, found {calls}"
    # Every call must forward to_lang.
    import re
    blocks = re.findall(r"generate_outputs\((?:[^()]|\([^()]*\))*\)", text, re.S)
    missing = [block for block in blocks if "to_lang=to_lang" not in block]
    assert not missing, f"{len(missing)} generate_outputs call site(s) omit to_lang"


# --------------------------------------------------------------------------
# 3. A completed batch must not lose its translations
# --------------------------------------------------------------------------

def _batch_line(chunk_id, text):
    """One line of a downloaded provider batch output file."""
    return json.dumps({
        "custom_id": chunk_id,
        "response": {
            "error": None,
            "body": {"choices": [{"message": {"content": text}}]},
        },
    })


def test_partial_batch_results_are_persisted(tmp_path):
    """A batch that finished some requests must save what it paid for."""
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    paths = {
        "job_dir": str(job_dir),
        "chunks_file": str(job_dir / "chunks.json"),
        "translations_file": str(job_dir / "translations.json"),
        "state_file": str(job_dir / "job_state.json"),
    }
    (job_dir / "chunks.json").write_text(
        json.dumps({"chunks": [["chunk-0", "Hello"], ["chunk-1", "World"]],
                    "chapter_map": {}}),
        encoding="utf-8",
    )
    state_path = job_dir / "batch_status_x.json"
    state_path.write_text(json.dumps({"paths": paths}), encoding="utf-8")

    output_path = job_dir / "batch_x_output.jsonl"
    output_path.write_text(
        "\n".join([
            _batch_line("chunk-0", "سلام"),
            _batch_line("chunk-1", "جهان"),
            json.dumps({"custom_id": "chunk-2", "response": {"error": "rate limited"}}),
        ]) + "\n",
        encoding="utf-8",
    )

    # `status` is the provider SDK's Batch object and is read via attributes.
    status = SimpleNamespace(
        status="expired",
        output_file_id="file-abc123",
        request_counts=SimpleNamespace(completed=2, total=3),
    )

    class FakeFiles:
        def content(self, file_id):
            assert file_id == "file-abc123"
            return io.BytesIO(output_path.read_bytes())

    result = save_partial_batch_results(
        client=SimpleNamespace(files=FakeFiles()),
        temp_dir=job_dir,
        batch_id="x",
        state_file_path=str(state_path),
        status=status,
    )

    assert result, "save_partial_batch_results returned nothing; translations were lost"
    assert set(result) == {"chunk-0", "chunk-1"}

    translations_file = Path(paths["translations_file"])
    assert translations_file.is_file(), "translations.json was never written"
    saved = json.loads(translations_file.read_text(encoding="utf-8"))
    assert set(saved) == {"chunk-0", "chunk-1"}


def test_batch_module_imports_save_translations():
    """Guard the import itself.

    The original bug was a missing import whose NameError was swallowed. The
    behaviour test above would also pass if some other code path hid it, so
    assert the symbol is actually bound in the module.
    """
    from app.translation import batch

    assert hasattr(batch, "save_translations"), (
        "batch.py must import save_translations; otherwise saving partial "
        "batch results raises NameError and the work is discarded"
    )


# --------------------------------------------------------------------------
# 4. Concurrency and the adaptive rate limiter
# --------------------------------------------------------------------------

def test_translation_runs_chunks_concurrently(monkeypatch, tmp_path):
    """Several chunks must be in flight at once.

    Previously `auto_extract` forced max_workers=1, so every default web job
    translated one chunk at a time even with concurrency configured.

    Request pacing is disabled here on purpose: the limiter spreads requests
    apart by design, so leaving it armed would measure the limiter instead of
    the concurrency. Pacing is covered by its own tests below.
    """
    from app.core.paths import ensure_temp_structure
    from app.translation import translator
    from app.translation.translator import process_translations

    paths = ensure_temp_structure("concurrency_probe")
    try:
        Path(paths["chunks_file"]).write_text(
            json.dumps({"chunks": [], "chapter_map": {}}), encoding="utf-8"
        )
        Path(paths["job_dir"], "glossary.json").write_text(
            json.dumps({"auto_extract": True, "terms": []}), encoding="utf-8"
        )

        lock = threading.Lock()
        peak = {"value": 0, "current": 0}

        def response(content):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )

        def create(**kwargs):
            if kwargs["messages"][0]["content"].startswith("Extract a concise book glossary"):
                return response(json.dumps({"terms": []}))
            with lock:
                peak["current"] += 1
                peak["value"] = max(peak["value"], peak["current"])
            time.sleep(0.05)
            with lock:
                peak["current"] -= 1
            return response("ok")

        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )

        monkeypatch.setattr(translator, "_glossary_mode", lambda: "deferred")
        monkeypatch.setattr(translator, "_translation_concurrency", lambda: 4)
        monkeypatch.setattr(translator, "_build_rate_limiter", lambda concurrency: None)

        chunks = [(f"c{i}", f"Text {i}") for i in range(8)]
        process_translations(client, chunks, {}, "fast", "EN", "FA", paths)
        assert peak["value"] > 1, f"only {peak['value']} chunk(s) in flight"
    finally:
        import shutil
        shutil.rmtree(Path(paths["job_dir"]), ignore_errors=True)


def test_glossary_mode_inline_forces_sequential(monkeypatch, tmp_path):
    """inline propagation is only possible when nothing else is in flight."""
    from app.core.paths import ensure_temp_structure
    from app.translation import translator
    from app.translation.translator import process_translations

    paths = ensure_temp_structure("inline_probe")
    try:
        Path(paths["chunks_file"]).write_text(
            json.dumps({"chunks": [], "chapter_map": {}}), encoding="utf-8"
        )
        Path(paths["job_dir"], "glossary.json").write_text(
            json.dumps({"auto_extract": True, "terms": []}), encoding="utf-8"
        )

        lock = threading.Lock()
        peak = {"value": 0, "current": 0}

        def response(content):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )

        def create(**kwargs):
            if kwargs["messages"][0]["content"].startswith("Extract a concise book glossary"):
                return response(json.dumps({"terms": []}))
            with lock:
                peak["current"] += 1
                peak["value"] = max(peak["value"], peak["current"])
            time.sleep(0.02)
            with lock:
                peak["current"] -= 1
            return response("ok")

        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )

        monkeypatch.setattr(translator, "_glossary_mode", lambda: "inline")
        monkeypatch.setattr(translator, "_translation_concurrency", lambda: 4)
        monkeypatch.setattr(translator, "_build_rate_limiter", lambda concurrency: None)

        chunks = [(f"c{i}", f"Text {i}") for i in range(4)]
        process_translations(client, chunks, {}, "fast", "EN", "FA", paths)
        assert peak["value"] == 1, (
            f"glossary_mode=inline must be sequential, saw {peak['value']} in flight"
        )
    finally:
        import shutil
        shutil.rmtree(Path(paths["job_dir"]), ignore_errors=True)


def test_rate_limiter_halves_on_throttle_and_recovers():
    from app.core.rate_limit import AdaptiveRateLimiter

    limiter = AdaptiveRateLimiter(max_requests_per_minute=60, min_requests_per_minute=4)
    assert limiter.current_rpm == 60

    limiter.report_throttled()
    assert limiter.current_rpm == 30

    for _ in range(10):
        limiter.report_throttled()
    assert limiter.current_rpm >= 4, "must floor instead of collapsing to zero"

    for _ in range(100):
        limiter.report_success()
    assert limiter.current_rpm == 60, "must recover to the configured maximum"


def test_rate_limiter_honours_retry_after():
    from app.core.rate_limit import AdaptiveRateLimiter

    limiter = AdaptiveRateLimiter(max_requests_per_minute=60)
    limiter.report_throttled(retry_after=3.0)
    remaining = limiter.stats()["cooldown_remaining"]
    assert 2.5 <= remaining <= 3.1, remaining


def test_rate_limiter_paces_instead_of_bursting():
    from app.core.rate_limit import AdaptiveRateLimiter

    limiter = AdaptiveRateLimiter(max_requests_per_minute=600, min_requests_per_minute=10)
    marks = []
    for _ in range(4):
        limiter.acquire()
        marks.append(time.monotonic())
    spread = marks[-1] - marks[0]
    assert spread > 0.05, f"4 requests went out in {spread * 1000:.0f}ms; expected pacing"


def test_rate_limiter_acquire_respects_stop():
    from app.core.rate_limit import AdaptiveRateLimiter

    limiter = AdaptiveRateLimiter(max_requests_per_minute=1)
    limiter.acquire()
    stop = threading.Event()
    stop.set()
    started = time.monotonic()
    acquired = limiter.acquire(stop)
    assert acquired is False
    assert time.monotonic() - started < 0.2

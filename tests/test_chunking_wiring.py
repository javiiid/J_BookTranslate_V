"""Integration tests for the chunking wiring.

The unit tests in ``test_semantic_chunker.py`` cover the chunker on its own. These
cover the parts that only break when it is connected:

  * the flag actually gates the switch, and the default is off
  * the context reaches the model as a separate message, and the payload the
    model is asked to translate is byte-identical with and without it
  * a book survives build -> translate -> save with its markup intact
  * the build/save split agrees, which is the invariant the old
    ``max_chunk_size`` mismatch violated
  * context is persisted, so a resumed job is not translated blind
"""
import json
import sys
import zipfile
from pathlib import Path

import pytest

from app.core.config import get_chunking_config
from app.pipeline.epub_handler import EPUBHandler, _split_for_build
from app.translation import translator as translator_module
from app.translation.translator import translate_chunk


CHAPTER = (
    "<h1>The Cartographer</h1>"
    + "".join(
        f"<p>Paragraph {n} of the chapter, long enough to stand alone. "
        f"It continues for a little while longer.</p>"
        for n in range(6)
    )
)


@pytest.fixture
def semantic_on(monkeypatch):
    """Turn semantic chunking on for the duration of a test."""
    from app.core import config as config_module

    real = config_module.get_chunking_config

    def fake():
        settings = real()
        settings["semantic_chunking"] = True
        settings["chunk_max_tokens"] = 120
        settings["chunk_context_window"] = 2
        return settings

    monkeypatch.setattr(config_module, "get_chunking_config", fake)
    monkeypatch.setattr(
        "app.pipeline.epub_handler._chunk_settings",
        lambda: fake(),
    )
    return fake


@pytest.fixture
def epub(tmp_path):
    path = tmp_path / "book.epub"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("OEBPS/ch1.xhtml", CHAPTER)
    return path


class _Recorder:
    """A client that records the messages it was called with."""

    def __init__(self, reply="TR"):
        self.calls = []
        self.reply = reply
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = type("M", (), {"content": self.reply})()
        choice = type("C", (), {"message": message})()
        return type("R", (), {"choices": [choice]})()


# ============================================================
# The flag
# ============================================================

class TestFlag:

    def test_default_is_off(self):
        # The *code* default, not the value in config.yaml. Those are different
        # questions: the constant is what a fresh install gets, and a user is
        # entitled to turn the flag on in their own config. Asserting the live
        # value here made this test fail the moment anyone enabled it, which
        # trains people to ignore it.
        #
        # Why the default is off at all: chunks are identified by position and a
        # saved translation is keyed by that id, so switching chunkers mid-project
        # mixes two segmentations. See config.py.
        from app.core import config as config_module

        assert config_module.SEMANTIC_CHUNKING_DEFAULT is False

    def test_the_config_default_survives_a_nonsense_value(self, monkeypatch):
        from app.core import config as config_module

        monkeypatch.setattr(
            config_module, "get_translation_config", lambda: {"semantic_chunking": "maybe"}
        )
        # "maybe" is not a yes, so the code default stands rather than enabling a
        # chunker by typo.
        assert config_module.get_chunking_config()["semantic_chunking"] is False

    def test_reads_the_four_settings(self):
        settings = get_chunking_config()
        for key in (
            "semantic_chunking",
            "chunk_max_tokens",
            "chunk_context_window",
        ):
            assert key in settings

    def test_off_uses_the_old_splitter(self):
        pieces, contexts = _split_for_build(CHAPTER, 10000)
        assert contexts == {}
        # The old splitter's signature: one chunk for a chapter this size.
        assert len(pieces) == 1

    def test_on_produces_several_chunks_with_context(self, semantic_on):
        pieces, contexts = _split_for_build(CHAPTER, 10000)
        assert len(pieces) > 1
        assert contexts
        # The first piece has nothing before it.
        assert 0 not in contexts

    def test_context_is_plain_text(self, semantic_on):
        _, contexts = _split_for_build(CHAPTER, 10000)
        for text in contexts.values():
            assert "<" not in text
            assert text == text.strip()

    def test_a_nonsense_value_falls_back(self, monkeypatch):
        from app.core import config as config_module

        monkeypatch.setattr(
            config_module,
            "get_translation_config",
            lambda: {
                "semantic_chunking": "perhaps",
                "chunk_max_tokens": "not a number",
                "chunk_context_window": -5,
            },
        )
        settings = config_module.get_chunking_config()
        # "perhaps" is not a yes, and a bad integer must not reach the chunker.
        assert settings["semantic_chunking"] is False
        assert settings["chunk_max_tokens"] == config_module.CHUNK_MAX_TOKENS_DEFAULT
        assert settings["chunk_context_window"] == 0


# ============================================================
# Context reaching the model
# ============================================================

class TestContextReachesTheModel:

    def test_no_context_sends_two_messages(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            translator_module, "load_snapshot", lambda paths: {}, raising=False
        )
        client = _Recorder()
        translate_chunk(client=client, text="<p>Hello.</p>", chunk_id="c1")
        roles = [m["role"] for m in client.calls[0]["messages"]]
        assert roles == ["system", "user"]
        assert client.calls[0]["messages"][-1]["content"] == "<p>Hello.</p>"

    def test_context_adds_messages_and_keeps_the_payload_last(self, monkeypatch):
        client = _Recorder()
        translate_chunk(
            client=client,
            text="<p>She left.</p>",
            chunk_id="c2",
            context_before="He had already gone.",
        )
        messages = client.calls[0]["messages"]
        roles = [m["role"] for m in messages]
        assert roles == ["system", "user", "assistant", "user"]

        # The context is marked as not for translation...
        assert "Do not translate it" in messages[1]["content"]
        assert "He had already gone." in messages[1]["content"]
        # ...and the chunk is the last thing asked for, on its own.
        assert messages[-1]["content"] == "<p>She left.</p>"

    def test_the_payload_is_identical_either_way(self, monkeypatch):
        without = _Recorder()
        with_context = _Recorder()
        translate_chunk(client=without, text="<p>She left.</p>", chunk_id="c2")
        translate_chunk(
            client=with_context,
            text="<p>She left.</p>",
            chunk_id="c2",
            context_before="He had already gone.",
        )
        # What the model is asked to translate must not depend on whether context
        # was supplied, or the stored translation would not map to the chunk.
        assert without.calls[0]["messages"][-1]["content"] == (
            with_context.calls[0]["messages"][-1]["content"]
        )

    def test_still_exactly_one_request(self, monkeypatch):
        client = _Recorder()
        translate_chunk(
            client=client,
            text="<p>x</p>",
            chunk_id="c1",
            context_before="y",
        )
        # Context must not cost an extra round trip.
        assert len(client.calls) == 1

    def test_blank_context_is_ignored(self, monkeypatch):
        client = _Recorder()
        translate_chunk(
            client=client, text="<p>x</p>", chunk_id="c1", context_before="   "
        )
        assert [m["role"] for m in client.calls[0]["messages"]] == ["system", "user"]


# ============================================================
# Build and save
# ============================================================

class TestBuildAndSave:

    def test_build_returns_three_values(self, epub, semantic_on):
        chunks, chapter_map, contexts = EPUBHandler.build_chunks(epub)
        assert chunks and chapter_map
        assert isinstance(contexts, dict)

    def test_contexts_are_keyed_by_chunk_id(self, epub, semantic_on):
        chunks, _, contexts = EPUBHandler.build_chunks(epub)
        known = {chunk_id for chunk_id, _ in chunks}
        assert set(contexts) <= known

    def test_chapter_map_covers_every_chunk(self, epub, semantic_on):
        chunks, chapter_map, _ = EPUBHandler.build_chunks(epub)
        assert set(chapter_map) == {chunk_id for chunk_id, _ in chunks}

    def test_the_build_split_is_lossless(self, epub, semantic_on):
        chunks, _, _ = EPUBHandler.build_chunks(epub)
        with zipfile.ZipFile(epub) as archive:
            source = archive.read("OEBPS/ch1.xhtml").decode("utf-8")
        assert "".join(text for _, text in chunks) == source

    def test_the_save_split_agrees_with_the_build(self, epub, semantic_on, tmp_path):
        """The invariant the old max_chunk_size mismatch broke.

        Saving re-splits the original file and overwrites by position, so the two
        splits must produce the same pieces. Previously the build honoured its
        ``max_chunk_size`` argument and the save silently used the module default,
        so any other value put every translation after the first divergence into
        the wrong paragraph.
        """
        for size in (200, 5000, 10000):
            chunks, chapter_map, _ = EPUBHandler.build_chunks(epub, max_chunk_size=size)
            rebuilt, _ = _split_for_build(CHAPTER, size)
            assert [text for _, text in chunks] == rebuilt, size

    def test_a_full_round_trip_keeps_the_markup(self, epub, semantic_on, tmp_path):
        chunks, chapter_map, _ = EPUBHandler.build_chunks(epub)
        # Translate each chunk to a marked version of itself, so a misplaced
        # translation is visible in the output.
        translations = {
            chunk_id: text.replace("Paragraph", "TR-Paragraph")
            for chunk_id, text in chunks
        }
        out = tmp_path / "out.epub"
        EPUBHandler.save_translated_epub(
            epub, out, translations, chapter_map, max_chunk_size=10000
        )
        with zipfile.ZipFile(out) as archive:
            result = archive.read("OEBPS/ch1.xhtml").decode("utf-8")

        # Every paragraph is translated exactly once, and nothing else changed.
        assert result.count("TR-Paragraph") == 6
        assert "Paragraph" not in result.replace("TR-Paragraph", "")
        assert result.startswith("<h1>")
        assert result.count("<p>") == 6
        assert result.count("</p>") == 6

    def test_an_untranslated_chunk_is_left_alone(self, epub, semantic_on, tmp_path):
        chunks, chapter_map, _ = EPUBHandler.build_chunks(epub)
        # Pick a chunk that actually contains a paragraph. The first chunk is the
        # <h1>, so a blanket replace on it would silently do nothing and the test
        # would pass for the wrong reason.
        target = next(
            (chunk_id, text)
            for chunk_id, text in chunks
            if "Paragraph" in text
        )
        partial = {target[0]: target[1].replace("Paragraph", "TR-Paragraph")}
        # How many paragraphs this one chunk covers, counted before translating.
        # The chunker packs to a token budget, so a chunk may hold more than one
        # paragraph; asserting "one" would be asserting the fixture, not the code.
        expected = target[1].count("<p>Paragraph")

        out = tmp_path / "partial.epub"
        EPUBHandler.save_translated_epub(
            epub, out, partial, chapter_map, max_chunk_size=10000
        )
        with zipfile.ZipFile(out) as archive:
            result = archive.read("OEBPS/ch1.xhtml").decode("utf-8")

        assert result.count("<p>TR-Paragraph") == expected
        # Counted at the tag, because "TR-Paragraph" contains "Paragraph" and a
        # bare count would double-report.
        assert result.count("<p>Paragraph") == 6 - expected
        # The title chunk was not translated, so it is still the original.
        assert "<h1>The Cartographer</h1>" in result


class TestPersistedContext:

    @staticmethod
    def _read(paths):
        # Read the file the engine writes, rather than a loader. There is no
        # `load_state` -- the module exposes `load_job_state`, which returns a
        # different shape -- and the point here is what is on disk, since that is
        # what a resumed run reads.
        return json.loads(paths["chunks_file"].read_text(encoding="utf-8"))

    def test_context_is_written_with_the_chunks(self, tmp_path, semantic_on):
        from app.jobs.state import save_chunks

        paths = {
            "job_dir": tmp_path,
            "chunks_file": tmp_path / "chunks.json",
        }
        save_chunks(
            paths,
            [("chunk-0", "<p>a</p>"), ("chunk-1", "<p>b</p>")],
            {"chunk-0": ("ch.xhtml", 0), "chunk-1": ("ch.xhtml", 1)},
            {"chunk-1": "the first paragraph"},
        )
        state = self._read(paths)
        assert state["chunk_contexts"] == {"chunk-1": "the first paragraph"}
        # The chunks themselves are untouched by the addition.
        assert [text for _, text in state["chunks"]] == ["<p>a</p>", "<p>b</p>"]

    def test_no_context_key_when_there_is_none(self, tmp_path):
        from app.jobs.state import save_chunks

        paths = {
            "job_dir": tmp_path,
            "chunks_file": tmp_path / "chunks.json",
        }
        save_chunks(
            paths,
            [("chunk-0", "<p>a</p>")],
            {"chunk-0": ("ch.xhtml", 0)},
            {},
        )
        state = self._read(paths)
        # An empty map is not written at all, so a job with no context is
        # indistinguishable on disk from one saved before the feature existed.
        assert "chunk_contexts" not in state

    def test_context_for_an_unknown_chunk_is_dropped(self, tmp_path):
        from app.jobs.state import save_chunks

        paths = {
            "job_dir": tmp_path,
            "chunks_file": tmp_path / "chunks.json",
        }
        save_chunks(
            paths,
            [("chunk-0", "<p>a</p>")],
            {"chunk-0": ("ch.xhtml", 0)},
            {"chunk-0": "kept", "chunk-99": "orphan"},
        )
        state = self._read(paths)
        assert state["chunk_contexts"] == {"chunk-0": "kept"}

    def test_a_non_string_context_is_not_written(self, tmp_path):
        from app.jobs.state import save_chunks

        paths = {
            "job_dir": tmp_path,
            "chunks_file": tmp_path / "chunks.json",
        }
        save_chunks(
            paths,
            [("chunk-0", "<p>a</p>")],
            {"chunk-0": ("ch.xhtml", 0)},
            {"chunk-0": None},
        )
        assert "chunk_contexts" not in self._read(paths)

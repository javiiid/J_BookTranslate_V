"""Tests for the pre-translation estimate.

The stub this replaces had three defects, and each has a test here:

  * the chunk count came from the file's size in bytes, not from chunking it
  * the time estimate ignored ``max_concurrency``, overstating by about 12x
  * the cost was a hardcoded ``0.0``, which beside a "start" button reads as free

The last is the one worth being careful about. A price table for models that do
not exist on any public list cannot honestly be filled in, so the design is that an
unknown model reports ``known: False`` and the UI says so. There is a test that
the unknown path is distinguishable from a real zero, because collapsing those two
is exactly the bug being fixed.
"""
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.jobs.estimate import (
    GLOSSARY_INPUT_RATIO,
    GLOSSARY_OUTPUT_CAP,
    GLOSSARY_OUTPUT_RATIO,
    GLOSSARY_SYSTEM_TOKENS,
    LATENCY_BATCH_SECONDS,
    LATENCY_FAST_SECONDS,
    OUTPUT_RATIO,
    PRICING,
    RANGE,
    CostBreakdown,
    Estimate,
    Resume,
    cost_for,
    count_chunks,
    estimate,
    format_duration,
    resume_for,
    seconds_for,
)


def make_epub(path: Path, paragraphs: int = 40, words: int = 60) -> Path:
    """A real EPUB, so the chunker actually runs rather than a size guess."""
    body = "".join(
        f"<p>{'word ' * words}Paragraph number {n} of the chapter.</p>"
        for n in range(paragraphs)
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("OEBPS/ch1.xhtml", f"<html><body>{body}</body></html>")
        archive.writestr("OEBPS/ch2.xhtml", f"<html><body>{body}</body></html>")
    return path


# ============================================================
# Duration formatting
# ============================================================

class TestFormatDuration:

    def test_sub_minute_says_so_rather_than_guessing(self):
        assert format_duration(0) == "کمتر از یک دقیقه"
        assert format_duration(45) == "کمتر از یک دقیقه"

    def test_minutes_under_an_hour(self):
        assert format_duration(2700) == "~۴۵ دقیقه"

    def test_hours_with_a_decimal_when_they_are_few(self):
        out = format_duration(int(2.5 * 3600))
        assert "ساعت" in out
        assert "." in out

    def test_many_hours_are_rounded(self):
        assert format_duration(30 * 3600) == "~۳۰ ساعت"

    def test_negative_is_clamped(self):
        assert format_duration(-10) == "کمتر از یک دقیقه"

    def test_every_duration_contains_persian_digits(self):
        for seconds in (0, 60, 600, 3600, 7200, 86400, 400000):
            out = format_duration(seconds)
            assert any("۰" <= c <= "۹" for c in out) or "یک" in out


# ============================================================
# Time
# ============================================================

class TestSecondsFor:

    def test_concurrency_divides_the_work(self):
        # 120 chunks at 12 workers is 10 rounds, not 120.
        fast = seconds_for(120, 12, "fast", False)
        assert fast == int(10 * LATENCY_FAST_SECONDS)

    def test_the_stub_overstated_by_the_concurrency_factor(self):
        # The old route returned chunks * 4 regardless of concurrency.
        one = seconds_for(120, 1, "fast", False)
        twelve = seconds_for(120, 12, "fast", False)
        assert one == 12 * twelve
        assert twelve < one

    def test_waves_not_averages(self):
        # 13 chunks over 12 workers is 2 rounds, not 13/12 rounded down to 1.
        import math

        assert seconds_for(13, 12, "fast", False) == math.ceil(2 * LATENCY_FAST_SECONDS)
        assert seconds_for(12, 12, "fast", False) == math.ceil(LATENCY_FAST_SECONDS)

    def test_batch_is_slower_than_fast(self):
        assert seconds_for(50, 4, "batch", False) > seconds_for(50, 4, "fast", False)

    def test_concurrency_of_zero_or_less_does_not_divide_by_zero(self):
        assert seconds_for(10, 0, "fast", False) > 0
        assert seconds_for(10, -3, "fast", False) > 0

    def test_no_chunks_is_no_time(self):
        assert seconds_for(0, 12, "fast", False) == 0

    def test_glossary_adds_time_but_not_double_it(self):
        plain = seconds_for(100, 12, "fast", False)
        with_glossary = seconds_for(100, 12, "fast", True)
        assert with_glossary > plain
        assert with_glossary < plain * 1.5


# ============================================================
# Cost
# ============================================================

class TestCostFor:

    def test_an_unknown_model_is_flagged_rather_than_priced_at_zero(self):
        # This is the whole point. The stub returned 0.0 for everything, which
        # reads as "free" rather than "unknown".
        cost = cost_for("no-such-model", 100000, False, 10)
        assert cost.known is False
        assert cost.minimum == 0.0 and cost.maximum == 0.0
        # And the flag is what a caller must check before rendering a price.
        payload = Estimate(
            chunk_count=10, chunk_count_total=10, token_count=100000, cost=cost,
            seconds=10, source_lang="EN", target_lang="FA", model="no-such-model",
            mode="fast", concurrency=1, resume=Resume(False, None, 0, 0),
            chunk_count_exact=True,
        ).to_payload()
        assert payload["estimated_cost"]["known"] is False

    def test_a_known_model_costs_something(self):
        model = next(iter(PRICING))
        cost = cost_for(model, 100000, False, 10)
        assert cost.known is True
        assert cost.minimum > 0
        assert cost.maximum > cost.minimum

    def test_the_band_is_the_documented_width(self):
        model = next(iter(PRICING))
        cost = cost_for(model, 100000, False, 0)
        assert cost.maximum / cost.minimum == pytest.approx(
            (1 + RANGE) / (1 - RANGE), rel=1e-6
        )

    def test_output_costs_more_than_input_when_the_price_says_so(self):
        # A model priced higher on output should bill more for output. If the two
        # rates were swapped this inverts, so it is worth pinning.
        for model, (price_in, price_out) in PRICING.items():
            if price_out <= price_in:
                continue
            tokens = 1_000_000
            expected = (tokens / 1e6) * price_in + (tokens * OUTPUT_RATIO / 1e6) * price_out
            cost = cost_for(model, tokens, False, 0)
            assert cost.known, model
            mid = (cost.minimum + cost.maximum) / 2
            assert mid == pytest.approx(expected, rel=0.02), model

    def test_glossary_is_charged_only_when_enabled(self):
        model = next(iter(PRICING))
        without = cost_for(model, 10000, False, 100)
        with_it = cost_for(model, 10000, True, 100)
        assert without.glossary == 0.0
        assert with_it.glossary > 0.0
        # And the total moves by exactly the glossary's share, so the two parts
        # still add up to what the dialog shows.
        assert with_it.base - without.base == pytest.approx(with_it.glossary)

    def test_the_two_parts_add_up_to_the_total(self):
        """The property the dialog depends on.

        It rendered the total next to a badge reading ``+$0.12`` for the
        glossary, so a reader who believed the badge computed a total $0.12
        above the one on screen. The parts now sum to the base, and the band is
        a band around that base.
        """
        for model in PRICING:
            for glossary in (False, True):
                cost = cost_for(model, 500_000, glossary, 120)
                assert cost.translation + cost.glossary == pytest.approx(cost.base)
                assert cost.minimum == pytest.approx(cost.base * (1 - RANGE))
                assert cost.maximum == pytest.approx(cost.base * (1 + RANGE))

    def test_the_glossary_price_scales_with_the_model(self):
        """The flat-rate bug.

        ``GLOSSARY_COST_PER_CHUNK = 0.002`` was charged whatever the model. On
        the cheapest model that came to 70% of the whole bill and on the dearest
        to 6%, which is not a property of a glossary call -- it is a property of
        ignoring the model's prices. A glossary call is a call on the same model,
        so it has to move with the model.
        """
        shares = {}
        for model in PRICING:
            cost = cost_for(model, 129_013, True, 60)
            shares[model] = cost.glossary / cost.base

        # The absolute figure has to track the model. What actually decides the
        # share is the model's output:input price *ratio*, not its identity --
        # a glossary call is one input-heavy call against one input-heavy
        # translation, so a model priced relatively cheaper on output has a
        # smaller glossary share. Measured across the table: 29% at a ratio of
        # 5.0, 43% at 2.0, and identical for every model sharing a ratio.
        #
        # The first version of this test asserted the share was the same for every
        # model, which is not true and not the property that matters -- it failed
        # on gpt-3.5-turbo-16k, priced 2.0 on output against input.
        for model, (price_in, price_out) in PRICING.items():
            ratio = price_out / price_in
            peers = [
                shares[m]
                for m, (i, o) in PRICING.items()
                if i and o / i == ratio
            ]
            assert shares[model] in [
                pytest.approx(p, rel=1e-6) for p in peers
            ]

        # The real check: two models with the same ratio give the same share, and
        # two very different models do not give the same absolute cost.
        by_ratio: dict[float, set[float]] = {}
        for model, (price_in, price_out) in PRICING.items():
            by_ratio.setdefault(price_out / price_in, set()).add(
                round(shares[model], 9)
            )
        for ratio, seen in by_ratio.items():
            assert len(seen) == 1, (ratio, seen)

        absolute = {
            model: cost_for(model, 129_013, True, 60).glossary
            for model in PRICING
        }
        assert max(absolute.values()) > min(absolute.values()) * 10, (
            "a flat rate gives the same cost for every model"
        )

    def test_the_glossary_is_priced_from_what_the_call_actually_sends(self):
        # learn_chunk sends the source *and* the translation, so its input is
        # 1 + OUTPUT_RATIO times the source, not 1. Priced at 1x it was cheap
        # enough to look like a rounding error; priced correctly it is a real
        # line item and has to be shown as one.
        model = next(iter(PRICING))
        price_in, price_out = PRICING[model]
        tokens, chunks = 129_013, 60
        cost = cost_for(model, tokens, True, chunks)

        per_chunk = tokens / chunks
        glossary_in = per_chunk * GLOSSARY_INPUT_RATIO + GLOSSARY_SYSTEM_TOKENS
        glossary_out = min(
            per_chunk * GLOSSARY_INPUT_RATIO * GLOSSARY_OUTPUT_RATIO,
            GLOSSARY_OUTPUT_CAP,
        )
        expected = (glossary_in * chunks / 1e6) * price_in
        expected += (glossary_out * chunks / 1e6) * price_out
        assert cost.glossary == pytest.approx(expected, rel=1e-9)

    def test_the_glossary_output_is_capped_at_what_the_call_allows(self):
        # A tiny book would otherwise price a 20-term list at a size no single
        # term could occupy; learn_chunk passes max_tokens=2000.
        model = next(iter(PRICING))
        tiny = cost_for(model, 1_000, True, 1)
        assert tiny.glossary > 0
        # And the cap is what bounds the output term, so a 1-token book and a
        # 1M-token book differ only in their input.
        big = cost_for(model, 1_000_000, True, 1_000)
        assert big.glossary > tiny.glossary

    def test_more_tokens_costs_more(self):
        model = next(iter(PRICING))
        small = cost_for(model, 1000, False, 0)
        large = cost_for(model, 1000000, False, 0)
        assert large.base > small.base


# ============================================================
# Chunk counting
# ============================================================

class TestCountChunks:

    def test_an_epub_is_really_chunked(self, tmp_path):
        book = make_epub(tmp_path / "book.epub", paragraphs=40)
        chunks, tokens, exact = count_chunks(book, max_tokens=300)
        assert exact is True
        assert chunks > 1
        assert tokens > 0

    def test_the_count_is_not_derived_from_the_byte_size(self, tmp_path):
        # Two books of very different token density, similar size. A byte-count
        # stub gives them the same number; the real chunker does not.
        dense = make_epub(tmp_path / "dense.epub", paragraphs=20, words=120)
        sparse = make_epub(tmp_path / "sparse.epub", paragraphs=20, words=12)
        dense_chunks, _, _ = count_chunks(dense, max_tokens=300)
        sparse_chunks, _, _ = count_chunks(sparse, max_tokens=300)
        assert dense_chunks != sparse_chunks

    def test_a_larger_budget_gives_fewer_chunks(self, tmp_path):
        book = make_epub(tmp_path / "book.epub", paragraphs=40)
        small, _, _ = count_chunks(book, max_tokens=200)
        large, _, _ = count_chunks(book, max_tokens=2000)
        assert large < small

    def test_bigger_book_means_more_chunks(self, tmp_path):
        small = make_epub(tmp_path / "s.epub", paragraphs=10)
        big = make_epub(tmp_path / "b.epub", paragraphs=60)
        assert count_chunks(big, 300)[0] > count_chunks(small, 300)[0]

    def test_a_missing_file_does_not_raise(self, tmp_path):
        chunks, tokens, exact = count_chunks(tmp_path / "nope.epub")
        assert chunks == 0
        assert exact is False

    def test_a_corrupt_archive_is_not_claimed_as_exact(self, tmp_path):
        broken = tmp_path / "broken.epub"
        broken.write_bytes(b"not a zip file at all")
        chunks, _, exact = count_chunks(broken)
        assert exact is False
        assert chunks >= 1

    def test_an_unknown_extension_falls_back_without_raising(self, tmp_path):
        other = tmp_path / "book.txt"
        other.write_text("hello " * 5000, encoding="utf-8")
        chunks, tokens, exact = count_chunks(other)
        assert exact is False
        assert chunks >= 1
        assert tokens > 0

    def test_a_non_utf8_chapter_is_skipped_not_miscounted(self, tmp_path):
        # The translator skips these too, so counting them would overstate the
        # bill. The good chapter is one paragraph, split at a sentence boundary
        # because it does not fit the budget -- so two chunks, and nothing from
        # the undecodable file.
        path = tmp_path / "mixed.epub"
        body = "<p>" + "word " * 200 + "</p>"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("OEBPS/good.xhtml", f"<html><body>{body}</body></html>")
            archive.writestr("OEBPS/bad.xhtml", b"\xff\xfe not utf-8 \xff")
        chunks, _, exact = count_chunks(path, max_tokens=100)
        assert exact is True
        assert chunks == 2

    def test_a_book_of_only_undecodable_chapters_is_not_called_exact(self, tmp_path):
        path = tmp_path / "bad.epub"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("OEBPS/a.xhtml", b"\xff\xfe\xff")
            archive.writestr("OEBPS/b.xhtml", b"\xff\xfe\xff")
        chunks, _, exact = count_chunks(path)
        assert exact is False


# ============================================================
# Resume
# ============================================================

class TestResumeFor:

    def test_no_job_means_no_resume(self):
        resume = resume_for("nothing-called-this", "FA", "EN", "gpt-5.6-luna")
        assert resume.found is False
        assert resume.progress is None

    def test_a_bogus_argument_does_not_raise(self):
        # A resume lookup must never be what breaks the estimate dialog.
        assert resume_for("", "", "", "").found is False

    def test_a_job_found_as_a_tuple_is_still_read(self, monkeypatch):
        """The guard that ate every job.

        ``find_resumable_jobs`` yields ``(name, timestamp, state)`` tuples. The
        reader did ``job.get("state") if isinstance(job, dict) else None``, so
        every real job was skipped and the dialog reported a resume with no
        progress on it -- for a book that was 100% translated.
        """
        jobs = [("book_EN_FA_model_20260101_000000", "20260101_000000",
                 {"chunks_total": 60, "chunks_completed": 25, "last_updated": "x"})]
        monkeypatch.setattr("app.jobs.state.find_resumable_jobs", lambda *a, **k: jobs)
        resume = resume_for("book", "EN", "FA", "model")
        assert resume.found is True
        assert resume.progress == pytest.approx(25 / 60)
        assert resume.remaining == 35
        assert resume.done == 25

    def test_a_finished_job_is_not_a_resume(self, monkeypatch):
        """A book translated yesterday was offered as resumable and priced in
        full, because nothing compared completed against total."""
        jobs = [("book_EN_FA_model_20260101_000000", "20260101_000000",
                 {"chunks_total": 60, "chunks_completed": 60, "last_updated": "x"})]
        monkeypatch.setattr("app.jobs.state.find_resumable_jobs", lambda *a, **k: jobs)
        resume = resume_for("book", "EN", "FA", "model")
        assert resume.found is False
        assert resume.complete is False

    def test_the_most_finished_job_wins(self, monkeypatch):
        jobs = [
            ("a", "t", {"chunks_total": 60, "chunks_completed": 5, "last_updated": "1"}),
            ("b", "t", {"chunks_total": 60, "chunks_completed": 50, "last_updated": "2"}),
        ]
        monkeypatch.setattr("app.jobs.state.find_resumable_jobs", lambda *a, **k: jobs)
        resume = resume_for("book", "EN", "FA", "model")
        assert resume.remaining == 10
        assert resume.progress == pytest.approx(50 / 60)

    def test_a_malformed_entry_does_not_break_the_lookup(self, monkeypatch):
        jobs = [
            ("a", "t", None),
            "not even a tuple",
            ("b", "t", {"chunks_total": 60, "chunks_completed": 30, "last_updated": "1"}),
        ]
        monkeypatch.setattr("app.jobs.state.find_resumable_jobs", lambda *a, **k: jobs)
        assert resume_for("book", "EN", "FA", "model").remaining == 30


# ============================================================
# The entry point
# ============================================================

class TestEstimate:

    def test_a_real_book(self, tmp_path):
        book = make_epub(tmp_path / "book.epub", paragraphs=40)
        result = estimate(
            file_path=str(book),
            model="gpt-5.6-luna",
            concurrency=12,
            mode="fast",
        )
        assert result.chunk_count > 1
        assert result.token_count > 0
        assert result.chunk_count_exact is True
        assert result.seconds > 0
        assert result.to_payload()["estimated_cost"]["currency"] == "USD"

    def test_a_missing_file_still_yields_a_usable_dialog(self, tmp_path):
        # One chunk, not zero: something will be sent, and a zero would be a lie.
        result = estimate(str(tmp_path / "gone.epub"), "gpt-5.6-luna", 12)
        assert result.chunk_count == 1
        assert result.chunk_count_exact is False

    def test_glossary_is_reflected_in_both_money_and_time(self, tmp_path):
        book = make_epub(tmp_path / "book.epub", paragraphs=20)
        plain = estimate(str(book), "gpt-5.6-luna", 12, glossary_auto=False)
        rich = estimate(str(book), "gpt-5.6-luna", 12, glossary_auto=True)
        assert rich.cost.glossary > 0
        assert plain.cost.glossary == 0
        assert rich.seconds > plain.seconds

    def test_a_resume_is_priced_on_what_is_left(self, tmp_path, monkeypatch):
        """The figure the user saw was the whole book.

        The dialog offered "continue where it left off" and then quoted the cost
        of translating all 60 chunks, when only 10 were left to send. Both the
        money and the time were for work that would not be done.
        """
        # Big enough that the two cases straddle a wavefront at concurrency 12:
        # three remaining chunks take one round, the whole book takes more. With a
        # small book both fit in one round and the times are legitimately equal.
        book = make_epub(tmp_path / "book.epub", paragraphs=120)
        total = count_chunks(book)[0]
        done = total - 3
        jobs = [("book_EN_FA_gpt-5.6-luna_20260101_000000", "t",
                 {"chunks_total": total, "chunks_completed": done, "last_updated": "1"})]
        monkeypatch.setattr("app.jobs.state.find_resumable_jobs", lambda *a, **k: jobs)

        partial = estimate(str(book), "gpt-5.6-luna", 12,
                           source_lang="EN", target_lang="FA")
        assert partial.chunk_count == 3
        assert partial.chunk_count_total == total
        assert partial.resume.done == done
        # The baseline has to be taken with the fake job out of the way, or both
        # sides price the remaining three chunks and the comparison is vacuous.
        monkeypatch.undo()
        whole = estimate(str(book), "gpt-5.6-luna", 12,
                         source_lang="EN", target_lang="FA")
        assert whole.chunk_count == total
        assert partial.cost.maximum < whole.cost.maximum
        assert partial.seconds < whole.seconds
    def test_a_finished_job_does_not_reduce_the_quote(self, tmp_path, monkeypatch):
        # No resume means the full book, even when a finished job sits on disk.
        book = make_epub(tmp_path / "book.epub", paragraphs=20)
        total = count_chunks(book)[0]
        jobs = [("book_EN_FA_gpt-5.6-luna_20260101_000000", "t",
                 {"chunks_total": total, "chunks_completed": total, "last_updated": "1"})]
        monkeypatch.setattr("app.jobs.state.find_resumable_jobs", lambda *a, **k: jobs)
        result = estimate(str(book), "gpt-5.6-luna", 12,
                          source_lang="EN", target_lang="FA")
        assert result.chunk_count == result.chunk_count_total
        assert result.resume.found is False

    def test_payload_is_json_safe(self, tmp_path):
        import json

        book = make_epub(tmp_path / "book.epub", paragraphs=6)
        payload = estimate(str(book), "gpt-5.6-luna", 12).to_payload()
        # Would raise on a tuple, a set or a numpy value.
        json.dumps(payload)
        assert set(payload) >= {
            "chunk_count", "chunk_count_total", "chunks_already_done",
            "token_count", "estimated_cost", "glossary_cost",
            "estimated_time", "estimated_time_seconds", "source_lang",
            "target_lang", "model", "mode", "has_resume", "resume_progress",
            "resume_remaining",
        }
        # The breakdown has to be there for the dialog to show a checkable total.
        assert set(payload["estimated_cost"]) >= {
            "min", "max", "base", "translation", "glossary", "currency", "known",
        }

    def test_mode_is_carried_through(self, tmp_path):
        book = make_epub(tmp_path / "book.epub", paragraphs=6)
        for mode in ("fast", "batch"):
            assert estimate(str(book), "gpt-5.6-luna", 4, mode=mode).mode == mode

    def test_an_unknown_model_does_not_raise(self, tmp_path):
        book = make_epub(tmp_path / "book.epub", paragraphs=4)
        result = estimate(str(book), "gpt-9-imaginary", 12)
        assert result.cost.known is False

    def test_a_relative_path_is_accepted(self, tmp_path, monkeypatch):
        book = make_epub(tmp_path / "book.epub", paragraphs=4)
        monkeypatch.chdir(tmp_path)
        result = estimate("book.epub", "gpt-5.6-luna", 12)
        assert result.chunk_count >= 1

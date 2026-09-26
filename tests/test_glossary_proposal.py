"""Tests for explicit, review-before-use glossary proposals.

Automatic learning during a run is now off by default. Terminology comes from
a proposal the user reviews, and only approved terms are promoted into the live
glossary that gets snapshotted into the job. These tests cover the sampling,
the hallucination guard, the storage split between draft and approved, and the
promotion rules.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.glossary.proposal import (
    DEFAULT_SAMPLE_CHUNKS,
    _parse,
    key,
    merge_approved,
    propose_terms,
    propose_unapproved,
    sample_chunks,
)
from app.glossary.service import (
    get_glossary,
    get_proposal,
    save_glossary,
    save_proposal,
)


# --------------------------------------------------------------------------
# Sampling
# --------------------------------------------------------------------------

def test_sampling_spreads_across_the_book():
    chunks = [(f"c{i}", f"Body {i}") for i in range(300)]
    samples = sample_chunks(chunks, count=12, per_chunk_chars=100)
    assert len(samples) == 12
    assert "Body 0" in samples[0], "the opening must be sampled"
    assert "Body 299" in samples[-1], "the ending must be sampled"
    # Reading only the first twelve would miss the middle and the end.
    picked = {int(sample.split()[1]) for sample in samples}
    assert picked != set(range(12)), "must not just read the opening"
    assert max(picked) > 100, "must reach deep into the book"
    assert len(picked & set(range(0, 12, 2))) < 12


def test_sampling_handles_a_short_book():
    chunks = [(f"c{i}", f"Body {i}") for i in range(3)]
    assert len(sample_chunks(chunks, count=12)) == 3


def test_sampling_trims_long_chunks():
    chunks = [("c0", "word " * 5000)]
    samples = sample_chunks(chunks, count=1, per_chunk_chars=200)
    assert len(samples[0]) <= 210


def test_sampling_skips_empty_chunks():
    chunks = [("c0", "   "), ("c1", "<p></p>"), ("c2", "Real text here")]
    samples = sample_chunks(chunks, count=3)
    assert samples == ["Real text here"]


# --------------------------------------------------------------------------
# Parsing and the hallucination guard
# --------------------------------------------------------------------------

def test_parse_accepts_terms_present_in_the_text():
    corpus = "Ann met Robert in Bristol. The Dagger Society met again."
    content = json.dumps({"terms": [
        {"source_term": "Ann", "target_term": "آن", "kind": "person"},
        {"source_term": "Bristol", "target_term": "بریستول", "kind": "place"},
    ]})
    terms = _parse(content, corpus)
    assert [t["source_term"] for t in terms] == ["Ann", "Bristol"]
    assert all(t["origin"] == "proposed" for t in terms)


def test_parse_drops_terms_the_model_invented():
    """The guard that matters: a term absent from the text is discarded.

    An invented glossary poisons every chunk that contains the phrase, so this
    must be enforced server-side regardless of what the model claims.
    """
    corpus = "Ann met Robert in Bristol."
    content = json.dumps({"terms": [
        {"source_term": "Christopher Marlowe", "target_term": "مارلو", "kind": "person"},
        {"source_term": "Ann", "target_term": "آن", "kind": "person"},
    ]})
    terms = _parse(content, corpus)
    assert [t["source_term"] for t in terms] == ["Ann"]


def test_parse_normalises_kind_and_drops_duplicates():
    corpus = "Ann and Ann met Robert."
    content = json.dumps({"terms": [
        {"source_term": "Ann", "target_term": "آن", "kind": "nonsense-kind"},
        {"source_term": "ann", "target_term": "آن دیگر", "kind": "person"},
        {"source_term": "Robert", "target_term": "رابرت", "kind": "person"},
    ]})
    terms = _parse(content, corpus)
    keys = [key(t["source_term"]) for t in terms]
    assert len(keys) == len(set(keys)), "case variants must collapse"
    assert all(t["kind"] in {"person", "place", "organization", "term", "title"} for t in terms)


def test_parse_strips_code_fences():
    corpus = "Ann met Robert."
    fenced = "```json\n" + json.dumps({"terms": [
        {"source_term": "Ann", "target_term": "آن", "kind": "person"}]}) + "\n```"
    assert _parse(fenced, corpus)


def test_parse_rejects_malformed_responses():
    with pytest.raises(ValueError):
        _parse("", "text")
    with pytest.raises(ValueError):
        _parse("not json at all", "text")
    with pytest.raises(ValueError):
        _parse(json.dumps({"terms": "not a list"}), "text")


# --------------------------------------------------------------------------
# Promotion rules
# --------------------------------------------------------------------------

def test_merge_keeps_only_approved_terms():
    existing = [{"source_term": "Old", "target_term": "قدیمی"}]
    proposed = [
        {"source_term": "Ann", "target_term": "آن", "kind": "person"},
        {"source_term": "Robert", "target_term": "رابرت", "kind": "person"},
    ]
    merged = merge_approved(proposed, existing, {key("Ann")})
    terms = {key(t["source_term"]): t for t in merged}
    assert "old" in terms, "the existing glossary must survive"
    assert "ann" in terms, "the approved term must be promoted"
    assert "robert" not in terms, "an unapproved term must not be promoted"


def test_merge_lets_the_user_override_a_proposed_equivalent():
    existing = [{"source_term": "Ann", "target_term": "آن"}]
    proposed = [{"source_term": "Ann", "target_term": "آن (پیشنهاد مدل)"}]
    merged = merge_approved(proposed, existing, {key("Ann")})
    assert len(merged) == 1, "must update in place, not duplicate"
    assert merged[0]["target_term"] == "آن (پیشنهاد مدل)"


def test_merge_is_case_insensitive_on_approval():
    proposed = [{"source_term": "Dagger Society", "target_term": "جامعهٔ چاقو"}]
    merged = merge_approved(proposed, [], {key("dagger society")})
    assert len(merged) == 1


# --------------------------------------------------------------------------
# Drafts stay out of the live glossary
# --------------------------------------------------------------------------

def test_proposal_does_not_touch_the_live_glossary(db):
    book_id = _book(db)
    save_proposal(db, book_id, "EN", "FA", [
        {"source_term": "Ann", "target_term": "آن", "kind": "person", "notes": ""},
    ])
    # The draft exists...
    assert get_proposal(db, book_id, "EN", "FA")["terms"]
    # ...but the book still has no approved terminology.
    assert get_glossary(db, book_id, "EN", "FA")["terms"] == []


def test_approved_proposal_lands_in_the_live_glossary(db):
    book_id = _book(db)
    save_proposal(db, book_id, "EN", "FA", [
        {"source_term": "Ann", "target_term": "آن", "kind": "person", "notes": ""},
        {"source_term": "Robert", "target_term": "رابرت", "kind": "person", "notes": ""},
    ])
    proposal = get_proposal(db, book_id, "EN", "FA")
    current = get_glossary(db, book_id, "EN", "FA")
    merged = merge_approved(proposal["terms"], current["terms"], {key("Ann")})
    save_glossary(db, book_id, {
        "source_language": "EN", "target_language": "FA",
        "version": current["version"], "terms": merged,
    })
    approved = {key(t["source_term"]) for t in get_glossary(db, book_id, "EN", "FA")["terms"]}
    assert approved == {key("Ann")}


def test_preflight_and_postrun_drafts_are_separate(db):
    book_id = _book(db)
    save_proposal(db, book_id, "EN", "FA", [
        {"source_term": "First", "target_term": "اول", "kind": "term", "notes": ""},
    ], origin="preflight")
    save_proposal(db, book_id, "EN", "FA", [
        {"source_term": "Second", "target_term": "دوم", "kind": "term", "notes": ""},
    ], origin="postrun")
    assert get_proposal(db, book_id, "EN", "FA", "preflight")["terms"][0]["source_term"] == "First"
    assert get_proposal(db, book_id, "EN", "FA", "postrun")["terms"][0]["source_term"] == "Second"


def test_proposal_rejects_an_unknown_origin(db):
    book_id = _book(db)
    with pytest.raises(ValueError):
        save_proposal(db, book_id, "EN", "FA", [], origin="nonsense")


# --------------------------------------------------------------------------
# End to end with a fake provider
# --------------------------------------------------------------------------

def _fake_client(payload, calls=None):
    def create(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
        )
    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )


def test_propose_terms_makes_exactly_one_call():
    calls = []
    chunks = [(f"c{i}", f"Chapter {i}. Ann met Robert in Bristol.") for i in range(300)]
    client = _fake_client(json.dumps({"terms": [
        {"source_term": "Ann", "target_term": "آن", "kind": "person"},
    ]}), calls)
    terms = propose_terms(client, chunks, "model", "EN", "FA")
    assert len(calls) == 1, "a proposal must cost one call, not one per chunk"
    assert [t["source_term"] for t in terms] == ["Ann"]


def test_postrun_proposal_excludes_already_approved_terms():
    payload = json.dumps({"terms": [
        {"source_term": "Ann", "target_term": "آن", "kind": "person"},
        {"source_term": "Robert", "target_term": "رابرت", "kind": "person"},
    ]})
    chunks = [("c0", "Ann met Robert in Bristol.")]
    translations = {"c0": "آن در بریستول با رابرت دیدار کرد."}
    existing = [{"source_term": "Ann", "target_term": "آن"}]
    terms = propose_unapproved(
        _fake_client(payload), chunks, translations, "model", "EN", "FA",
        existing_terms=existing,
    )
    assert [t["source_term"] for t in terms] == ["Robert"]


def test_propose_uses_the_default_twelve_chunk_sample():
    assert DEFAULT_SAMPLE_CHUNKS == 12


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    from app.storage.database import Database
    return Database(tmp_path / "glossary-proposal.db")


def _book(database):
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).isoformat()
    return database.execute(
        "INSERT INTO library_books(title, created_at, updated_at) VALUES (?,?,?)",
        ("Test book", stamp, stamp),
    )

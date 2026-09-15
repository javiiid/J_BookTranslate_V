import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.glossary.automatic import learn_chunk, sync_book
from app.glossary.service import get_glossary, load_snapshot, save_glossary
from app.storage.database import Database
from app.translation.translator import process_translations


def paths_for(tmp_path, **snapshot):
    paths = {'job_dir': tmp_path, 'translations_file': tmp_path / 'translations.json'}
    (tmp_path / 'glossary.json').write_text(json.dumps({
        'source_language': 'EN', 'target_language': 'FA', 'terms': [],
        'auto_extract': True, **snapshot,
    }), encoding='utf-8')
    return paths


def response(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def candidate(source='Ann', target='آن'):
    return {'source_term': source, 'target_term': target, 'kind': 'person'}


def client_with_terms(terms):
    client = Mock()
    client.chat.completions.create.return_value = response(json.dumps({'terms': terms}))
    return client


def test_learns_only_real_terms_and_preserves_manual_equivalents(tmp_path):
    paths = paths_for(tmp_path, terms=[candidate('Bob', 'باب')])
    client = client_with_terms([
        candidate(), candidate('ANN', 'آن'), candidate('Ann', 'اختراعی'),
        candidate('Absent', 'آن'), candidate('Bob', 'بابی'),
        candidate('Annual', 'آن'), {'source_term': None, 'target_term': 'آن'},
    ])
    learn_chunk(client, paths, 'one', '<p>Ann and Bob</p>', '<p>آن و بابی</p>', 'model')
    snapshot = load_snapshot(paths)
    assert [(term['source_term'], term['target_term']) for term in snapshot['terms']] == [('Bob', 'باب'), ('Ann', 'آن')]
    assert snapshot['terms'][1]['origin'] == 'automatic'
    learn_chunk(client, paths, 'one', 'Ann and Bob', 'آن و بابی', 'model')
    assert client.chat.completions.create.call_count == 1


@pytest.mark.parametrize('payload', ['not json', '{"terms":null}', '{"terms":{}}'])
def test_bad_response_can_be_retried_without_losing_terms(tmp_path, payload):
    paths = paths_for(tmp_path)
    client = client_with_terms([])
    client.chat.completions.create.return_value = response(payload)
    learn_chunk(client, paths, 'one', 'Ann', 'آن', 'model')
    state = json.loads((tmp_path / 'glossary_learned.json').read_text())
    assert state['processed_chunks'] == []
    assert 'one' in state['failures']
    client.chat.completions.create.return_value = response(json.dumps({'terms': [candidate()]}))
    learn_chunk(client, paths, 'one', 'Ann', 'آن', 'model')
    state = json.loads((tmp_path / 'glossary_learned.json').read_text())
    assert state['processed_chunks'] == ['one']
    assert state['failures'] == {}


def test_disabled_and_stopped_jobs_make_no_extraction_request(tmp_path):
    client = Mock()
    paths = paths_for(tmp_path, auto_extract=False)
    learn_chunk(client, paths, 'one', 'Ann', 'آن', 'model')
    paths_for(tmp_path)
    stopped = threading.Event()
    stopped.set()
    learn_chunk(client, paths, 'one', 'Ann', 'آن', 'model', stopped)
    client.chat.completions.create.assert_not_called()


def test_new_terms_reach_next_chunk_and_resume_is_idempotent(tmp_path):
    paths = paths_for(tmp_path)
    client = Mock()
    translation_prompts = []
    def create(**kwargs):
        system = kwargs['messages'][0]['content']
        if system.startswith('Extract a concise book glossary'):
            assert paths['translations_file'].exists()
            return response(json.dumps({'terms': [candidate()]}))
        translation_prompts.append(system)
        return response('آن آمد.')
    client.chat.completions.create.side_effect = create
    chunks = [('first', 'Ann arrives.'), ('second', 'Ann returns.')]
    translated, _, _ = process_translations(client, chunks, {}, 'fast', 'EN', 'FA', paths)
    assert 'آن' not in translation_prompts[0]
    assert 'آن' in translation_prompts[1]
    assert client.chat.completions.create.call_count == 4
    process_translations(client, chunks, translated, 'resume', 'EN', 'FA', paths)
    assert client.chat.completions.create.call_count == 4


def test_resume_recovers_extraction_after_translation_checkpoint(tmp_path):
    paths = paths_for(tmp_path)
    translated = {'first': 'آن آمد.'}
    paths['translations_file'].write_text(json.dumps(translated), encoding='utf-8')
    client = client_with_terms([candidate()])
    process_translations(client, [('first', 'Ann arrives.')], translated, 'resume', 'EN', 'FA', paths)
    assert client.chat.completions.create.call_count == 1
    assert load_snapshot(paths)['terms'][0]['source_term'] == 'Ann'


def test_extraction_error_keeps_translated_chunk(tmp_path):
    paths = paths_for(tmp_path)
    client = Mock()
    client.chat.completions.create.side_effect = [response('آن آمد.'), TimeoutError('offline')]
    translated, _, _ = process_translations(client, [('first', 'Ann arrives.')], {}, 'fast', 'EN', 'FA', paths)
    assert translated == {'first': 'آن آمد.'}
    assert json.loads(paths['translations_file'].read_text(encoding='utf-8')) == translated


def test_publication_is_incremental_and_preserves_user_changes(tmp_path):
    database = Database(tmp_path / 'library.db')
    book_id = database.execute("INSERT INTO library_books(title,created_at,updated_at) VALUES ('Book','now','now')")
    paths = paths_for(tmp_path, book_id=book_id)
    learn_chunk(client_with_terms([candidate()]), paths, 'one', 'Ann', 'آن', 'model')
    sync_book(database, paths)
    glossary = get_glossary(database, book_id, 'EN', 'FA')
    assert glossary['terms'][0]['origin'] == 'automatic'
    assert glossary['version'] == 1
    sync_book(database, paths)
    assert get_glossary(database, book_id, 'EN', 'FA')['version'] == 1
    edited = save_glossary(database, book_id, {**glossary, 'terms': [candidate('Bob', 'باب')]})
    learn_chunk(client_with_terms([candidate('Bob', 'بابی')]), paths, 'two', 'Bob', 'بابی', 'model')
    sync_book(database, paths)
    current = get_glossary(database, book_id, 'EN', 'FA')
    assert current['terms'] == edited['terms']
    assert get_glossary(database, book_id, 'EN', 'DE')['terms'] == []

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.glossary.service import get_glossary, save_glossary, load_snapshot, matching_terms, check_translation
from app.storage.database import Database
from app.translation.translator import translate_chunk


def test_version_language_and_snapshot(tmp_path):
    database = Database(tmp_path / 'test.db')
    book = database.execute("INSERT INTO library_books(title,created_at,updated_at) VALUES ('Book','now','now')")
    initial = get_glossary(database, book, 'en', 'fa')
    term = dict(source_term='Ann', target_term='آن', kind='person', notes='')
    saved = save_glossary(database, book, {**initial, 'terms': [term]})
    assert saved['version'] == 1
    assert get_glossary(database, book, 'EN', 'DE')['terms'] == []
    with pytest.raises(ValueError):
        save_glossary(database, book, initial)
    (tmp_path / 'glossary.json').write_text(json.dumps(saved), encoding='utf-8')
    save_glossary(database, book, {**saved, 'terms': []})
    assert load_snapshot({'job_dir': tmp_path})['terms'] == [term]
    assert matching_terms('Annual report', saved) == []
    assert matching_terms('<p>Ann arrived.</p>', saved) == [term]
    assert check_translation('Ann arrived.', 'او آمد.', saved) == [term]
    assert check_translation('Ann arrived.', 'آن آمد.', saved) == []
    with pytest.raises(ValueError):
        save_glossary(database, book, {**saved, 'terms': [term, term]})


def test_terms_reach_translation_request():
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='آن آمد.'))])
    snapshot = {'terms': [dict(source_term='Ann', target_term='آن')]}
    translate_chunk(client, 'Ann arrived.', glossary_snapshot=snapshot)
    prompt = client.chat.completions.create.call_args.kwargs['messages'][0]['content']
    assert 'آن' in prompt
    translate_chunk(client, 'Annual report.', glossary_snapshot=snapshot)
    assert 'آن' not in client.chat.completions.create.call_args.kwargs['messages'][0]['content']


def test_batch_uses_snapshot(tmp_path, monkeypatch):
    from app.translation import batch
    snapshot = {'terms': [dict(source_term='Ann', target_term='آن')]}
    (tmp_path / 'glossary.json').write_text(json.dumps(snapshot), encoding='utf-8')
    monkeypatch.setattr(batch, 'ensure_dir', lambda name: tmp_path)
    monkeypatch.setattr(batch.time, 'sleep', lambda seconds: None)
    client = Mock()
    uploaded = []
    def upload(file, purpose):
        uploaded.extend(json.loads(line) for line in file)
        file.close()
        return SimpleNamespace(id='file-id')
    client.files.create.side_effect = upload
    client.batches.create.return_value = SimpleNamespace(id='batch-id')
    client.batches.retrieve.return_value = SimpleNamespace(status='in_progress', request_counts=SimpleNamespace(completed=0, total=2))
    batch.batch_translate_chunks(client, [('1', 'Ann arrived.'), ('2', 'Annual report.')], 'EN', 'FA', paths={'job_dir': tmp_path})
    assert 'آن' in uploaded[0]['body']['messages'][0]['content']
    assert 'آن' not in uploaded[1]['body']['messages'][0]['content']


def test_pipeline_snapshot_is_not_overwritten(tmp_path, monkeypatch):
    from app import web
    monkeypatch.setattr(web, '_persist_job', lambda job: None)
    job = SimpleNamespace(options={'glossary_snapshot': json.dumps({'version': 1, 'terms': []})}, started_at=None)
    web._on_pipeline_started(job, 'pipeline', {'job_dir': tmp_path})
    job.options['glossary_snapshot'] = json.dumps({'version': 2, 'terms': []})
    web._on_pipeline_started(job, 'pipeline', {'job_dir': tmp_path})
    assert load_snapshot({'job_dir': tmp_path})['version'] == 1


def test_library_glossary_http(tmp_path, monkeypatch):
    import threading
    from http.client import HTTPConnection
    from http.server import ThreadingHTTPServer
    from app import web
    database = Database(tmp_path / 'http.db')
    book = database.execute("INSERT INTO library_books(title,created_at,updated_at) VALUES ('Book','now','now')")
    source = tmp_path / 'book.epub'
    source.write_bytes(b'test source')
    database.execute("INSERT INTO files(book_id,path,kind,display_name,extension,size_bytes,created_at) VALUES (?,?,'original','book.epub','epub',11,'now')", (book, str(source)))
    monkeypatch.setattr(web, 'db', database)
    monkeypatch.setattr(web, 'JOBS', {})
    monkeypatch.setattr(web, 'JOB_META_DIR', tmp_path / 'jobs')
    monkeypatch.setattr(web, '_run_job', lambda job: None)
    server = ThreadingHTTPServer(('127.0.0.1', 0), web.Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    connection = HTTPConnection(*server.server_address)
    try:
        route = f'/api/library/{book}/glossary'
        connection.request('GET', route)
        response = connection.getresponse()
        initial = json.loads(response.read())
        assert response.status == 200
        connection.request('PUT', route, json.dumps({**initial, 'terms': [{'source_term': 'Ann', 'target_term': 'آن'}]}), {'Content-Type': 'application/json'})
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())['version'] == 1
        connection.request('POST', f'/api/library/{book}/translate', '{}', {'Content-Type': 'application/json'})
        response = connection.getresponse()
        result = json.loads(response.read())
        assert response.status == 201
        job = web.JOBS[result['id']]
        assert json.loads(job.options['glossary_snapshot'])['version'] == 1
        assert json.loads(job.options['glossary_snapshot'])['auto_extract'] is True
        assert web._library_book_for_job(job) == book
        assert (tmp_path / 'jobs' / (job.id + '.json')).exists()
        job_dir = tmp_path / 'pipeline'
        job_dir.mkdir()
        web._on_pipeline_started(job, 'pipeline', {'job_dir': job_dir})
        (job_dir / 'glossary_learned.json').write_text(json.dumps({
            'terms': [{'source_term': 'Winterfell', 'target_term': 'وینترفل', 'origin': 'automatic'}],
            'processed_chunks': ['one'], 'failures': {}, 'published_count': 0,
        }), encoding='utf-8')
        connection.request('GET', route)
        response = connection.getresponse()
        glossary = json.loads(response.read())
        assert response.status == 200
        assert any(term['source_term'] == 'Winterfell' for term in glossary['terms'])
        job.status = 'completed'
        connection.request('POST', f'/api/library/{book}/translate', '{"auto_glossary": false}', {'Content-Type': 'application/json'})
        response = connection.getresponse()
        result = json.loads(response.read())
        assert response.status == 201
        assert json.loads(web.JOBS[result['id']].options['glossary_snapshot'])['auto_extract'] is False
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        worker.join()

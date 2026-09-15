import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import pytest

from app.storage.database import Database


@pytest.mark.parametrize(('mode', 'enabled', 'expected'), [('fast', True, True), ('fast', False, False), ('batch', True, False)])
def test_upload_captures_automatic_glossary_choice(tmp_path, monkeypatch, mode, enabled, expected):
    from app import web
    monkeypatch.setattr(web, 'db', Database(tmp_path / 'library.db'))
    monkeypatch.setattr(web, 'JOBS', {})
    monkeypatch.setattr(web, 'UPLOAD_DIR', tmp_path)
    monkeypatch.setattr(web, 'JOB_META_DIR', tmp_path / 'jobs')
    monkeypatch.setattr(web, 'validate_book', lambda path: path)
    monkeypatch.setattr(web, '_run_job', lambda job: None)
    fields = {'mode': mode, 'from_lang': 'EN', 'to_lang': 'FA'}
    if enabled:
        fields['auto_glossary'] = 'true'
    body = ''.join(f'--test-boundary\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n' for key, value in fields.items())
    body += '--test-boundary\r\nContent-Disposition: form-data; name="book"; filename="book.epub"\r\nContent-Type: application/epub+zip\r\n\r\ntest-book\r\n--test-boundary--\r\n'
    server = ThreadingHTTPServer(('127.0.0.1', 0), web.Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    connection = HTTPConnection(*server.server_address)
    try:
        connection.request('POST', '/api/jobs', body.encode(), {'Content-Type': 'multipart/form-data; boundary=test-boundary'})
        response = connection.getresponse()
        result = json.loads(response.read())
        assert response.status == 201
        job = web.JOBS[result['id']]
        snapshot = json.loads(job.options['glossary_snapshot'])
        assert snapshot['auto_extract'] is expected
        assert snapshot['book_id'] == web._library_book_for_job(job)
        metadata = json.loads((tmp_path / 'jobs' / (job.id + '.json')).read_text(encoding='utf-8'))
        assert json.loads(metadata['options']['glossary_snapshot']) == snapshot
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        worker.join()

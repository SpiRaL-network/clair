import importlib
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core


@pytest.fixture
def local_client(tmp_path, monkeypatch):
    # Isolate app initialization from the user's real meeting library.
    data = tmp_path / 'reunions'
    data.mkdir()
    monkeypatch.setattr(core, 'DATA', data)
    app_module = importlib.import_module('app')
    monkeypatch.setattr(app_module, 'ROOT', tmp_path)
    monkeypatch.setattr(app_module, 'studio', core.Studio())
    # Import API tests validate byte storage; inference is replaced by the launch stub.
    monkeypatch.setattr(app_module.studio.catalog, 'installed', lambda mid: mid in app_module.studio.catalog.entries)
    launched = []
    monkeypatch.setattr(app_module.studio, 'launch', launched.append)
    from fastapi.testclient import TestClient
    client = TestClient(app_module.app, base_url='http://127.0.0.1:8787')
    client.cookies.set('clair_session', app_module.TOKEN)
    client.headers['X-Clair-Token'] = app_module.TOKEN
    return client, app_module, launched


def test_selected_file_is_preserved_and_processing_starts(local_client):
    client, app_module, launched = local_client
    content = b'media-data' * 4000
    response = client.post('/api/import-upload', params={
        'filename': '../../réunion été.MP4', 'title': 'Réunion été',
        'language': 'auto', 'auto_summary': 'false'}, content=content)
    assert response.status_code == 200
    meeting = response.json()
    source = Path(meeting['source'])
    assert source.parent == app_module.studio.folder(meeting['id'])
    assert source.name == 'source.mp4'
    assert source.read_bytes() == content
    assert meeting['title'] == 'Réunion été'
    assert meeting['auto_summary'] is False
    assert launched == [meeting['id']]
    assert not list((app_module.ROOT / '.imports').iterdir())


def test_invalid_empty_and_busy_uploads_do_not_create_meetings(local_client):
    client, app_module, launched = local_client
    assert client.post('/api/import-upload?filename=test.exe', content=b'x').status_code == 400
    assert client.post('/api/import-upload?filename=test.mp4&language=invalid', content=b'x').status_code == 400
    assert client.post('/api/import-upload?filename=test.mp4', content=b'').status_code == 400
    app_module.studio.active = 'already-running'
    assert client.post('/api/import-upload?filename=test.mp4', content=b'x').status_code == 409
    assert not app_module.studio.listing()
    assert not launched
    assert not list((app_module.ROOT / '.imports').iterdir())


def test_upload_requires_local_session_and_token(local_client):
    client, _, launched = local_client
    client.headers.pop('X-Clair-Token')
    assert client.post('/api/import-upload?filename=test.mp4', content=b'x').status_code == 403
    client.cookies.clear()
    assert client.post('/api/import-upload?filename=test.mp4', content=b'x').status_code == 401
    assert not launched

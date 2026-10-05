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


def test_participant_and_voice_edits_require_valid_session_and_keep_audio(local_client):
    client, module, _ = local_client
    m = module.studio.create('Test', 'unused.mp4', participants='Alice, Karim')
    mid = m['id']
    module.studio.update(mid, segments=[{'start':1,'end':3,'text':'Bonjour','voice':'voice-1'}],
                         voices=[{'id':'voice-1','name':''}])
    url = '/api/meetings/' + mid
    assert client.post(url + '/voices/voice-1', json={'name':'Alice'}).status_code == 200
    assert client.get(url).json()['segments'][0]['speaker'] == 'Alice'
    assert client.post(url + '/speaker', json={'index':0,'start':1,'speaker':'Karim'}).status_code == 200
    assert client.post(url + '/speaker', json={'index':0,'start':99,'speaker':'Alice'}).status_code == 400
    assert client.post(url + '/participants', json={'participants':'Karim'}).status_code == 200
    client.headers.pop('X-Clair-Token')
    assert client.post(url + '/voices/voice-1', json={'name':'Karim'}).status_code == 403
    assert client.post('/api/models/refresh').status_code == 403
    assert client.post('/api/voices/install').status_code == 403


def test_new_voice_settings_are_saved_with_uploaded_media(local_client, monkeypatch):
    client, module, _ = local_client
    monkeypatch.setattr(module.studio.voices, 'ready', lambda: True)
    response = client.post('/api/import-upload', params={'filename':'test.mp4',
        'participants':'Alice\nKarim', 'diarize':True, 'speaker_count':2,
        'execution':'gpu','voice_execution':'cpu'}, content=b'test-audio')
    assert response.status_code == 200
    meeting = response.json()
    assert meeting['participants'] == ['Alice','Karim']
    assert meeting['diarize'] and meeting['speaker_count'] == 2
    assert meeting['execution'] == 'gpu' and meeting['voice_execution'] == 'cpu'
    assert client.post('/api/import-upload', params={'filename':'test.mp4','speaker_count':99},content=b'x').status_code == 422


def test_reference_api_validates_payload_and_requires_local_session(local_client, monkeypatch):
    client, module, _ = local_client
    meeting = module.studio.create('Test', 'unused.wav', participants='Alice\nKarim')
    url = '/api/meetings/' + meeting['id'] + '/voice-references'
    received = []
    monkeypatch.setattr(module.studio, 'launch_voice_references', lambda *args: received.append(args))
    payload = {'references':[{'name':'Alice','start':1.5,'end':6.5}], 'execution':'cpu'}
    assert client.post(url, json=payload).status_code == 200
    assert received == [(meeting['id'], payload['references'], 'cpu')]
    assert client.post(url, json={'references':[{'name':'Alice','start':-1,'end':6}]}).status_code == 422
    client.headers.pop('X-Clair-Token')
    assert client.post(url, json=payload).status_code == 403
    client.cookies.clear()
    assert client.post(url, json=payload).status_code == 401
    assert len(received) == 1

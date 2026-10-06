import json
import sys
from pathlib import Path
import wave
import threading
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core

@pytest.fixture(autouse=True)
def models_available_for_storage_tests(monkeypatch):
    # These tests exercise persistence/capture, with no model loading or downloads.
    monkeypatch.setattr(core.ModelCatalog, 'installed', lambda self, mid: mid in self.entries)

def test_long_meeting_chunking_keeps_every_passage():
    segments = [{'start': i * 3, 'text': f'Unique passage {i} ' + 'x' * 700} for i in range(100)]
    parts = list(core.chunks(segments, limit=2000))
    assert len(parts) > 10
    rebuilt = '\n'.join(parts)
    for s in segments:
        assert rebuilt.count(f'[{core.stamp(s["start"])}] {s["text"]}') == 1

def test_path_traversal_and_interrupted_job_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DATA', tmp_path)
    s = core.Studio()
    for mid in ('../outside', '0' * 15, 'z' * 16, '0' * 16 + '/..'):
        with pytest.raises(ValueError):
            s.folder(mid)
    m = s.create('Test', 'missing.mp4')
    s.update(m['id'], status='transcribing', segments=[{'start': 0, 'end': 1, 'text': 'Conservé'}])
    recovered = core.Studio().read(m['id'])
    assert recovered['status'] == 'interrupted'
    assert recovered['segments'][0]['text'] == 'Conservé'

def test_microphone_only_mix_has_correct_duration_and_audio(tmp_path):
    import numpy as np
    rate = 48000
    samples = (np.sin(2 * np.pi * 440 * np.arange(rate) / rate) * 10000).astype(np.int16)
    with wave.open(str(tmp_path / 'mic.wav'), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(samples.tobytes())
    r = core.Recorder()
    r.folder = tmp_path
    mixed = r.mix()
    with wave.open(str(mixed), 'rb') as w:
        assert w.getframerate() == 16000
        assert 15900 < w.getnframes() < 16100
        assert np.max(np.abs(np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16))) > 8000

def test_cancel_preserves_exportable_partial_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(core,'DATA',tmp_path)
    s=core.Studio()
    m=s.create('Partiel','missing.mp4')
    s.update(m['id'], segments=[{'start':0,'end':1.5,'text':'Une décision.'}])
    s.active=m['id']
    s.cancel(m['id'])
    s.write_transcript(m['id'])
    assert s.cancelled.is_set()
    assert 'Une décision.' in (s.folder(m['id'])/'transcription.txt').read_text(encoding='utf-8')

def test_report_markdown_keeps_proposals_separate_from_decisions():
    r={'title':'Test','overview':'Résumé','topics':[{'title':'Outil','points':['Un fait']}],
       'decisions':[], 'proposals':[{'text':'Étendre éventuellement','time':'00:00:12'}],
       'actions':[], 'questions':[]}
    md=core.markdown_report(r)
    assert md.index('Aucune décision explicite') < md.index('Étendre éventuellement')
    assert '## Propositions à confirmer' in md

def test_silent_loopback_gets_elapsed_time_instead_of_empty_wave(tmp_path):
    import time
    r=core.Recorder()
    w=wave.open(str(tmp_path/'silent.wav'),'wb')
    w.setnchannels(2);w.setsampwidth(2);w.setframerate(48000)
    r.files=[w]
    r.clock_started=time.monotonic()-2
    r.stop()
    with wave.open(str(tmp_path/'silent.wav'),'rb') as f:
        assert 95900 < f.getnframes() < 97000
        assert f.readframes(100)==b'\0'*400


def test_transient_replace_denial_preserves_old_file_until_commit(tmp_path, monkeypatch):
    path = tmp_path / 'meeting.json'
    path.write_text('{"segments": ["ancien"]}', encoding='utf-8')
    replace = Path.replace
    attempts = []
    def temporarily_locked(source, target):
        attempts.append(source)
        if len(attempts) < 3:
            assert json.loads(path.read_text(encoding='utf-8'))['segments'] == ['ancien']
            raise PermissionError('temporary Windows sharing lock')
        return replace(source, target)
    monkeypatch.setattr(Path, 'replace', temporarily_locked)
    monkeypatch.setattr(core.time, 'sleep', lambda delay: None)
    core.atomic_json_write(path, {'segments':['transcription complète'], 'status':'done'})
    assert json.loads(path.read_text(encoding='utf-8'))['segments'] == ['transcription complète']
    assert len(attempts) == 3 and not list(tmp_path.glob('meeting-*.tmp'))


def test_persistent_denial_keeps_old_json_and_complete_recovery_snapshot(tmp_path, monkeypatch):
    path = tmp_path / 'meeting.json'
    path.write_text('{"segments": ["ancien"]}', encoding='utf-8')
    def locked(*args): raise PermissionError('persistent access denial')
    monkeypatch.setattr(Path, 'replace', locked)
    monkeypatch.setattr(core.time, 'sleep', lambda delay: None)
    payload = {'segments':['dernier passage'], 'status':'transcribing'}
    for _ in range(2):
        with pytest.raises(PermissionError): core.atomic_json_write(path, payload)
    assert json.loads(path.read_text(encoding='utf-8'))['segments'] == ['ancien']
    snapshots = list(tmp_path.glob('meeting-*.tmp'))
    assert len(snapshots) == 2 and all(json.loads(p.read_text(encoding='utf-8')) == payload for p in snapshots)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows file sharing semantics')
def test_real_windows_read_handle_does_not_abort_save(tmp_path):
    import ctypes
    from ctypes import wintypes
    path = tmp_path / 'meeting.json'
    path.write_text('{"status":"transcribing"}', encoding='utf-8')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    # Read/write sharing, deliberately without FILE_SHARE_DELETE, as with Python file readers.
    handle = kernel.CreateFileW(str(path), 0x80000000, 3, None, 3, 128, None)
    assert handle != ctypes.c_void_p(-1).value
    released = threading.Event()
    def release():
        kernel.CloseHandle(handle)
        released.set()
    timer = threading.Timer(.2, release)
    timer.start()
    try:
        core.atomic_json_write(path, {'status':'done', 'segments':['conservé']})
        assert released.is_set()
        assert json.loads(path.read_text(encoding='utf-8'))['status'] == 'done'
    finally:
        timer.join(timeout=2)
        if not released.is_set(): release()


def test_api_reader_and_progress_writer_are_serialized(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DATA', tmp_path)
    studio = core.Studio()
    m = studio.create('Test', 'unused.mp4')
    target = studio.folder(m['id']) / 'meeting.json'
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    read_text = Path.read_text
    def held_read(path, *args, **kwargs):
        if path == target and threading.current_thread().name == 'held-reader':
            with path.open(encoding='utf-8') as file:
                entered.set()
                assert release.wait(timeout=3)
                return file.read()
        return read_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', held_read)
    reader = threading.Thread(target=lambda: studio.read(m['id']), name='held-reader')
    def write():
        studio.update(m['id'], progress=90)
        finished.set()
    writer = threading.Thread(target=write)
    reader.start()
    assert entered.wait(timeout=2)
    writer.start()
    try:
        assert not finished.wait(timeout=.1)
    finally:
        release.set()
        reader.join(timeout=3)
        writer.join(timeout=3)
    assert finished.is_set() and studio.read(m['id'])['progress'] == 90

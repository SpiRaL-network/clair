import json
import sys
from pathlib import Path
import wave
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

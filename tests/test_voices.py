from pathlib import Path
import sys
import threading

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core
from voices import attribute_segments, split_at_voice_changes


@pytest.fixture
def meeting(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DATA', tmp_path)
    monkeypatch.setattr(core.ModelCatalog, 'installed', lambda self, mid: mid in self.entries)
    studio = core.Studio()
    m = studio.create('Test', 'unused.wav', participants='Alice, Karim; Alice')
    studio.update(m['id'], report={'overview': 'Ancien rapport'}, voices=[
        {'id':'voice-1', 'label':'Voix 1', 'name':''}],
        segments=[{'start':0,'end':2,'text':'Un fait.','voice':'voice-1'},
                  {'start':3,'end':5,'text':'Une autre phrase.','voice':'voice-1'}])
    return studio, m['id']


def test_overlap_attribution_leaves_mixed_and_uncovered_segments_unassigned():
    segments = [{'start':0,'end':3,'text':'A'}, {'start':3,'end':6,'text':'Mixed'},
                {'start':7,'end':9,'text':'Silent'}]
    turns = [{'start':0,'end':4.5,'voice':'voice-1'}, {'start':4.5,'end':6,'voice':'voice-2'}]
    result = attribute_segments(segments, turns)
    assert result[0]['voice'] == 'voice-1' and 'speaker' not in result[0]
    assert result[1]['voice_uncertain'] and 'voice' not in result[1]
    assert result[2]['voice_uncertain'] and 'voice' not in result[2]


def test_word_timestamps_split_mixed_paragraph_without_losing_text():
    words = [{'start':0,'end':1,'word':' Bonjour'}, {'start':1,'end':2,'word':' Alice.'},
             {'start':3,'end':4,'word':' Salut'}, {'start':4,'end':5,'word':' Karim.'}]
    segment = {'start':0,'end':5,'text':'Bonjour Alice. Salut Karim.', 'words':words}
    turns = [{'start':0,'end':2,'voice':'voice-1'}, {'start':3,'end':5,'voice':'voice-2'}]
    result = split_at_voice_changes([segment], turns)
    assert [r['voice'] for r in result] == ['voice-1', 'voice-2']
    assert ' '.join(r['text'] for r in result) == segment['text']
    assert [w for r in result for w in r['words']] == words


def test_names_apply_to_voice_but_preserve_manual_corrections(meeting):
    studio, mid = meeting
    assert studio.read(mid)['participants'] == ['Alice', 'Karim']
    studio.set_speaker(mid, 1, 3, 'Karim')
    m = studio.name_voice(mid, 'voice-1', 'Alice')
    assert [s['speaker'] for s in m['segments']] == ['Alice', 'Karim']
    assert m['report_stale'] and m['report']['overview'] == 'Ancien rapport'
    txt = (studio.folder(mid) / 'transcription.txt').read_text(encoding='utf-8')
    assert 'Alice : Un fait.' in txt and 'Karim : Une autre phrase.' in txt
    assert 'Alice : Un fait.' in '\n'.join(core.chunks(m['segments']))
    assert 'Karim : Une autre phrase.' in (studio.folder(mid) / 'sous-titres.srt').read_text(encoding='utf-8')


def test_removing_participant_clears_name_from_voice_and_segments(meeting):
    studio, mid = meeting
    studio.name_voice(mid, 'voice-1', 'Alice')
    m = studio.set_participants(mid, 'Karim')
    assert m['voices'][0]['name'] == '' and all('speaker' not in s for s in m['segments'])
    assert 'Alice' not in (studio.folder(mid) / 'transcription.txt').read_text(encoding='utf-8')


def test_invalid_names_stale_segment_and_busy_edits_are_rejected(meeting):
    studio, mid = meeting
    with pytest.raises(ValueError): studio.name_voice(mid, 'voice-1', 'Unknown')
    with pytest.raises(ValueError): studio.name_voice(mid, 'voice-999', 'Alice')
    with pytest.raises(ValueError): studio.set_speaker(mid, 0, 99, 'Alice')
    with pytest.raises(ValueError): studio.set_participants(mid, ['x'] * 31 + ['y' * 81])
    studio.active = mid
    with pytest.raises(RuntimeError): studio.name_voice(mid, 'voice-1', 'Alice')
    with pytest.raises(RuntimeError): studio.set_participants(mid, 'Alice')
    with pytest.raises(RuntimeError): studio.set_speaker(mid, 0, 0, 'Alice')


def test_explicit_unassignment_survives_remapping_voice(meeting):
    studio, mid = meeting
    studio.name_voice(mid, 'voice-1', 'Alice')
    studio.set_speaker(mid, 0, 0, '')
    m = studio.name_voice(mid, 'voice-1', 'Karim')
    assert 'speaker' not in m['segments'][0] and m['segments'][1]['speaker'] == 'Karim'


def test_cancelled_diarization_keeps_existing_attributions(meeting, monkeypatch):
    studio, mid = meeting
    studio.name_voice(mid, 'voice-1', 'Alice')
    from faster_whisper import audio
    monkeypatch.setattr(audio, 'decode_audio', lambda *args, **kwargs: [])
    def analyze(*args):
        studio.cancelled.set()
        return [], []
    monkeypatch.setattr(studio.voices, 'analyze', analyze)
    with pytest.raises(core.Cancelled): studio.diarize(mid)
    assert studio.read(mid)['segments'][0]['speaker'] == 'Alice'


def test_new_report_contains_participant_snapshot_and_named_source(meeting, monkeypatch):
    studio, mid = meeting
    studio.name_voice(mid, 'voice-1', 'Alice')
    prompts = []
    def ask(text, *args, **kwargs):
        prompts.append(text)
        return {'title':'Test', 'overview':'Résumé de test.', 'topics':[], 'decisions':[],
                'proposals':[], 'actions':[], 'questions':[]}
    monkeypatch.setattr(studio.llm, 'ask', ask)
    studio.summarize(mid)
    m = studio.read(mid)
    assert 'Alice : Un fait.' in prompts[0]
    assert m['report']['participants'] == ['Alice', 'Karim'] and not m['report_stale']
    assert 'Participants déclarés : Alice, Karim' in (studio.folder(mid) / 'compte-rendu.md').read_text(encoding='utf-8')

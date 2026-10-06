import copy
import json
import sys
import threading
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core


def report(title='Rapport'):
    return {'title': title, 'overview': 'Les faits de la réunion.', 'topics': [],
            'decisions': [], 'proposals': [], 'actions': [], 'questions': []}


def stream(text, finish='stop', done=True):
    events = [{'choices': [{'delta': {'content': text}, 'finish_reason': None}]},
              {'choices': [], 'usage': {'completion_tokens': 42}},
              {'choices': [{'delta': {}, 'finish_reason': finish}]}]
    lines = [b'data: ' + json.dumps(event).encode() for event in events]
    return lines + ([b'data: [DONE]'] if done else [])


class Response:
    def __init__(self, lines): self.lines = lines
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def raise_for_status(self): pass
    def iter_lines(self): yield from self.lines


@pytest.fixture
def engine(monkeypatch):
    llm = core.LocalLLM()
    monkeypatch.setattr(llm, 'start', lambda cancelled: None)
    monkeypatch.setattr(llm, 'prompt_tokens', lambda messages: 100)
    return llm


@pytest.mark.parametrize('bad', [
    stream('{"title":"Coupé', 'length'),
    stream(json.dumps(report()), 'length'),
    stream(json.dumps(report()), done=False),
    stream('{"title":"Pas de overview"}'),
    stream('{"title":"JSON incomplet'),
])
def test_incomplete_output_is_regenerated_with_more_room(engine, monkeypatch, bad):
    calls = []
    responses = iter([bad, stream(json.dumps(report('Complet'))) ])
    def post(*args, **kwargs):
        calls.append(copy.deepcopy(kwargs['json']))
        return Response(next(responses))
    monkeypatch.setattr(core.requests, 'post', post)
    assert engine.ask('Source originale', threading.Event())['title'] == 'Complet'
    assert [call['max_tokens'] for call in calls] == [4200, 8192]
    assert calls[0]['messages'][1] == calls[1]['messages'][1]
    assert 'JSON complet' in calls[1]['messages'][0]['content']


def test_two_failures_stop_without_accepting_partial_json(engine, monkeypatch):
    calls = []
    def post(*args, **kwargs):
        calls.append(kwargs['json']['max_tokens'])
        return Response(stream('{"title":"contenu privé', 'length'))
    monkeypatch.setattr(core.requests, 'post', post)
    with pytest.raises(RuntimeError, match='Reprendre le résumé') as error:
        engine.ask('Source', threading.Event())
    assert calls == [4200, 8192]
    assert 'contenu privé' not in str(error.value)


def test_cancel_during_stream_stops_without_retry(engine, monkeypatch):
    cancelled = threading.Event()
    calls, stopped = [], []
    class CancelledResponse(Response):
        def iter_lines(self):
            cancelled.set()
            yield from self.lines
    monkeypatch.setattr(engine, 'stop', lambda: stopped.append(True))
    def post(*args, **kwargs):
        calls.append(True)
        return CancelledResponse(stream(json.dumps(report())))
    monkeypatch.setattr(core.requests, 'post', post)
    with pytest.raises(core.Cancelled): engine.ask('Source', cancelled)
    assert len(calls) == 1 and stopped == [True]


def test_retry_budget_respects_actual_context_space(engine, monkeypatch):
    monkeypatch.setattr(engine, 'prompt_tokens', lambda messages: 11000)
    calls = []
    responses = iter([stream('{', 'length'), stream(json.dumps(report()))])
    def post(*args, **kwargs):
        calls.append(kwargs['json']['max_tokens'])
        return Response(next(responses))
    monkeypatch.setattr(core.requests, 'post', post)
    engine.ask('Source entière', threading.Event())
    assert calls == [4200, 5128]


def test_oversized_prompt_is_rejected_before_inference(engine, monkeypatch):
    monkeypatch.setattr(engine, 'prompt_tokens', lambda messages: 16000)
    def unexpected(*args, **kwargs): raise AssertionError('Cannot fit this prompt')
    monkeypatch.setattr(core.requests, 'post', unexpected)
    with pytest.raises(RuntimeError, match='contexte'): engine.ask('Source entière', threading.Event())


def test_prompt_token_count_uses_model_chat_template(monkeypatch):
    llm = core.LocalLLM()
    calls = []
    class JsonResponse(Response):
        def __init__(self, value): self.value = value
        def json(self): return self.value
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return JsonResponse({'prompt': '<user>source<assistant>'} if url.endswith('/apply-template') else {'tokens': [1, 2, 3]})
    monkeypatch.setattr(core.requests, 'post', post)
    messages = [{'role': 'user', 'content': 'source'}]
    assert llm.prompt_tokens(messages) == 3
    assert calls[0][1]['json'] == {'messages': messages}
    assert calls[1][1]['json']['content'] == '<user>source<assistant>'
    assert all('Authorization' in kwargs['headers'] for _, kwargs in calls)


@pytest.fixture
def meeting(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DATA', tmp_path)
    monkeypatch.setattr(core.ModelCatalog, 'installed', lambda self, mid: mid in self.entries)
    studio = core.Studio()
    m = studio.create('Test', 'unused.mp4')
    studio.update(m['id'], segments=[{'start': i, 'end': i+1, 'text': 'Passage ' + str(i) + 'x'*4000} for i in range(3)])
    monkeypatch.setattr(studio.llm, 'stop', lambda: None)
    studio.llm.device = 'cpu'
    return studio, m['id']


def test_resume_reuses_completed_parts_and_keeps_transcript(meeting, monkeypatch):
    studio, mid = meeting
    before = studio.read(mid)['segments']
    calls = []
    def fail_on_second(source, *args, **kwargs):
        calls.append(source)
        if len(calls) == 2: raise RuntimeError('interruption')
        return report()
    monkeypatch.setattr(studio.llm, 'ask', fail_on_second)
    with pytest.raises(RuntimeError): studio.summarize(mid)
    checkpoint = studio.folder(mid) / 'summary-checkpoint.json'
    assert len(json.loads(checkpoint.read_text())['reports']) == 1
    resumed = []
    monkeypatch.setattr(studio.llm, 'ask', lambda source, *args, **kwargs: resumed.append(source) or report())
    studio.summarize(mid)
    assert len(resumed) == 3  # two remaining passages + consolidation
    assert calls[0] not in resumed
    assert studio.read(mid)['segments'] == before
    assert studio.read(mid)['summary_device'] == 'cpu'
    assert not checkpoint.exists()
    assert (studio.folder(mid) / 'compte-rendu.md').is_file()


@pytest.mark.parametrize('change', ['participants', 'segments', 'llm_model', 'execution'])
def test_changed_input_does_not_reuse_old_summary_parts(meeting, monkeypatch, change):
    studio, mid = meeting
    calls = []
    def fail_on_second(source, *args, **kwargs):
        calls.append(source)
        if len(calls) == 2: raise RuntimeError('interruption')
        return report()
    monkeypatch.setattr(studio.llm, 'ask', fail_on_second)
    with pytest.raises(RuntimeError): studio.summarize(mid)
    m = studio.read(mid)
    changes = {'participants': ['Alice'], 'segments': m['segments'] + [{'start': 5, 'end': 6, 'text': 'Nouveau'}],
               'llm_model': next(key for key in studio.catalog.entries if key != m['llm_model']), 'execution': 'cpu'}
    studio.update(mid, **{change: changes[change]})
    resumed = []
    monkeypatch.setattr(studio.llm, 'ask', lambda source, *args, **kwargs: resumed.append(source) or report())
    studio.summarize(mid)
    assert len(resumed) >= 4  # all passages must be recomputed


def test_resume_from_complete_cache_preserves_device(meeting, monkeypatch):
    studio, mid = meeting
    monkeypatch.setattr(studio.llm, 'ask', lambda *args, **kwargs: report())
    update = studio.update
    def fail_before_commit(mid, **values):
        if 'report' in values: raise RuntimeError('saving interrupted')
        return update(mid, **values)
    monkeypatch.setattr(studio, 'update', fail_before_commit)
    with pytest.raises(RuntimeError): studio.summarize(mid)
    monkeypatch.setattr(studio, 'update', update)
    studio.llm.device = None
    def unexpected(*args, **kwargs): raise AssertionError('No inference needed')
    monkeypatch.setattr(studio.llm, 'ask', unexpected)
    studio.summarize(mid)
    assert studio.read(mid)['summary_device'] == 'cpu'


def test_summary_failure_is_marked_for_safe_retry(meeting, monkeypatch):
    studio, mid = meeting
    def fail(mid): raise RuntimeError('Résumé incomplet')
    monkeypatch.setattr(studio, 'summarize', fail)
    monkeypatch.setattr(core, 'ROOT', studio.folder(mid))  # keep test logs out of application log
    before = studio.read(mid)['segments']
    studio.run(mid, summary_only=True)
    m = studio.read(mid)
    assert m['status'] == 'error' and m['failed_stage'] == 'summary'
    assert m['segments'] == before


@pytest.mark.parametrize('repetitions', [600, 1000])
def test_dense_notes_still_consolidate_without_dropping_a_part(meeting, monkeypatch, repetitions):
    studio, mid = meeting
    studio.update(mid, segments=studio.read(mid)['segments'][:2])
    calls = []
    def dense(source, *args, **kwargs):
        calls.append(source)
        value = report('Note ' + str(len(calls)))
        value['overview'] = 'Faits détaillés. ' * repetitions
        return value
    monkeypatch.setattr(studio.llm, 'ask', dense)
    studio.summarize(mid)
    assert len(calls) == 3
    combined = json.loads(calls[-1])
    assert [note['title'] for note in combined] == ['Note 1', 'Note 2']
    assert studio.read(mid)['report']['title'] == 'Note 3'

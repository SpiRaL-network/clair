import copy
import hashlib
import json
from pathlib import Path
import sys
import threading

import pytest
import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog
import discovery


def info(repo='unsloth/New-Chat-4B-GGUF'):
    return {'id': repo, 'sha': 'a' * 40, 'createdAt': '2026-03-01T12:00:00Z',
            'pipeline_tag': 'text-generation', 'cardData': {'license': 'apache-2.0'},
            'siblings': [{'rfilename': 'New-Chat-4B-Q4_K_M.gguf',
                          'lfs': {'size': 2_000_000_000, 'sha256': 'b' * 64}}]}


def test_discovery_pins_revision_digest_and_distinguishes_storage_names():
    entry = discovery.make_entry(info())
    assert entry['revision'] == 'a' * 40 and entry['sha256'] == 'b' * 64
    assert entry['filename'] != entry['source_filename']
    assert entry['license'] == 'apache-2.0' and entry['date_label'] == 'Ajout au dépôt'
    assert discovery.validate_cached(entry) == {**entry, 'visible': True}


@pytest.mark.parametrize('change', ['unknown-author', 'private', 'gated', 'license', 'revision',
                                  'traversal', 'split', 'too-big', 'no-digest', 'future', 'wrong-task'])
def test_discovery_rejects_unusable_or_untrusted_entries(change):
    data = info()
    if change == 'unknown-author': data['id'] = 'unknown/New-Chat-4B-GGUF'
    elif change in ('private', 'gated'): data[change] = True
    elif change == 'license': data['cardData']['license'] = 'other'
    elif change == 'revision': data['sha'] = 'main'
    elif change == 'traversal': data['siblings'][0]['rfilename'] = '../New-Q4_K_M.gguf'
    elif change == 'split': data['siblings'][0]['rfilename'] = 'New-Q4_K_M-00001-of-00002.gguf'
    elif change == 'too-big': data['siblings'][0]['lfs']['size'] = 50_000_000_000
    elif change == 'no-digest': data['siblings'][0]['lfs'].pop('sha256')
    elif change == 'future': data['createdAt'] = '2099-01-01T00:00:00Z'
    elif change == 'wrong-task': data['pipeline_tag'] = 'text-to-image'
    assert discovery.make_entry(data) is None


def small_catalog(tmp_path):
    payload = b'GGUF-test'
    seed = dict(id='local', name='Local', repo='trusted/test', filename='local.gguf',
                revision='a'*40, size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    (tmp_path / 'models-catalog.json').write_text(json.dumps([seed]))
    (tmp_path / 'models').mkdir()
    (tmp_path / 'models/local.gguf').write_bytes(payload)
    return catalog.ModelCatalog(tmp_path)


def test_refresh_persists_offline_cache_without_switching_installed_model(tmp_path, monkeypatch):
    c = small_catalog(tmp_path);c.set_default('local');c.set_execution('cpu')
    entry = discovery.make_entry(info())
    monkeypatch.setattr(catalog, 'discover', lambda *args: ([entry], []))
    c.start_refresh();c.refresh_thread.join(3)
    assert c.refreshing['status'] == 'done'
    restarted = catalog.ModelCatalog(tmp_path)
    assert restarted.default() == 'local' and restarted.execution == 'cpu'
    assert entry['id'] in restarted.entries
    before = (tmp_path / 'catalog-cache.json').read_bytes()
    def offline(*args): raise requests.ConnectionError('offline')
    monkeypatch.setattr(catalog, 'discover', offline)
    restarted.start_refresh();restarted.refresh_thread.join(3)
    assert restarted.refreshing['status'] == 'error'
    assert (tmp_path / 'catalog-cache.json').read_bytes() == before
    assert entry['id'] in restarted.entries


def test_removed_remote_entries_remain_resolvable_for_existing_meetings(tmp_path, monkeypatch):
    c = small_catalog(tmp_path);entry = discovery.make_entry(info())
    monkeypatch.setattr(catalog, 'discover', lambda *args: ([entry], []))
    c._refresh()
    monkeypatch.setattr(catalog, 'discover', lambda *args: ([], []))
    c._refresh()
    assert c.resolve(entry['id'], require_installed=False) == entry['id']
    assert entry['id'] not in [m['id'] for m in c.state()['models']]


def test_tampered_cache_never_introduces_a_filesystem_path(tmp_path):
    c = small_catalog(tmp_path);entry = discovery.make_entry(info())
    entry['filename'] = '../outside.gguf'
    (tmp_path / 'catalog-cache.json').write_text(json.dumps({'models': [entry]}))
    assert set(catalog.ModelCatalog(tmp_path).entries) == {'local'}


def test_source_queries_only_fetch_metadata_and_balance_publishers(monkeypatch):
    calls = []
    def get(path, **params):
        calls.append((path, params))
        if not path:
            return [info(f"{params['author']}/New-Chat-{i}B-GGUF") for i in range(8)]
        return info(path[1:])
    monkeypatch.setattr(discovery, 'get_json', get)
    found, warnings = discovery.discover(set(), threading.Event(), lambda message: None)
    assert not warnings and len(found) == 12
    assert all(sum(e['repo'].startswith(a + '/') for e in found) == 4 for a in discovery.PUBLISHERS)
    assert all(params.get('blobs') == 'true' for path, params in calls if path)


def test_partial_source_failure_preserves_previously_visible_entries(tmp_path, monkeypatch):
    c = small_catalog(tmp_path);entry = discovery.make_entry(info())
    monkeypatch.setattr(catalog, 'discover', lambda *args: ([entry], []));c._refresh()
    monkeypatch.setattr(catalog, 'discover', lambda *args: ([], ['unsloth']));c._refresh()
    assert entry['id'] in [m['id'] for m in c.state()['models']]

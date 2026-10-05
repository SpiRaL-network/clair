"""Discover public GGUF metadata. Never execute repository code or upload user data."""
from datetime import datetime, timezone
import hashlib
import math
import re
import time

import requests

PUBLISHERS = ('unsloth', 'bartowski', 'lmstudio-community')
OPEN_LICENSES = {'apache-2.0', 'mit', 'bsd-2-clause', 'bsd-3-clause', 'cc0-1.0', 'cc-by-4.0'}
MAX_SIZE = 20_000_000_000
MAX_MODELS = 12


def get_json(path, **params):
    with requests.get('https://huggingface.co/api/models' + path, params=params,
                      headers={'User-Agent': 'Clair-local/1.2'}, stream=True,
                      timeout=(5, 12)) as response:
        response.raise_for_status()
        data = bytearray()
        for block in response.iter_content(65536):
            data.extend(block)
            if len(data) > 4_000_000:
                raise ValueError('Réponse du catalogue trop volumineuse.')
        import json
        return json.loads(data)


def license_of(info):
    value = (info.get('cardData') or {}).get('license')
    if not isinstance(value, str):
        value = next((tag[8:] for tag in info.get('tags', []) if tag.startswith('license:')), '')
    return value.lower()


def safe_repo(repo):
    return isinstance(repo, str) and bool(re.fullmatch(
        r'(unsloth|bartowski|lmstudio-community)/[A-Za-z0-9][A-Za-z0-9_.-]{0,180}', repo))


def candidate(info):
    repo = info.get('id', '')
    if not safe_repo(repo) or info.get('private') or info.get('gated') or info.get('disabled'):
        return False
    name = repo.split('/')[1].lower()
    if not name.endswith('-gguf') or any(word in name for word in (
        'embedding', 'rerank', 'whisper', 'diffusion', 'image-gen', 'qwen-image', 'tts', 'ocr', 'reward')):
        return False
    return (license_of(info) in OPEN_LICENSES and
            info.get('pipeline_tag') in (None, 'text-generation', 'image-text-to-text'))


def make_entry(info):
    if not candidate(info) or not re.fullmatch(r'[0-9a-f]{40}', info.get('sha', '')):
        return None
    options = []
    for file in info.get('siblings', []):
        name = file.get('rfilename', '')
        lfs = file.get('lfs') or {}
        size = lfs.get('size', 0)
        if (re.fullmatch(r'[A-Za-z0-9_.-]+\.gguf', name) and
                re.search(r'(?i)[.-]Q4_K_M\.gguf$', name) and
                not re.search(r'(?i)mmproj|vision|adapter', name) and
                isinstance(size, int) and 500_000_000 <= size <= MAX_SIZE and
                re.fullmatch(r'[0-9a-f]{64}', lfs.get('sha256', ''))):
            options.append(file)
    if not options:
        return None
    file = min(options, key=lambda f: f['lfs']['size'])
    try:
        published = datetime.fromisoformat(info['createdAt'].replace('Z', '+00:00'))
        if published.tzinfo is None or published > datetime.now(timezone.utc):
            return None
    except (KeyError, ValueError, TypeError):
        return None
    repo, revision, name = info['id'], info['sha'], file['rfilename']
    key = hashlib.sha256(f'{repo}@{revision}/{name}'.encode()).hexdigest()[:20]
    size = file['lfs']['size']
    return dict(id='hub-' + key, name=repo.split('/')[1][:-5].replace('_', ' '),
                repo=repo, revision=revision, source_filename=name,
                filename=f'hub-{key}-{name}', size=size, sha256=file['lfs']['sha256'],
                source='https://huggingface.co/' + repo, quantization='Q4_K_M',
                release_date=published.date().isoformat(), date_label='Ajout au dépôt',
                memory_gb=math.ceil(size / 1e9 + 3), license=license_of(info),
                description='Découvert sur Hugging Face. Résumé texte uniquement ; compatibilité et qualité à essayer sur votre PC.',
                dynamic=True, no_thinking=True)


def validate_cached(entry):
    """Untrusted cache must not introduce paths, hosts, or mutable model revisions."""
    try:
        restored = make_entry(dict(id=entry['repo'], sha=entry['revision'],
                                   createdAt=entry['release_date'] + 'T00:00:00Z',
                                   cardData={'license': entry['license']},
                                   siblings=[{'rfilename': entry['source_filename'],
                                              'lfs': {'size': entry['size'], 'sha256': entry['sha256']}}]))
        if restored and all(restored[key] == entry[key] for key in
                            ('id', 'repo', 'revision', 'filename', 'source_filename', 'size', 'sha256')):
            return {**restored, 'visible': bool(entry.get('visible', True))}
    except (KeyError, TypeError, ValueError):
        pass
    return None


def discover(known, cancelled, progress):
    start = time.monotonic()
    listed, warnings = {}, []
    for author in PUBLISHERS:
        if cancelled.is_set():
            return [], warnings
        progress('Recherche des nouveautés chez ' + author + '…')
        try:
            values = get_json('', author=author, filter='gguf', sort='createdAt', direction=-1, limit=40)
            if not isinstance(values, list):
                raise ValueError('Liste inattendue.')
            for value in values:
                if isinstance(value, dict) and candidate(value):
                    listed[value['id']] = value
        except (requests.RequestException, ValueError, TypeError):
            warnings.append(author)
    if len(warnings) == len(PUBLISHERS):
        raise RuntimeError('Hugging Face est indisponible. Le catalogue local reste accessible.')
    models, seen_files, counts = [], set(known), dict.fromkeys(PUBLISHERS, 0)
    # Balance publishers so one prolific converter does not hide new official families.
    queues = {author: sorted((v for v in listed.values() if v['id'].startswith(author + '/')),
                            key=lambda x: x.get('createdAt', ''), reverse=True) for author in PUBLISHERS}
    ordered = [queue[i] for i in range(15) for queue in queues.values() if i < len(queue)]
    for info in ordered:
        if cancelled.is_set() or time.monotonic() - start > 100:
            break
        author = info['id'].split('/')[0]
        if counts[author] >= 4:
            continue
        progress('Vérification de ' + info['id'].split('/')[1] + '…')
        try:
            entry = make_entry(get_json('/' + info['id'], blobs='true'))
            if entry:
                identity = (entry['repo'], entry['source_filename'])
                if identity not in seen_files:
                    models.append(entry)
                    counts[author] += 1
                    seen_files.add(identity)
        except (requests.RequestException, ValueError, TypeError):
            warnings.append(info['id'])
        if len(models) >= MAX_MODELS:
            break
    return models, warnings

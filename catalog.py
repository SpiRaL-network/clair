"""Curated, pinned GGUF catalogue; downloads never transmit meeting contents."""
from pathlib import Path
import hashlib
import json
import shutil
import threading
import requests


class ModelCatalog:
    def __init__(self, root):
        self.root = Path(root)
        entries = json.loads((self.root / 'models-catalog.json').read_text(encoding='utf-8'))
        self.entries = {entry['id']: entry for entry in entries}
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.thread = None
        self.download = None
        try:
            self.preferred = json.loads((self.root / 'settings.json').read_text(encoding='utf-8'))['llm_model']
        except (OSError, ValueError, KeyError):
            self.preferred = 'qwen25-14b'
        try:
            self.execution = json.loads((self.root / 'settings.json').read_text(encoding='utf-8')).get('execution', 'auto')
        except (OSError, ValueError):
            self.execution = 'auto'
        if self.execution not in ('auto', 'cpu', 'gpu'):
            self.execution = 'auto'

    def resolve_execution(self, execution=None):
        value = execution or self.execution
        if value not in ('auto', 'cpu', 'gpu'):
            raise ValueError('Mode de traitement invalide. Choisissez automatique, CPU ou GPU.')
        return value

    def set_execution(self, execution):
        value = self.resolve_execution(execution)
        with self.lock:
            self._save_setting('execution', value)
            self.execution = value

    def entry(self, model_id):
        if model_id not in self.entries:
            raise ValueError('Modèle inconnu. Choisissez un modèle du catalogue.')
        return self.entries[model_id]

    def path(self, model_id):
        return self.root / 'models' / self.entry(model_id)['filename']

    def installed(self, model_id):
        path = self.path(model_id)
        return path.is_file() and path.stat().st_size == self.entry(model_id)['size']

    def partial_size(self, model_id):
        try:
            return self.path(model_id).with_suffix('.gguf.part').stat().st_size
        except FileNotFoundError:
            return 0

    def default(self):
        if self.preferred in self.entries and self.installed(self.preferred):
            return self.preferred
        return next((mid for mid in self.entries if self.installed(mid)), 'qwen25-14b')

    def resolve(self, model_id=None, require_installed=True):
        mid = model_id or self.default()
        self.entry(mid)
        if require_installed and not self.installed(mid):
            raise ValueError('Ce modèle n’est pas installé. Téléchargez-le depuis le catalogue avant de l’utiliser.')
        return mid

    def set_default(self, model_id):
        mid = self.resolve(model_id)
        with self.lock:
            self._save_setting('llm_model', mid)
            self.preferred = mid

    def _save_setting(self, name, value):
        path = self.root / 'settings.json'
        try:
            settings = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            settings = {}
        settings[name] = value
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(path)

    def state(self):
        with self.lock:
            models = []
            for mid, entry in self.entries.items():
                if entry.get('legacy'):
                    continue
                models.append({**entry, 'installed': self.installed(mid),
                               'partial_bytes': self.partial_size(mid)})
            return {'models': models, 'default': self.default(), 'execution': self.execution,
                    'download': dict(self.download) if self.download else None}

    def update(self, **values):
        with self.lock:
            self.download.update(values)

    def start_download(self, model_id):
        entry = self.entry(model_id)
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise RuntimeError('Un téléchargement est déjà en cours.')
            if self.installed(model_id):
                return {'ok': True, 'installed': True}
            self.cancelled.clear()
            received = min(self.partial_size(model_id), entry['size'])
            self.download = {'model_id': model_id, 'status': 'downloading', 'received': received,
                             'total': entry['size'], 'progress': round(100 * received / entry['size'], 1),
                             'message': 'Reprise : connexion au dépôt…' if received else 'Connexion au dépôt…'}
            self.thread = threading.Thread(target=self._download, args=(model_id,), daemon=True)
            self.thread.start()
            return {'ok': True}

    def cancel_download(self):
        with self.lock:
            if not self.thread or not self.thread.is_alive():
                raise ValueError('Aucun téléchargement en cours.')
            self.cancelled.set()
            self.download['message'] = 'Arrêt du téléchargement…'

    def _download(self, model_id):
        entry = self.entry(model_id)
        target = self.path(model_id)
        part = target.with_suffix('.gguf.part')
        try:
            target.parent.mkdir(exist_ok=True)
            offset = part.stat().st_size if part.exists() else 0
            if offset > entry['size']:
                part.unlink()
                offset = 0
            if shutil.disk_usage(target.parent).free < entry['size'] - offset + 100 * 1024 * 1024:
                raise RuntimeError('Espace disque insuffisant pour ce modèle.')
            if offset < entry['size']:
                url = f"https://huggingface.co/{entry['repo']}/resolve/{entry['revision']}/{entry['filename']}"
                headers = {'User-Agent': 'Clair-local/1.1'}
                if offset:
                    headers['Range'] = f'bytes={offset}-'
                with requests.get(url, headers=headers, stream=True, timeout=(20, 30)) as response:
                    response.raise_for_status()
                    if response.status_code == 206:
                        if not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
                            raise RuntimeError('Le dépôt a renvoyé une reprise incohérente. Réessayez.')
                    else:
                        offset = 0
                    self.update(received=offset, progress=round(100 * offset / entry['size'], 1))
                    with part.open('ab' if offset else 'wb') as output:
                        for chunk in response.iter_content(4 * 1024 * 1024):
                            if self.cancelled.is_set():
                                self.update(status='cancelled', message='Téléchargement arrêté. La reprise est disponible.')
                                return
                            if not chunk:
                                continue
                            output.write(chunk)
                            offset += len(chunk)
                            if offset > entry['size']:
                                raise RuntimeError('Le fichier reçu dépasse la taille attendue.')
                            self.update(received=offset, progress=round(100 * offset / entry['size'], 1),
                                        message='Téléchargement du modèle…')
            self.update(status='verifying', message='Vérification SHA-256 du modèle…')
            digest = hashlib.sha256()
            with part.open('rb') as source:
                while block := source.read(8 * 1024 * 1024):
                    if self.cancelled.is_set():
                        self.update(status='cancelled', message='Vérification arrêtée. La reprise est disponible.')
                        return
                    digest.update(block)
            if part.stat().st_size != entry['size'] or digest.hexdigest() != entry['sha256']:
                part.unlink(missing_ok=True)
                raise RuntimeError('L’intégrité du modèle n’a pas pu être vérifiée. Relancez le téléchargement.')
            part.replace(target)
            self.update(status='done', progress=100, received=entry['size'], message='Modèle installé et vérifié.')
        except requests.RequestException:
            self.update(status='error', message='Connexion au dépôt interrompue. Vérifiez Internet et reprenez le téléchargement.')
        except Exception as error:
            self.update(status='error', message=str(error)[:500])

    def close(self):
        self.cancelled.set()

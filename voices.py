"""Local CPU diarization with sherpa-onnx, pyannote segmentation and 3D-Speaker."""
import hashlib
import importlib.util
from pathlib import Path
import shutil
import tarfile
import threading

import requests

ASSETS = (
    ('https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2',
     'segmentation.tar.bz2', 6958444, '24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488'),
    ('https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_eres2net_sv_en_voxceleb_16k.onnx',
     'embedding.onnx', 26485263, 'c59158379255ad66e161679cca6af8d52d51e389e3224ab7d7a7baae295c2db5'),
)
MODEL_FILES = {'segmentation.onnx': (5992913, '220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079'),
               'embedding.onnx': (26485263, 'c59158379255ad66e161679cca6af8d52d51e389e3224ab7d7a7baae295c2db5')}


def verified(path, size, sha):
    if not path.is_file() or path.stat().st_size != size:
        return False
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest() == sha


class VoiceEngine:
    def __init__(self, root):
        self.folder = Path(root) / 'models/diarization'
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.thread = None
        self.download = None

    def ready(self):
        return importlib.util.find_spec('sherpa_onnx') is not None and all(
            (self.folder / name).is_file() and (self.folder / name).stat().st_size == size
            for name, (size, _) in MODEL_FILES.items())

    def state(self):
        with self.lock:
            return {'installed': self.ready(), 'download': dict(self.download) if self.download else None,
                    'name': 'Pyannote segmentation 3.0 + 3D-Speaker ERes2Net (sherpa-onnx)',
                    'size': sum(a[2] for a in ASSETS)}

    def start_install(self):
        with self.lock:
            if importlib.util.find_spec('sherpa_onnx') is None:
                raise RuntimeError('Mettez les dépendances à jour avec Installer.cmd pour installer le moteur de voix.')
            if self.thread and self.thread.is_alive():
                return {'ok': True}
            self.cancelled.clear()
            self.download = {'status': 'downloading', 'progress': 0, 'message': 'Téléchargement des modèles de voix…'}
            self.thread = threading.Thread(target=self._install, daemon=True)
            self.thread.start()
            return {'ok': True}

    def _progress(self, **values):
        with self.lock:
            self.download.update(values)

    def _install(self):
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(self.folder).free < 100_000_000:
                raise RuntimeError('Prévoir au moins 100 Mo libres pour installer les modèles de voix.')
            total, received = sum(a[2] for a in ASSETS), 0
            for url, name, size, sha in ASSETS:
                path = self.folder / name
                if not verified(path, size, sha):
                    part = path.with_suffix(path.suffix + '.part')
                    with requests.get(url, stream=True, timeout=(10, 30)) as response:
                        response.raise_for_status()
                        count = 0
                        with part.open('wb') as output:
                            for block in response.iter_content(1024 * 1024):
                                if self.cancelled.is_set():
                                    self._progress(status='cancelled', message='Installation arrêtée. Vous pouvez la relancer.')
                                    return
                                count += len(block)
                                if count > size:
                                    raise RuntimeError('Le dépôt a renvoyé un modèle de voix de taille inattendue.')
                                output.write(block)
                                self._progress(progress=round(100 * (received + count) / total, 1))
                    if not verified(part, size, sha):
                        part.unlink(missing_ok=True)
                        raise RuntimeError('L’intégrité du modèle de voix n’a pas pu être vérifiée.')
                    part.replace(path)
                received += size
            # Read one known member, never extract archive paths onto the filesystem.
            with tarfile.open(self.folder / 'segmentation.tar.bz2', 'r:bz2') as archive:
                member = archive.getmember('sherpa-onnx-pyannote-segmentation-3-0/model.onnx')
                if not member.isfile() or member.size != MODEL_FILES['segmentation.onnx'][0]:
                    raise RuntimeError('Archive de segmentation inattendue.')
                target = self.folder / 'segmentation.tmp'
                with archive.extractfile(member) as source, target.open('wb') as output:
                    shutil.copyfileobj(source, output)
                if not verified(target, *MODEL_FILES['segmentation.onnx']):
                    target.unlink(missing_ok=True)
                    raise RuntimeError('Intégrité du modèle de segmentation invalide.')
                target.replace(self.folder / 'segmentation.onnx')
            self._progress(status='done', progress=100, message='Modèles de voix installés et vérifiés. Traitement local sur CPU.')
        except Exception as error:
            self._progress(status='error', message=str(error)[:300])

    def analyze(self, audio, count, cancelled, progress):
        if not self.ready():
            raise RuntimeError('Installez les modèles de voix dans le catalogue avant de lancer la détection.')
        for name, (size, sha) in MODEL_FILES.items():
            if not verified(self.folder / name, size, sha):
                raise RuntimeError('Modèle de voix altéré. Réinstallez les modèles depuis le catalogue.')
        import sherpa_onnx
        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                    model=str(self.folder / 'segmentation.onnx'), window_shift_ratio=0.1),
                num_threads=4, provider='cpu'),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(self.folder / 'embedding.onnx'), num_threads=4, provider='cpu'),
            clustering=sherpa_onnx.FastClusteringConfig(num_clusters=count or -1, threshold=0.9),
            min_duration_on=0.3, min_duration_off=0.5)
        if not config.validate():
            raise RuntimeError('Configuration du moteur de voix invalide.')
        engine = sherpa_onnx.OfflineSpeakerDiarization(config)
        def callback(done, total):
            progress(done / max(1, total))
            return 1 if cancelled.is_set() else 0
        result = engine.process(audio, callback=callback).sort_by_start_time()
        if cancelled.is_set():
            return [], []
        turns = [{'start': round(t.start, 3), 'end': round(t.end, 3), 'raw': t.speaker} for t in result]
        order = list(dict.fromkeys(t['raw'] for t in turns))
        for turn in turns:
            turn['voice'] = 'voice-' + str(order.index(turn.pop('raw')) + 1)
        voices = []
        for i, _ in enumerate(order, 1):
            selected = [t for t in turns if t['voice'] == f'voice-{i}']
            sample = max(selected, key=lambda t: t['end'] - t['start'])
            voices.append({'id': f'voice-{i}', 'label': f'Voix {i}', 'name': '',
                           'sample_start': sample['start'], 'sample_end': min(sample['end'], sample['start'] + 8),
                           'seconds': round(sum(t['end'] - t['start'] for t in selected), 1)})
        return turns, voices

    def close(self):
        self.cancelled.set()


def attribute_segments(segments, turns):
    """Conservative overlap mapping: mixed or weakly covered passages remain unassigned."""
    for segment in segments:
        segment.pop('speaker', None)
        segment.pop('speaker_manual', None)
        segment.pop('voice', None)
        segment.pop('voice_uncertain', None)
        scores = {}
        for turn in turns:
            overlap = max(0, min(segment['end'], turn['end']) - max(segment['start'], turn['start']))
            if overlap:
                scores[turn['voice']] = scores.get(turn['voice'], 0) + overlap
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        duration = max(.01, segment['end'] - segment['start'])
        if ranked and ranked[0][1] / duration >= .55 and (len(ranked) < 2 or ranked[1][1] / duration < .25):
            segment['voice'] = ranked[0][0]
        else:
            segment['voice_uncertain'] = True
    return segments


def split_at_voice_changes(segments, turns):
    """Word timestamps allow a Whisper paragraph containing several voices to be split."""
    output = []
    for segment in segments:
        words = segment.get('words', [])
        if not words:
            output.extend(attribute_segments([segment], turns))
            continue
        aligned = attribute_segments([{'start': w['start'], 'end': w['end'],
                                       'text': w['word'], 'words': [w]} for w in words], turns)
        groups = []
        for word in aligned:
            if groups and groups[-1].get('voice') == word.get('voice'):
                groups[-1]['end'] = word['end']
                groups[-1]['text'] += word['text']
                groups[-1]['words'] += word['words']
            else:
                groups.append(word)
        for group in groups:
            group['text'] = group['text'].strip()
            if group['text']:
                output.append(group)
    return output

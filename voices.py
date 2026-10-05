"""Local CPU/CUDA diarization and reference-based speaker matching."""
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tarfile
import tempfile
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
                    'size': sum(a[2] for a in ASSETS), 'gpu_available': self.gpu_available()}

    def gpu_available(self):
        try:
            if '+cuda12.cudnn9' not in importlib.metadata.version('sherpa-onnx'):
                return False
            import ctranslate2
            return ctranslate2.get_cuda_device_count() > 0
        except Exception:
            return False

    def provider(self, execution):
        if execution not in ('auto', 'cpu', 'gpu'):
            raise ValueError('Mode des voix invalide : automatique, CPU ou GPU.')
        if execution == 'cpu':
            return 'cpu'
        if self.gpu_available():
            return 'cuda'
        if execution == 'gpu':
            raise RuntimeError('GPU NVIDIA des voix indisponible. Lancez Installer.cmd pour mettre le moteur CUDA à jour, ou choisissez CPU.')
        return 'cpu'

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
            self._progress(status='done', progress=100, message='Modèles de voix installés et vérifiés. Traitement local CPU/GPU.')
        except Exception as error:
            self._progress(status='error', message=str(error)[:300])

    def analyze(self, audio, count, cancelled, progress, provider='cpu'):
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
                num_threads=4, provider=provider),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(self.folder / 'embedding.onnx'), num_threads=4, provider=provider),
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

    def identify(self, audio, references, turns, cancelled, progress, provider='cpu'):
        """Compare individual, non-overlapping turns to user-labelled audio excerpts."""
        import numpy as np
        import sherpa_onnx
        if not verified(self.folder / 'embedding.onnx', *MODEL_FILES['embedding.onnx']):
            raise RuntimeError('Modèle de voix absent ou altéré. Réinstallez-le depuis le catalogue.')
        extractor = sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(self.folder / 'embedding.onnx'), num_threads=4, provider=provider))

        def embed(start, end):
            samples = np.ascontiguousarray(audio[int(start * 16000):int(end * 16000)], dtype=np.float32)
            if len(samples) < 24000 or float(np.sqrt(np.mean(samples ** 2))) < .001:
                return None
            stream = extractor.create_stream()
            stream.accept_waveform(sample_rate=16000, waveform=samples)
            stream.input_finished()
            if not extractor.is_ready(stream):
                return None
            vector = np.asarray(extractor.compute(stream), dtype=np.float32)
            norm = np.linalg.norm(vector)
            return vector / norm if np.isfinite(vector).all() and norm > 0 else None

        enrolled = []
        for ref in references:
            if cancelled.is_set():
                return []
            vector = embed(ref['start'], ref['end'])
            if vector is None:
                raise ValueError('Un extrait de référence est trop silencieux. Choisissez un passage avec une seule personne qui parle clairement.')
            enrolled.append((ref['name'], vector))
        matched = []
        for i, turn in enumerate(turns):
            if cancelled.is_set():
                return []
            progress((i + 1) / max(1, len(turns)))
            # Crosstalk and very short turns do not provide a reliable voice sample.
            if any(other is not turn and other['voice'] != turn['voice'] and
                   min(other['end'], turn['end']) - max(other['start'], turn['start']) > .1 for other in turns):
                continue
            vector = embed(turn['start'], min(turn['end'], turn['start'] + 12))
            if vector is None:
                continue
            scores = {}
            for name, sample in enrolled:
                scores[name] = max(scores.get(name, -1), float(np.dot(vector, sample)))
            name, score = reference_match(scores)
            if name:
                matched.append({**turn, 'name': name, 'score': round(score, 3)})
        return matched

    def analyze_file(self, path, count, cancelled, progress, provider, references=None, turns=None, voices=None):
        """Fresh process avoids ONNX/CUDA DLL collisions with Whisper's VAD on Windows."""
        python = Path(sys.executable)
        if python.name.lower() == 'pythonw.exe':
            python = python.with_name('python.exe')
        payload = {'root': str(self.folder.parent.parent), 'audio': str(path), 'count': count,
                   'provider': provider, 'references': references, 'turns': turns, 'voices': voices}
        messages = queue.Queue()
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen([str(python), '-u', str(Path(__file__).resolve()), '--worker'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, text=True, encoding='utf-8', errors='replace',
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            def read():
                try:
                    for line in process.stdout:
                        messages.put(line)
                finally:
                    messages.put(None)
            reader = threading.Thread(target=read, daemon=True)
            reader.start()
            result, failure = None, None
            try:
                process.stdin.write(json.dumps(payload) + '\n')
                process.stdin.close()
                while True:
                    if cancelled.is_set():
                        return [], [], []
                    try:
                        line = messages.get(timeout=.1)
                    except queue.Empty:
                        continue
                    if line is None:
                        break
                    try:
                        message = json.loads(line)
                    except ValueError:
                        continue
                    if message.get('kind') == 'progress':
                        progress(message['ratio'])
                    elif message.get('kind') == 'result':
                        result = message
                    elif message.get('kind') == 'error':
                        failure = message['message']
                process.wait(timeout=10)
                if failure or process.returncode or result is None:
                    raise RuntimeError(failure or 'Le moteur des voix s’est arrêté. Réessayez sur CPU.')
                return result['turns'], result['voices'], result['matched']
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                reader.join(timeout=2)
                process.stdout.close()
                if not process.stdin.closed:
                    process.stdin.close()

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


def reference_match(scores, threshold=.65, margin=.10):
    """Cosine similarities are heuristic scores, never identity probabilities."""
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if not ranked or ranked[0][1] < threshold or (len(ranked) > 1 and ranked[0][1] - ranked[1][1] < margin):
        return '', 0
    return ranked[0]


def apply_reference_names(segments, matched):
    """Keep manual decisions and unrelated voice names; refresh reference attributions."""
    for segment in segments:
        if segment.get('speaker_manual'):
            continue
        if segment.pop('speaker_reference', False):
            segment.pop('speaker', None)
            segment.pop('speaker_score', None)
        scores = {}
        for turn in matched:
            overlap = max(0, min(segment['end'], turn['end']) - max(segment['start'], turn['start']))
            scores[turn['name']] = scores.get(turn['name'], 0) + overlap
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        duration = max(.01, segment['end'] - segment['start'])
        if ranked and ranked[0][1] / duration >= .55 and (len(ranked) < 2 or ranked[1][1] / duration < .25):
            segment.update(speaker=ranked[0][0], speaker_reference=True)
    return segments


def _worker():
    sys.stdout.reconfigure(encoding='utf-8')
    def emit(**message):
        print(json.dumps(message, ensure_ascii=False), flush=True)
    try:
        args = json.loads(sys.stdin.readline())
        root = Path(args['root'])
        handles = []
        for folder in (root / '.venv/Lib/site-packages/nvidia').glob('*/bin'):
            os.environ['PATH'] = str(folder) + os.pathsep + os.environ.get('PATH', '')
            if hasattr(os, 'add_dll_directory'):
                handles.append(os.add_dll_directory(str(folder)))
        from faster_whisper.audio import decode_audio
        audio = decode_audio(args['audio'], sampling_rate=16000)
        engine = VoiceEngine(root)
        cancelled = threading.Event()
        progress = lambda ratio: emit(kind='progress', ratio=ratio)
        turns, voices = args.get('turns'), args.get('voices')
        if not turns:
            turns, voices = engine.analyze(audio, args['count'], cancelled, progress, args['provider'])
        references = args.get('references')
        matched = engine.identify(audio, references, turns, cancelled, progress, args['provider']) if references else []
        emit(kind='result', turns=turns, voices=voices, matched=matched)
    except Exception as error:
        emit(kind='error', message=str(error)[:500])
        sys.exit(1)


if __name__ == '__main__' and '--worker' in sys.argv:
    _worker()

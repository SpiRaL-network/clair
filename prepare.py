"""Install local models and llama.cpp; never uploads meeting data."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
MODELS = ROOT / 'models'
BIN = ROOT / 'bin'

def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        print(f'Already present: {path.name}', flush=True)
        return
    tmp = path.with_suffix(path.suffix + '.part')
    req = urllib.request.Request(url, headers={'User-Agent': 'Clair-local/1.0'})
    with urllib.request.urlopen(req, timeout=120) as src, tmp.open('wb') as dest:
        total = int(src.headers.get('Content-Length', 0))
        done, last = 0, 0
        while chunk := src.read(4 * 1024 * 1024):
            dest.write(chunk)
            done += len(chunk)
            if done - last > 256 * 1024 * 1024:
                print(f'{path.name}: {done // 1048576} / {total // 1048576} MB', flush=True)
                last = done
    tmp.replace(path)
    print(f'Download complete: {path.name}', flush=True)

def whisper():
    from huggingface_hub import snapshot_download
    snapshot_download('Systran/faster-whisper-large-v3', local_dir=MODELS / 'whisper-large-v3',
                      allow_patterns=['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.json', 'preprocessor_config.json'])
    print('Whisper ready', flush=True)

def summary():
    import time
    from catalog import ModelCatalog
    catalog = ModelCatalog(ROOT)
    catalog.start_download('qwen35-4b')
    while catalog.thread and catalog.thread.is_alive():
        print(catalog.state()['download'], flush=True)
        time.sleep(10)
    if not catalog.installed('qwen35-4b'):
        raise RuntimeError(catalog.state()['download']['message'])
    catalog.set_default('qwen35-4b')

def engine():
    release = 'b11408'
    BIN.mkdir(parents=True, exist_ok=True)
    for kind, name in [('gpu', f'llama-{release}-bin-win-cuda-13.4-x64.zip'),
                       ('gpu', 'cudart-llama-bin-win-cuda-13.4-x64.zip'),
                       ('cpu', f'llama-{release}-bin-win-cpu-x64.zip')]:
        destination = BIN / kind
        destination.mkdir(exist_ok=True)
        archive = ROOT / 'downloads' / name
        download(f'https://github.com/ggml-org/llama.cpp/releases/download/{release}/{name}', archive)
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                target = (destination / entry.filename).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise ValueError('Unsafe archive path')
            z.extractall(destination)
    print('llama.cpp ready', flush=True)

def runtime():
    archive = ROOT / 'downloads/python-3.12.10-embed-amd64.zip'
    download('https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip', archive)
    dest = ROOT / 'runtime'
    dest.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        z.extractall(dest)
    (dest / 'python312._pth').write_text('python312.zip\n.\n..\n../.venv/Lib/site-packages\nimport site\n', encoding='utf-8')
    print('Standalone Python runtime ready', flush=True)

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(lambda f: f(), [whisper, summary, engine, runtime]):
            pass
    files = [p for p in MODELS.rglob('*') if p.is_file() and '.cache' not in p.parts]
    manifest = {}
    for p in files:
        with p.open('rb') as f:
            manifest[p.relative_to(ROOT).as_posix()] = hashlib.file_digest(f, 'sha256').hexdigest()
    (ROOT / 'model-checksums.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('All local models are ready.', flush=True)

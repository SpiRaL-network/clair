import json
import os
from pathlib import Path
import secrets
import threading
import time
import webbrowser

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel, Field
from core import ROOT, Studio

PORT = 8787
TOKEN = secrets.token_urlsafe(32)
studio = Studio()
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

@app.middleware('http')
async def local_only(request: Request, call_next):
    if request.headers.get('host') not in (f'127.0.0.1:{PORT}', f'localhost:{PORT}'):
        return JSONResponse({'detail': 'Hôte non autorisé.'}, status_code=403)
    origin = request.headers.get('origin')
    if origin and origin not in (f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}'):
        return JSONResponse({'detail': 'Origine non autorisée.'}, status_code=403)
    if request.url.path.startswith('/api/'):
        if not secrets.compare_digest(request.cookies.get('clair_session', ''), TOKEN):
            return JSONResponse({'detail': 'Ouvre l’application pour démarrer une session locale.'}, status_code=401)
        if request.method != 'GET' and not secrets.compare_digest(request.headers.get('x-clair-token', ''), TOKEN):
            return JSONResponse({'detail': 'Session invalide.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    return response

@app.exception_handler(RuntimeError)
async def runtime_error(request, error):
    return JSONResponse({'detail': str(error)}, status_code=409)

@app.exception_handler(ValueError)
async def value_error(request, error):
    return JSONResponse({'detail': str(error)}, status_code=400)

@app.exception_handler(FileNotFoundError)
async def missing(request, error):
    return JSONResponse({'detail': 'Fichier introuvable.'}, status_code=404)

@app.get('/', response_class=HTMLResponse)
def home():
    content = (ROOT / 'web/index.html').read_text(encoding='utf-8').replace('__TOKEN__', TOKEN)
    response = HTMLResponse(content)
    response.set_cookie('clair_session', TOKEN, httponly=True, samesite='strict')
    return response

@app.get('/app.js')
def javascript():
    return FileResponse(ROOT / 'web/app.js', media_type='application/javascript')

@app.get('/style.css')
def stylesheet():
    return FileResponse(ROOT / 'web/style.css', media_type='text/css')

@app.get('/api/state')
def state():
    return {'meetings': studio.listing(), 'active': studio.active, 'recording': studio.recorder.state(),
            'catalog': studio.catalog.state(),
            'models_ready': (ROOT / 'models/whisper-large-v3/model.bin').exists()
                             and any(studio.catalog.installed(mid) for mid in studio.catalog.entries)}

@app.get('/api/models')
def models():
    return studio.catalog.state()

@app.post('/api/models/{model_id}/download')
def download_model(model_id: str):
    return studio.catalog.start_download(model_id)

@app.post('/api/models/download/cancel')
def cancel_download():
    studio.catalog.cancel_download()
    return {'ok': True}

@app.post('/api/models/{model_id}/default')
def default_model(model_id: str):
    studio.catalog.set_default(model_id)
    return {'ok': True}

class ExecutionRequest(BaseModel):
    execution: str

@app.post('/api/preferences')
def preferences(body: ExecutionRequest):
    studio.catalog.set_execution(body.execution)
    return {'ok': True}

@app.get('/api/devices')
def devices():
    return studio.recorder.devices()

MEDIA_SUFFIXES = {'.mp4', '.mkv', '.mov', '.webm', '.avi', '.mp3', '.wav', '.m4a',
                  '.flac', '.ogg', '.wma', '.aac', '.wmv'}

@app.post('/api/import-upload')
async def import_upload(request: Request, filename: str = Query(max_length=255),
                        title: str = Query(default='', max_length=160), language: str = 'auto',
                        context: str = Query(default='', max_length=3000), auto_summary: bool = True,
                        llm_model: str = '', execution: str = ''):
    # Browser-selected files are copied over loopback in chunks, never loaded wholly into RAM.
    filename = Path(filename.replace('\\', '/')).name
    suffix = Path(filename).suffix.lower()
    if suffix not in MEDIA_SUFFIXES:
        raise ValueError('Format non pris en charge. Utilise un fichier audio ou vidéo.')
    if language not in ('fr', 'en', 'auto'):
        raise ValueError('Langue invalide.')
    llm_model = studio.catalog.resolve(llm_model, require_installed=auto_summary)
    execution = studio.catalog.resolve_execution(execution)
    with studio.lock:
        if studio.active or studio.recorder.streams:
            raise RuntimeError('Un traitement ou un enregistrement est déjà en cours.')
    staging = ROOT / '.imports'
    staging.mkdir(exist_ok=True)
    path = staging / (secrets.token_hex(16) + suffix)
    try:
        size = 0
        with path.open('xb') as output:
            async for chunk in request.stream():
                output.write(chunk)
                size += len(chunk)
        if not size:
            raise ValueError('Le fichier sélectionné est vide.')
        with studio.lock:
            if studio.active or studio.recorder.streams:
                raise RuntimeError('Un traitement ou un enregistrement est déjà en cours.')
            m = studio.create(title or Path(filename).stem, path, language, context, auto_summary, llm_model, execution)
            source = studio.folder(m['id']) / ('source' + suffix)
            path.replace(source)
            m = studio.update(m['id'], source=str(source))
            studio.launch(m['id'])
            return m
    except OSError as error:
        raise RuntimeError('Impossible de copier le fichier. Vérifiez l’espace disque disponible.') from error
    finally:
        path.unlink(missing_ok=True)

class ImportRequest(BaseModel):
    path: str
    title: str = ''
    language: str = 'auto'
    context: str = Field(default='', max_length=3000)
    auto_summary: bool = True
    llm_model: str = ''
    execution: str = ''

@app.post('/api/import')
def import_file(body: ImportRequest):
    with studio.lock:
        if studio.active or studio.recorder.streams:
            raise RuntimeError('Un traitement ou un enregistrement est déjà en cours.')
        path = Path(body.path.strip().strip('"')).expanduser().resolve()
        if not path.is_file():
            raise ValueError('Ce fichier est introuvable. Sélectionne une vidéo ou un fichier audio.')
        if path.suffix.lower() not in MEDIA_SUFFIXES:
            raise ValueError('Format non pris en charge. Utilise un fichier audio ou vidéo.')
        if body.language not in ('fr', 'en', 'auto'):
            raise ValueError('Langue invalide.')
        m = studio.create(body.title or path.stem, path, body.language, body.context, body.auto_summary, body.llm_model, body.execution)
        studio.launch(m['id'])
        return m

@app.get('/api/meetings/{mid}')
def meeting(mid: str):
    return studio.read(mid)

class RetryRequest(BaseModel):
    summary_only: bool = False
    llm_model: str | None = None
    execution: str | None = None

@app.post('/api/meetings/{mid}/retry')
def retry(mid: str, body: RetryRequest):
    m = studio.read(mid)
    if body.summary_only and not m['segments']:
        raise ValueError('Aucune transcription disponible.')
    # Recover captured tracks after an interruption before the mix was written.
    mix = not body.summary_only and not Path(m['source']).is_file() and any((studio.folder(mid) / name).exists() for name in ('system.wav', 'mic.wav'))
    if mix:
        studio.recorder.folder = studio.folder(mid)
    studio.launch(mid, summary_only=body.summary_only, mix=mix, llm_model=body.llm_model, execution=body.execution)
    return {'ok': True}

@app.post('/api/meetings/{mid}/cancel')
def cancel(mid: str):
    studio.cancel(mid)
    return {'ok': True}

@app.get('/api/meetings/{mid}/export/{name}')
def export(mid: str, name: str):
    if name not in ('transcription.txt', 'sous-titres.srt', 'compte-rendu.md', 'compte-rendu.json'):
        raise HTTPException(404)
    path = studio.folder(mid) / name
    if not path.is_file():
        raise HTTPException(404, 'Cet export n’est pas encore disponible.')
    return FileResponse(path, filename=name)

@app.get('/api/meetings/{mid}/audio')
def audio(mid: str):
    path = studio.folder(mid) / 'audio.wav'
    if not path.is_file():
        raise HTTPException(404, 'Audio en cours de préparation.')
    return FileResponse(path, media_type='audio/wav')

class RecordingRequest(BaseModel):
    title: str = 'Réunion Teams'
    system_id: int | None = None
    mic_id: int | None = None
    language: str = 'auto'
    context: str = Field(default='', max_length=3000)
    llm_model: str = ''
    execution: str = ''

@app.post('/api/record/start')
def record_start(body: RecordingRequest):
    if body.language not in ('fr', 'en', 'auto'):
        raise ValueError('Langue invalide.')
    return studio.start_recording(body.title, body.system_id, body.mic_id, body.language, body.context, body.llm_model, body.execution)

@app.post('/api/record/stop')
def record_stop():
    return studio.stop_recording()

@app.post('/api/folder')
def open_folder():
    os.startfile(str(ROOT / 'reunions'))
    return {'ok': True}

@app.post('/api/shutdown')
def shutdown():
    if studio.active or studio.recorder.streams:
        raise RuntimeError('Arrête l’enregistrement ou annule le traitement avant de quitter.')
    def leave():
        time.sleep(.4)
        studio.close()
        os._exit(0)
    threading.Thread(target=leave, daemon=True).start()
    return {'ok': True}

if __name__ == '__main__':
    import sys
    import uvicorn
    if '--no-browser' not in sys.argv:
        threading.Timer(1.5, lambda: webbrowser.open(f'http://127.0.0.1:{PORT}')).start()
    uvicorn.run(app, host='127.0.0.1', port=PORT, log_level='warning')

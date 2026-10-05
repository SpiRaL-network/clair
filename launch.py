"""Double-click launcher with visible diagnostics, and no dependency on Codex."""
import ctypes
from pathlib import Path
import subprocess
import sys
import urllib.request
import webbrowser

root = Path(__file__).resolve().parent
try:
    try:
        with urllib.request.urlopen('http://127.0.0.1:8787/',timeout=2) as r:
            content=r.read().decode('utf-8')
        if '<title>Clair' in content:
            webbrowser.open('http://127.0.0.1:8787/')
            raise SystemExit(0)
    except (OSError,ValueError):
        pass
    with (root/'service.log').open('a',encoding='utf-8') as log:
        process=subprocess.Popen([sys.executable,str(root/'app.py')],cwd=root,stdout=log,stderr=log,
                                 creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        code=process.wait()
    if code:
        ctypes.windll.user32.MessageBoxW(0,'Clair n’a pas pu démarrer. Consultez service.log dans le dossier de l’application, ou relancez Installer.cmd.','Clair',0x10)
except SystemExit:
    pass
except Exception as error:
    ctypes.windll.user32.MessageBoxW(0,str(error),'Clair — démarrage impossible',0x10)

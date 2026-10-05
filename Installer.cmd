@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Installation de Clair et de ses modeles locaux.
echo Prevoir environ 20 Go d'espace disque et une connexion Internet.
if exist ".venv\Scripts\python.exe" goto dependencies
py -3.12 -m venv .venv
if not errorlevel 1 goto dependencies
echo Python 3.12 est necessaire. Installez-le depuis python.org puis relancez ce fichier.
pause
exit /b 1
:dependencies
".venv\Scripts\python.exe" -m pip install -r requirements.lock.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" prepare.py
if errorlevel 1 goto failed
echo Installation terminee. Lancez Lancer.cmd.
pause
exit /b 0
:failed
echo L'installation a echoue. Le message ci-dessus indique la cause.
pause
exit /b 1

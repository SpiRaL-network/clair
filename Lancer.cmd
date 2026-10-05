@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "runtime\pythonw.exe" (
  echo Clair n'est pas encore installe. Lancez Installer.cmd.
  pause
  exit /b 1
)
start "" /b "runtime\pythonw.exe" "launch.py"
exit /b 0

@echo off
setlocal
title GTV - Game Trainer Vault
cd /d "%~dp0"

REM GTV is for OFFLINE single-player games only.
REM This window only prepares things, then it closes itself.
REM GTV itself is started with pythonw.exe, a Windows GUI program, so cmd does
REM NOT wait for it - GTV becomes an independent process and stays alive
REM even after this console window is closed.

set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"
set "PYW=%VENV%\Scripts\pythonw.exe"
set "LOG=%APPDATA%\GameTrainerVault\logs\gtv.log"

echo [GTV] Preparing environment ...

if not exist "%PY%" goto create_venv
goto check_deps

:create_venv
echo [GTV] First run - creating virtual environment ...
python -m venv "%VENV%"
if errorlevel 1 goto venv_failed

:check_deps
if exist "%VENV%\Lib\site-packages\PySide6\__init__.py" goto launch
"%PY%" -c "import PySide6" >nul 2>nul
if not errorlevel 1 goto launch
goto install_deps

:install_deps
echo [GTV] Installing dependencies - this may take a few minutes, once ...
"%PY%" -m pip install --upgrade pip -q
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto install_failed

:launch
echo [GTV] Launching GTV - this window will close automatically
if not exist "%PYW%" set "PYW=%PY%"
"%PYW%" -m gtv.boot
timeout /t 4 /nobreak >nul
tasklist /FI "IMAGENAME eq pythonw.exe" /NH 2>nul | find /I "pythonw.exe" >nul
if not errorlevel 1 goto running
tasklist /FI "IMAGENAME eq python.exe" /NH 2>nul | find /I "python.exe" >nul
if not errorlevel 1 goto running
echo [GTV] WARNING: GTV does not seem to be running.
echo [GTV] Please check the log file:
echo [GTV] %LOG%
echo [GTV] You can also try one of these directly:
echo [GTV]   python -m gtv.boot
echo [GTV]   GTV.vbs
pause
goto endscript

:running
echo [GTV] GTV is running - this window will close now
timeout /t 2 /nobreak >nul
goto endscript

:venv_failed
echo [GTV] ERROR: failed to create the virtual environment.
echo [GTV] Make sure Python is installed and available on PATH.
pause
goto endscript

:install_failed
echo [GTV] ERROR: failed to install dependencies - check your network.
echo [GTV] If the network is slow, install manually with this command:
echo [GTV]   "%PY%" -m pip install -r requirements.txt
pause
goto endscript

:endscript
endlocal

@echo off
setlocal
title GTV - Game Trainer Vault
cd /d "%~dp0"

REM GTV is for OFFLINE single-player games only.

set "VENV=.venv"

if not exist "%VENV%\Scripts\python.exe" (
    echo [GTV] First run: creating virtual environment ...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [GTV] ERROR: failed to create venv. Is Python installed and on PATH?
        pause
        exit /b 1
    )
)

set "PY=%VENV%\Scripts\python.exe"

"%PY%" -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo [GTV] Installing dependencies, please wait ...
    "%PY%" -m pip install --upgrade pip -q
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [GTV] ERROR: dependency install failed. Check network and retry.
        pause
        exit /b 1
    )
)

echo [GTV] Starting ...
"%PY%" -m gtv.main
if errorlevel 1 (
    echo [GTV] Exited with error. Log: %%APPDATA%%\GameTrainerVault\logs\gtv.log
    pause
)
endlocal

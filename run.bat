@echo off
chcp 65001 >nul
title GTV - Game Trainer Vault
cd /d "%~dp0"

REM 仅用于单机/离线游戏的修改器管理，请勿用于任何联机模式。

set "VENV=.venv"
if not exist "%VENV%\Scripts\python.exe" (
    echo [GTV] 首次运行，正在创建虚拟环境...
    python -m venv "%VENV%"
)

set "PY=%VENV%\Scripts\python.exe"
"%PY%" -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo [GTV] 正在安装依赖，请稍候（首次较慢）...
    "%PY%" -m pip install --upgrade pip -q
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [GTV] 依赖安装失败，请检查网络后重试。
        pause
        exit /b 1
    )
)

echo [GTV] 启动中...
"%PY%" -m gtv.main
if errorlevel 1 (
    echo [GTV] 运行出错，日志见 %%APPDATA%%\GameTrainerVault\logs\gtv.log
    pause
)

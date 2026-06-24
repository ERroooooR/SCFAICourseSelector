@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

cd /d "%~dp0"
title SCFAI Course Selector

:: Auto-setup if venv missing
if not exist "venv\Scripts\activate" (
    echo venv not found, running setup...
    echo.
    call "%~dp0setup.bat"
    if not exist "venv\Scripts\activate" (
        echo [ERROR] Setup failed.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate
echo venv activated.

if not exist "main.py" (
    echo [ERROR] main.py not found.
    pause
    exit /b 1
)

python main.py

pause

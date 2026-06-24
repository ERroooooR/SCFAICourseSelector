@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

cd /d "%~dp0"
title SCFAI Course Selector - Setup

echo.
echo ============================================
echo    SCFAI Course Selector - Setup
echo ============================================
echo.

:: ---- 1. Check Python ----
echo [1/6] Checking Python...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.8+ first.
    echo         https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%V in ('python --version 2^>^&1') do (
    echo        Python %%V detected.
)

:: ---- 2. Check Chrome ----
echo.
echo [2/6] Checking Chrome browser...
where chrome >nul 2>&1
if %errorlevel% equ 0 (
    echo        Chrome found in PATH.
) else (
    if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
        echo        Chrome found in Program Files.
    ) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
        echo        Chrome found in Program Files (x86).
    ) else if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
        echo        Chrome found in LocalAppData.
    ) else (
        echo        [WARN] Chrome not found!
        echo        Please install: https://www.google.com/chrome/
        echo        Or set google_path manually in main.py
    )
)

:: ---- 3. Create venv ----
echo.
echo [3/6] Setting up virtual environment...
if exist "venv\Scripts\activate" (
    echo        venv already exists, skip.
) else (
    echo        Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
    echo        venv created.
)

call venv\Scripts\activate
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate venv.
    pause
    exit /b 1
)

:: ---- 4. Install dependencies ----
echo.
echo [4/6] Installing dependencies (Tsinghua mirror)...
python -m pip install --upgrade pip -q -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
if %errorlevel% neq 0 (
    echo [WARN] Dependency install may have failed. Check network.
) else (
    echo        Dependencies installed.
)

:: ---- 5. Download ChromeDriver ----
echo.
echo [5/6] Preparing ChromeDriver...
python updateDriver.py
if %errorlevel% neq 0 (
    echo [WARN] ChromeDriver download failed.
    echo        You can retry: python updateDriver.py
) else (
    echo        ChromeDriver ready.
)

:: ---- 6. Done ----
echo.
echo [6/6] Setup complete!
echo.
echo ============================================
echo    Run: run_app_in_venv_windows.bat
echo ============================================
echo.

pause

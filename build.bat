@echo off
chcp 65001 > nul

REM Compare App - Windows Build Script
REM Requirements: Python 3.11+ installed

echo ================================
echo  Compare App - Build
echo ================================
echo.

REM Check Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.11+
    echo         https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
python -m pip install -r requirements.txt pyinstaller --upgrade
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Building executable...
python -m PyInstaller Compare.spec --clean
if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Done!
echo Output: dist\Compare.exe
echo.
pause

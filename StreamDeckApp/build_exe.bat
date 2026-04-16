@echo off
title Streamer Tablet Helper - Build EXE
echo.
echo  Building Streamer Tablet Helper...
echo  This takes about 1-2 minutes the first time.
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Install from https://python.org
    pause & exit /b 1
)

:: Install required packages
echo  Installing dependencies...
pip install pyinstaller pyautogui pystray pillow websocket-client --quiet

:: Build
echo  Building EXE...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "StreamerTabletHelper" ^
    streamer_helper_server.py

if errorlevel 1 (
    echo.
    echo  Build failed. See error above.
    pause & exit /b 1
)

echo.
echo  =========================================
echo   Done!  Your EXE is in the dist/ folder:
echo   dist\StreamerTabletHelper.exe
echo  =========================================
echo.
echo  Copy StreamerTabletHelper.exe wherever you like.
echo  Double-click it to run - no Python needed.
echo.
pause

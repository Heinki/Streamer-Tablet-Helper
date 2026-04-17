@echo off
setlocal enabledelayedexpansion
title Streamer Tablet Helper - Setup and Build
echo.
echo  --------------------------------------------------
echo  Streamer Tablet Helper - Setup and Build
echo  --------------------------------------------------
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python is not installed or not in your PATH.
    echo.
    echo  To fix this:
    echo  1. Visit https://www.python.org/downloads/
    echo  2. Download and run the installer for Windows.
    echo  3. IMPORTANT: Check the box "Add Python to PATH" during installation.
    echo  4. Restart this script after installation.
    echo.
    pause
    exit /b 1
)

:: Ensure pip is up to date
echo  Checking for required tools...
python -m pip install --upgrade pip

:: Install required packages
echo  Installing dependencies (this may take a minute)...
python -m pip install pyinstaller pyautogui pystray pillow websocket-client customtkinter

:: Build the EXE
echo  Building application...
pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --icon="Streamer Tablet Helper.png" ^
    --name "StreamerTabletHelper" ^
    --collect-all customtkinter ^
    streamer_helper_server.py

if errorlevel 1 (
    echo.
    echo  ERROR: Build failed. Please check the messages above.
    pause
    exit /b 1
)

echo.
echo  ==================================================
echo   SUCCESS!
echo   Your application is ready in the "dist" folder:
echo   dist\StreamerTabletHelper.exe
echo  ==================================================
echo.
echo  You can now move StreamerTabletHelper.exe anywhere.
echo  Double-click it to start the server.
echo.
pause

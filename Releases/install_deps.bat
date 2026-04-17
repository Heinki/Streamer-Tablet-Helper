@echo off
title Install Dependencies
echo Installing Streamer Tablet Helper dependencies...
echo.
pip install pyautogui pystray pillow websocket-client
echo.
echo Done! You can now run streamer_helper_server.py
pause

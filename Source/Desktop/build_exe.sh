#!/usr/bin/env bash
# macOS / Linux build script
set -e
echo "Installing dependencies..."
pip install pyinstaller pyautogui pystray pillow websocket-client

echo "Building..."
pyinstaller \
    --onefile \
    --windowed \
    --name "StreamerTabletHelper" \
    streamer_helper_server.py

echo ""
echo "Done! Binary is at dist/StreamerTabletHelper"

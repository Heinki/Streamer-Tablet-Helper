# Streamer Tablet Helper - PC Server

This application acts as a bridge between your mobile device and your PC, allowing you to control OBS, trigger Twitch markers, and simulate keyboard shortcuts from your tablet.

## Installation for Users

If you have been provided with the `StreamerTabletHelper.exe` file:

1. Copy `StreamerTabletHelper.exe` to a folder on your computer.
2. Double-click the file to run it.
3. If Windows Defender shows a warning, click "More info" and then "Run anyway" (this happens because the app is not digitally signed).

## Installation for Developers / Building from Source

If you have the source code and want to build the executable yourself:

1. Install Python from python.org.
   - IMPORTANT: Check the box "Add Python to PATH" during installation.
2. Open the project folder.
3. Double-click `build_exe.bat`.
   - This script will automatically install all necessary libraries (customtkinter, pyinstaller, etc.).
   - It will create a `dist` folder containing the `StreamerTabletHelper.exe`.

## Usage

### 1. Connecting the App

- When you run the server, it will display your "PC IP".
- Enter this IP address into the Streamer Tablet Helper app on your mobile device.
- The status light for "Server" should turn green.

### 2. OBS Setup

- Open OBS Studio.
- Go to Tools -> WebSocket Server Settings.
- Ensure "Enable WebSocket Server" is checked.
- Note the Port (usually 4455) and the Password.
- In the PC Helper app, go to the Settings tab and enter the OBS Port and Password.
- Click "Save OBS Settings" and then "Test Connection".

### 3. Twitch Setup (Stream Markers)

- Go to the Settings tab in the PC Helper app.
- Click "Open Token Generator".
- Follow the instructions on the website to generate a token (ensure you select the `channel:manage:broadcast` scope).
- Copy the Access Token and Client ID into the PC Helper app.
- Click "Save & Test Twitch".

### 4. Keyboard Shortcuts

- The app can simulate key presses (e.g., F13-F24) which you can bind to actions in OBS or other streaming software.
- Ensure the app has permissions to simulate keys if prompted by your antivirus or OS.

## Troubleshooting

### Connection Refused (WinError 10061)

- This usually means OBS is not open or the WebSocket server is not enabled in OBS.
- Check that the Port in the Helper app matches the Port in OBS (default is 4455).

### IP Address Not Found

- Ensure both your PC and your mobile device are on the same Wi-Fi network.
- Check your firewall settings to ensure port 7878 is not being blocked.

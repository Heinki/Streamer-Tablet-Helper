# Streamer Tablet Helper

Control your PC, OBS, and Twitch stream directly from your Android tablet or phone! This project provides a bridge between your mobile device and your PC, allowing you to trigger actions, simulate keys, and more.

---

## **Quick Start (For Users)**

If you just want to use the project, everything you need is in the [Releases](Releases/) folder.

1.  **Android App**: Download [StreamerTabletHelper.apk](Releases/StreamerTabletHelper.apk) and install it on your Android device.
2.  **PC Server**: Download [StreamerTabletHelper.exe](Releases/StreamerTabletHelper.exe) and run it on your Windows PC.
    - _Note: If Windows Defender shows a warning, click "More info" and then "Run anyway" (this happens because the app is not digitally signed)._
3.  **Connect**:
    - Run the PC Server to find your **PC IP**.
    - Enter this IP address into the Android App on your device.
    - The status light for "Server" should turn green!

---

## **Project Structure**

The project is organized to keep things simple for users while maintaining full technical access for developers.

- **[Releases/](Releases/)**: Contains ready-to-use binaries (APK and EXE) for immediate installation.
- **[Source/](Source/)**: Contains the full source code for the project.
  - **[Source/Android/](Source/Android/)**: The Android application (Java/Android Studio).
  - **[Source/Desktop/](Source/Desktop/)**: The PC Server application (Python/PyInstaller).

---

## **Developer Guide / Building from Source**

If you want to modify the project or build the executables yourself:

### **PC Server (Desktop)**

1.  Go to [Source/Desktop/](Source/Desktop/).
2.  Install Python from [python.org](https://www.python.org/).
    - **IMPORTANT**: Check the box "Add Python to PATH" during installation.
3.  Run `install_deps.bat` to install all necessary libraries.
4.  Run `build_exe.bat` to generate your own `StreamerTabletHelper.exe`.

### **Android App**

1.  Go to [Source/Android/](Source/Android/).
2.  Open the project in **Android Studio**.
3.  Build the APK using `Build > Build Bundle(s) / APK(s) > Build APK(s)`.

---

## **Setup & Features**

### **1. OBS Setup**

- Open OBS Studio.
- Go to `Tools > WebSocket Server Settings`.
- Ensure **"Enable WebSocket Server"** is checked.
- Note the Port (usually 4455) and the Password.
- In the PC Helper app, enter these details in the **Settings** tab.

### **2. Twitch Setup (Stream Markers)**

- Go to the **Settings** tab in the PC Helper app.
- Click **"Open Token Generator"**.
- Follow the instructions to generate a token (select the `channel:manage:broadcast` scope).
- Copy the Access Token and Client ID into the PC Helper app.

---

## **Troubleshooting**

- **Connection Refused**: Ensure OBS is open and the WebSocket server is enabled.
- **IP Not Found**: Ensure both PC and mobile device are on the **same Wi-Fi network**.
- **Firewall**: Check that port `7878` is not blocked on your PC.

---

_Happy Streaming!_

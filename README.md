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

### **1. Keyboard Shortcuts (Keys)**

- On your Android app, add or edit a button.
- Set the **Type** to **Keys**.
- Enter the key combination separated by commas (e.g., `ctrl, alt, 0`).
- When pressed, the PC will simulate these keys as if they were pressed on your keyboard.

### **2. Sound Alerts (Sound)**

- Set the **Type** to **Sound**.
- Enter the **Full Path** to your sound file on the PC (e.g., `C:\Users\Name\Desktop\sound.wav`).
- **Requirement**: Currently only supports **.wav** files for background playback.
- The sound plays through your default PC audio device and is captured by OBS "Desktop Audio".

### **3. OBS Setup**

- Open OBS Studio.
- Go to `Tools > WebSocket Server Settings`.
- Ensure **"Enable WebSocket Server"** is checked.
- Note the Port (usually 4455) and the Password.
- In the PC Helper app, enter these details in the **Settings** tab.
- You can then use the **OBS** button type to:
  - Change Scenes
  - Start/Stop Streaming or Recording
  - Toggle Mute or set Volume for any source.

### **4. Twitch Setup (Stream Markers & Ads)**

- Go to the **Settings** tab in the PC Helper app.
- Click **"Open Token Generator"**.
- Follow the instructions to generate a token.
  - **Markers**: Check the `channel:manage:broadcast` scope.
  - **Ads**: Check the `channel:edit:commercial` scope.
- Copy the Access Token and Client ID into the PC Helper app.
- Use the **Twitch** button type to:
  - Create stream markers with optional descriptions.
  - Run commercials (30, 60, 90, 120, 150, or 180 seconds).

---

## **Troubleshooting**

- **Connection Refused**: Ensure OBS is open and the WebSocket server is enabled.
- **IP Not Found**: Ensure both PC and mobile device are on the **same Wi-Fi network**.
- **Firewall**: Check that port `7878` is not blocked on your PC.

---

## **FAQ**

**1. Why did you make this?**

I don't have a Streamdeck but I liked the idea, I have an old Tablet that is just collecting dust, so I wanted to use this! and here we are!

**2. Did you code this?**

Most of it is "vibe coded" as I have no knowledge of working with Android, Python. I also wanted to get something "working" quickly.

**3. Wow this is trash! You did not _insert feature here_ in this app!**

Sorry, I just mostly wanted to get my needs in here, but I'm willing to add more features/suggestion!

**4. You suck since you Vibe coded this app!**

That is not a question!

**5. Can I suggest something or work on this?**

This is Open Source, you can open a PR for improvements, open issue or just fork it yourself and upgrade it however you want!

**6. Feature X is not working!?**

Open an Issue and I will take a look!

---

## **License**

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

You are free to use, modify, and distribute this software for any purpose, commercial or personal, with or without modifications.

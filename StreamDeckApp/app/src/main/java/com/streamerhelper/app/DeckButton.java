package com.streamerhelper.app;

public class DeckButton {
    public String id;
    public String icon;
    public String label;

    // type: "keys" | "sound" | "obs"
    public String type;

    // type == "keys"
    public String keys;

    // type == "sound"
    public String sound;

    // type == "obs"
    public String obsCommand; // e.g. "SetCurrentProgramScene", "StartStream" …
    public String obsScene;
    public String obsSource;
    public float  obsVolume = -1f; // -1 = not used

    // UX options
    public String  color       = "#00e5ff";
    public boolean confirmTap  = false; // require double-tap for safety
    public boolean haptic      = true;  // vibrate on press
    public int     widthSpan   = 1;     // 1 = normal, 2 = double-wide

    public DeckButton() {}

    public DeckButton(String id, String icon, String label,
                      String type, String keys, String sound, String color) {
        this.id    = id;
        this.icon  = icon;
        this.label = label;
        this.type  = type;
        this.keys  = keys;
        this.sound = sound;
        this.color = color;
    }
}

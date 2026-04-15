package com.streamerhelper.app;

public class DeckButton {
    public String id;
    public String icon;
    public String label;

    // type: "keys" | "sound" | "obs" | "twitch"
    public String type;

    // type == "keys"
    public String keys;

    // type == "sound"
    public String sound;

    // type == "obs"
    public String obsCommand;
    public String obsScene;
    public String obsSource;
    public float  obsVolume = -1f;

    // type == "twitch"
    public String twitchCommand;    // e.g. "marker"
    public String twitchDescription; // optional marker description (max 140 chars)

    // UX options
    public String  color      = "#00e5ff";
    public boolean confirmTap = false;
    public boolean haptic     = true;
    public int     widthSpan  = 1;

    public DeckButton() {}

    public DeckButton(String id, String icon, String label,
                      String type, String keys, String sound, String color) {
        this.id    = id;   this.icon  = icon;  this.label = label;
        this.type  = type; this.keys  = keys;  this.sound = sound;
        this.color = color;
    }
}

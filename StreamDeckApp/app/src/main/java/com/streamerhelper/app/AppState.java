package com.streamerhelper.app;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public class AppState {
    private static final String PREFS     = "sth_prefs";
    private static final String KEY_IP    = "server_ip";
    private static final String KEY_PAGES = "pages_json";

    private static AppState instance;
    private final SharedPreferences prefs;

    public List<DeckPage> pages;
    public String serverIp;

    private AppState(Context ctx) {
        prefs    = ctx.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        serverIp = prefs.getString(KEY_IP, "");
        pages    = loadPages();
    }

    public static AppState get(Context ctx) {
        if (instance == null) instance = new AppState(ctx);
        return instance;
    }

    private List<DeckPage> loadPages() {
        String json = prefs.getString(KEY_PAGES, null);
        if (json != null) {
            try {
                JSONArray arr = new JSONArray(json);
                List<DeckPage> result = new ArrayList<>(arr.length());
                for (int i = 0; i < arr.length(); i++)
                    result.add(pageFromJson(arr.getJSONObject(i)));
                if (!result.isEmpty()) return result;
            } catch (Exception ignored) {}
        }
        return defaultPages();
    }

    public void save() {
        try {
            JSONArray arr = new JSONArray();
            for (DeckPage p : pages) arr.put(pageToJson(p));
            prefs.edit().putString(KEY_IP, serverIp).putString(KEY_PAGES, arr.toString()).apply();
        } catch (Exception ignored) {}
    }

    private JSONObject pageToJson(DeckPage p) throws Exception {
        JSONObject o = new JSONObject();
        o.put("name", p.name);
        JSONArray btns = new JSONArray();
        for (DeckButton b : p.buttons) btns.put(btnToJson(b));
        o.put("buttons", btns);
        return o;
    }

    private DeckPage pageFromJson(JSONObject o) throws Exception {
        DeckPage p = new DeckPage(o.getString("name"));
        JSONArray btns = o.getJSONArray("buttons");
        for (int i = 0; i < btns.length(); i++)
            p.buttons.add(btnFromJson(btns.getJSONObject(i)));
        return p;
    }

    private JSONObject btnToJson(DeckButton b) throws Exception {
        JSONObject o = new JSONObject();
        o.put("id",                b.id);
        o.put("icon",              b.icon);
        o.put("label",             b.label);
        o.put("type",              b.type);
        o.put("keys",              b.keys);
        o.put("sound",             b.sound);
        o.put("color",             b.color);
        o.put("confirmTap",        b.confirmTap);
        o.put("haptic",            b.haptic);
        o.put("widthSpan",         b.widthSpan);
        o.put("obsCommand",        b.obsCommand);
        o.put("obsScene",          b.obsScene);
        o.put("obsSource",         b.obsSource);
        o.put("obsVolume",         b.obsVolume);
        o.put("twitchCommand",     b.twitchCommand);
        o.put("twitchDescription", b.twitchDescription);
        return o;
    }

    private DeckButton btnFromJson(JSONObject o) throws Exception {
        DeckButton b = new DeckButton();
        b.id               = o.optString("id",                uid());
        b.icon             = o.optString("icon",              "▶");
        b.label            = o.optString("label",             "Button");
        b.type             = o.optString("type",              "keys");
        b.keys             = o.optString("keys",              "");
        b.sound            = o.optString("sound",             "");
        b.color            = o.optString("color",             "#00e5ff");
        b.confirmTap       = o.optBoolean("confirmTap",       false);
        b.haptic           = o.optBoolean("haptic",           true);
        b.widthSpan        = o.optInt("widthSpan",            1);
        b.obsCommand       = o.optString("obsCommand",        "");
        b.obsScene         = o.optString("obsScene",          "");
        b.obsSource        = o.optString("obsSource",         "");
        b.obsVolume        = (float) o.optDouble("obsVolume", -1.0);
        b.twitchCommand    = o.optString("twitchCommand",     "marker");
        b.twitchDescription= o.optString("twitchDescription", "");
        return b;
    }

    public static String uid() {
        return UUID.randomUUID().toString().substring(0, 8);
    }

    private List<DeckPage> defaultPages() {
        List<DeckPage> list = new ArrayList<>();

        // ── Speedrun page ──
        DeckPage speedrun = new DeckPage("Speedrun");
        speedrun.buttons.add(btn("⚡", "Split",    "keys", "ctrl,alt,1", "#00e5ff"));
        speedrun.buttons.add(btn("↩",  "Reset",    "keys", "ctrl,alt,2", "#ff3c6e"));
        speedrun.buttons.add(btn("⏸",  "Pause",    "keys", "ctrl,alt,3", "#aaff00"));
        speedrun.buttons.add(btn("🎙",  "Mute Mic", "keys", "ctrl,alt,m", "#ff9f00"));
        speedrun.buttons.add(btn("🎵",  "Music",    "keys", "ctrl,alt,4", "#bf7af0"));
        speedrun.buttons.add(btn("🔔",  "Alert",    "keys", "ctrl,alt,5", "#ff6b35"));
        list.add(speedrun);

        // ── OBS page ──
        DeckPage obs = new DeckPage("OBS");
        DeckButton startStream = btn("🔴", "Go Live",   "obs", "", "#ff3c6e");
        startStream.obsCommand = "StartStream"; startStream.confirmTap = true;
        obs.buttons.add(startStream);
        DeckButton stopStream = btn("⬛", "End Stream", "obs", "", "#555e7a");
        stopStream.obsCommand = "StopStream"; stopStream.confirmTap = true;
        obs.buttons.add(stopStream);
        DeckButton recStart = btn("⏺", "Record",    "obs", "", "#ff9f00");
        recStart.obsCommand = "StartRecord"; obs.buttons.add(recStart);
        DeckButton recStop  = btn("⏹", "Stop Rec",  "obs", "", "#555e7a");
        recStop.obsCommand  = "StopRecord";  obs.buttons.add(recStop);
        DeckButton scene1 = btn("🎮", "Gameplay",   "obs", "", "#00e5ff");
        scene1.obsCommand = "SetCurrentProgramScene"; scene1.obsScene = "Gameplay";
        obs.buttons.add(scene1);
        DeckButton scene2 = btn("💬", "Just Chat",  "obs", "", "#38bdf8");
        scene2.obsCommand = "SetCurrentProgramScene"; scene2.obsScene = "Just Chatting";
        obs.buttons.add(scene2);
        list.add(obs);

        // ── Twitch page ──
        DeckPage twitch = new DeckPage("Twitch");

        DeckButton marker = new DeckButton(uid(), "📍", "Mark VOD", "twitch", "", "", "#9146ff");
        marker.twitchCommand     = "marker";
        marker.twitchDescription = "";
        marker.haptic            = true;
        twitch.buttons.add(marker);

        DeckButton markerWR = new DeckButton(uid(), "🏆", "WR Pace",  "twitch", "", "", "#fbbf24");
        markerWR.twitchCommand     = "marker";
        markerWR.twitchDescription = "WR Pace";
        twitch.buttons.add(markerWR);

        DeckButton markerFunny = new DeckButton(uid(), "😂", "Funny",   "twitch", "", "", "#ff6b35");
        markerFunny.twitchCommand     = "marker";
        markerFunny.twitchDescription = "Funny moment";
        twitch.buttons.add(markerFunny);

        DeckButton markerClip = new DeckButton(uid(), "✂️", "Clip This", "twitch", "", "", "#00ff99");
        markerClip.twitchCommand     = "marker";
        markerClip.twitchDescription = "Clip this";
        twitch.buttons.add(markerClip);

        DeckButton markerPB = new DeckButton(uid(), "🎯", "PB Attempt", "twitch", "", "", "#e879f9");
        markerPB.twitchCommand     = "marker";
        markerPB.twitchDescription = "PB attempt";
        twitch.buttons.add(markerPB);

        DeckButton markerBlank = new DeckButton(uid(), "📌", "Marker",   "twitch", "", "", "#9146ff");
        markerBlank.twitchCommand     = "marker";
        markerBlank.twitchDescription = "";
        twitch.buttons.add(markerBlank);

        list.add(twitch);
        return list;
    }

    private DeckButton btn(String icon, String label, String type, String keys, String color) {
        return new DeckButton(uid(), icon, label, type, keys, "", color);
    }
}

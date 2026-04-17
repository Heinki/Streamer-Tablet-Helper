package com.streamerhelper.app;

import android.os.Handler;
import android.os.Looper;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Handles all HTTP communication with the PC server.
 * - Fixed thread pool (2 threads) — not unbounded cached pool
 * - Auto-retry with exponential back-off (ping loop)
 * - All callbacks are delivered on the main thread
 */
public class ServerClient {

    public interface Callback {
        void onResult(boolean ok, String message);
    }

    // Connection state listener (used by DeckActivity to update the dot)
    public interface ConnectionListener {
        void onConnected();
        void onDisconnected();
    }

    private static final int    TIMEOUT_MS        = 3_000;
    private static final int[]  RETRY_DELAYS_MS   = {2_000, 4_000, 8_000, 15_000, 30_000};

    private volatile String serverIp;
    private volatile boolean connected      = false;
    private volatile boolean retryRunning   = false;

    private final ExecutorService executor    = Executors.newFixedThreadPool(2);
    private final Handler         mainHandler = new Handler(Looper.getMainLooper());
    private ConnectionListener    listener;

    public ServerClient(String ip) {
        this.serverIp = ip;
    }

    public void setIp(String ip) {
        this.serverIp = ip;
        connected = false;          // force re-ping after IP change
    }

    public void setConnectionListener(ConnectionListener l) {
        this.listener = l;
    }

    public boolean isConnected() {
        return connected;
    }

    // ── PUBLIC ACTIONS ────────────────────────────────────────────────────────

    public void ping(Callback cb) {
        executor.submit(() -> {
            try {
                HttpURLConnection conn = open("GET", "/ping");
                int code = conn.getResponseCode();
                conn.disconnect();
                boolean ok = (code == 200);
                onConnectResult(ok);
                deliver(cb, ok, ok ? "ok" : "HTTP " + code);
            } catch (Exception e) {
                onConnectResult(false);
                deliver(cb, false, e.getMessage());
            }
        });
    }

    public void sendKeys(String keys, Callback cb) {
        executor.submit(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("action", "keys");
                JSONArray arr = new JSONArray();
                for (String k : keys.split(",")) {
                    String t = k.trim();
                    if (!t.isEmpty()) arr.put(t);
                }
                body.put("keys", arr);
                postJson(body.toString(), cb);
            } catch (Exception e) {
                deliver(cb, false, e.getMessage());
            }
        });
    }

    public void sendSound(String path, Callback cb) {
        executor.submit(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("action", "sound");
                body.put("path", path);
                postJson(body.toString(), cb);
            } catch (Exception e) {
                deliver(cb, false, e.getMessage());
            }
        });
    }

    public void sendObs(String command, String scene, String source, float volume, Callback cb) {
        executor.submit(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("action",  "obs");
                body.put("command", command);
                if (scene  != null && !scene.isEmpty())  body.put("scene",  scene);
                if (source != null && !source.isEmpty()) body.put("source", source);
                if (volume >= 0)                         body.put("volume", volume);
                postJson(body.toString(), cb);
            } catch (Exception e) {
                deliver(cb, false, e.getMessage());
            }
        });
    }

    // ── AUTO-RETRY ────────────────────────────────────────────────────────────

    /**
     * Start background retry loop. Call this once from DeckActivity.
     * Stops automatically when a connection succeeds, restarts on disconnect.
     */
    public void startRetryLoop() {
        if (retryRunning) return;
        retryRunning = true;
        executor.submit(this::retryLoop);
    }

    public void stopRetryLoop() {
        retryRunning = false;
    }

    private void retryLoop() {
        int attempt = 0;
        while (retryRunning) {
            if (!connected) {
                try {
                    HttpURLConnection conn = open("GET", "/ping");
                    int code = conn.getResponseCode();
                    conn.disconnect();
                    if (code == 200) {
                        onConnectResult(true);
                        attempt = 0;    // reset back-off on success
                    } else {
                        onConnectResult(false);
                    }
                } catch (Exception e) {
                    onConnectResult(false);
                }
                // Exponential back-off, capped at last entry
                int delayMs = RETRY_DELAYS_MS[Math.min(attempt, RETRY_DELAYS_MS.length - 1)];
                attempt++;
                try { Thread.sleep(delayMs); } catch (InterruptedException ignored) {}
            } else {
                // Already connected — just poll every 10 s to catch disconnects
                try { Thread.sleep(10_000); } catch (InterruptedException ignored) {}
                // Quick health check
                try {
                    HttpURLConnection conn = open("GET", "/ping");
                    int code = conn.getResponseCode();
                    conn.disconnect();
                    if (code != 200) onConnectResult(false);
                } catch (Exception e) {
                    onConnectResult(false);
                }
            }
        }
    }

    // ── INTERNAL ──────────────────────────────────────────────────────────────

    private HttpURLConnection open(String method, String path) throws Exception {
        URL url = new URL("http://" + serverIp + ":7878" + path);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod(method);
        conn.setConnectTimeout(TIMEOUT_MS);
        conn.setReadTimeout(TIMEOUT_MS);
        return conn;
    }


    public void sendTwitch(String command, String description, int adLength, Callback cb) {
        executor.submit(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("action",  "twitch");
                body.put("command", command);
                if (description != null && !description.isEmpty())
                    body.put("description", description);
                if (command.equals("ad"))
                    body.put("length", adLength);
                postJson(body.toString(), cb);
            } catch (Exception e) {
                deliver(cb, false, e.getMessage());
            }
        });
    }

    private void postJson(String json, Callback cb) {
        try {
            HttpURLConnection conn = open("POST", "/");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);
            byte[] data = json.getBytes(StandardCharsets.UTF_8);
            conn.setRequestProperty("Content-Length", String.valueOf(data.length));
            try (OutputStream os = conn.getOutputStream()) { os.write(data); }

            int code = conn.getResponseCode();
            InputStream is = (code >= 400) ? conn.getErrorStream() : conn.getInputStream();
            byte[] resp = (is != null) ? is.readAllBytes() : new byte[0];
            conn.disconnect();

            JSONObject result = new JSONObject(new String(resp, StandardCharsets.UTF_8));
            boolean ok = result.optBoolean("ok", code == 200);
            onConnectResult(true);    // successful HTTP round-trip = connected
            deliver(cb, ok, result.optString("message", ok ? "" : "Server error " + code));
        } catch (Exception e) {
            onConnectResult(false);
            deliver(cb, false, e.getMessage());
        }
    }

    private void onConnectResult(boolean ok) {
        if (ok == connected) return;    // no change — don't spam listener
        connected = ok;
        if (listener != null) {
            mainHandler.post(ok ? listener::onConnected : listener::onDisconnected);
        }
    }

    private void deliver(Callback cb, boolean ok, String msg) {
        if (cb != null) mainHandler.post(() -> cb.onResult(ok, msg));
    }
}

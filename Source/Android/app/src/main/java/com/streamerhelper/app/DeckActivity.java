package com.streamerhelper.app;

import android.app.AlertDialog;
import android.content.Intent;
import android.content.res.Configuration;
import android.content.res.Resources;
import android.graphics.Color;
import android.os.Bundle;
import android.os.PowerManager;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.*;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;

public class DeckActivity extends AppCompatActivity implements ServerClient.ConnectionListener {

    private AppState     state;
    private ServerClient client;
    private int          currentPage  = 0;
    private boolean      needsRefresh = false;
    private PowerManager.WakeLock wakeLock;
    private Vibrator     vibrator;

    // Confirm-tap state
    private int  confirmPrimed   = -1;
    private long confirmPrimedAt = 0;
    private static final long CONFIRM_WINDOW_MS = 1_500;

    private LinearLayout tabBar;
    private GridLayout   grid;
    private TextView     connectionDot;

    // ── Layout values — refreshed on every render from dimension resources ────
    private int   gridColumns;
    private float btnIconSize, btnLabelSize, btnHintSize;
    private int   btnPadV, btnPadH, btnMargin;
    private float dp;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        wakeLock = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "StreamerHelper:WakeLock");

        vibrator = (Vibrator) getSystemService(VIBRATOR_SERVICE);
        dp       = getResources().getDisplayMetrics().density;

        setContentView(R.layout.activity_deck);

        state  = AppState.get(this);
        client = new ServerClient(state.serverIp);
        client.setConnectionListener(this);

        tabBar        = findViewById(R.id.tab_bar);
        grid          = findViewById(R.id.button_grid);
        connectionDot = findViewById(R.id.connection_dot);

        findViewById(R.id.settings_btn).setOnClickListener(v -> openSettings());

        client.ping(null);
        client.startRetryLoop();

        loadDimens();
        renderTabs();
        renderGrid();
    }

    /** Called by Android when orientation/screenSize changes (we declared configChanges in manifest) */
    @Override
    public void onConfigurationChanged(@NonNull Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        // dp doesn't change but dimen resources do — reload them
        dp = getResources().getDisplayMetrics().density;
        loadDimens();
        renderTabs();
        renderGrid();
    }

    /** Read all layout dimensions from the appropriate resource qualifier bucket */
    private void loadDimens() {
        Resources r = getResources();
        gridColumns  = r.getInteger(R.integer.grid_columns);
        btnIconSize  = px(r, R.dimen.btn_icon_size)  / dp;   // convert back to sp-equivalent
        btnLabelSize = px(r, R.dimen.btn_label_size) / dp;
        btnHintSize  = px(r, R.dimen.btn_hint_size)  / dp;
        btnPadV      = pxR(r, R.dimen.btn_pad_v);
        btnPadH      = pxR(r, R.dimen.btn_pad_h);
        btnMargin    = pxR(r, R.dimen.btn_margin);
    }

    private int px(Resources r, int dimenRes) { return (int) r.getDimension(dimenRes); }
    private int pxR(Resources r, int dimenRes) { return (int) r.getDimension(dimenRes); }
    private int px(int dp_) { return (int)(dp_ * dp); }

    // ── CONNECTION ────────────────────────────────────────────────────────────
    @Override public void onConnected()    { runOnUiThread(this::showConnected);    }
    @Override public void onDisconnected() { runOnUiThread(this::showDisconnected); }

    private void showConnected() {
        connectionDot.setText(getString(R.string.dot_connected, state.hideIp ? "" : state.serverIp));
        connectionDot.setTextColor(0xFF00ff99);
    }
    private void showDisconnected() {
        connectionDot.setText(getString(R.string.dot_disconnected, state.hideIp ? "" : getString(R.string.reconnecting)));
        connectionDot.setTextColor(0xFFff3c6e);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (wakeLock != null && !wakeLock.isHeld()) {
            // Provide a timeout (10 mins) as a safety measure
            wakeLock.acquire(10 * 60 * 1000L);
        }
        if (needsRefresh) {
            needsRefresh = false;
            loadDimens();
            renderTabs();
            renderGrid();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        client.stopRetryLoop();
    }

    // ── SETTINGS ──────────────────────────────────────────────────────────────
    private void openSettings() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(px(24), px(16), px(24), px(24));

        layout.addView(sectionLabel(getString(R.string.pc_ip_address)));
        EditText ipField = styledEdit(state.serverIp, getString(R.string.ip_hint));
        ipField.setInputType(android.text.InputType.TYPE_CLASS_PHONE);
        layout.addView(ipField);
        layout.addView(hintText(getString(R.string.ip_help)));

        CheckBox hideIpCheck = new CheckBox(this);
        hideIpCheck.setText(R.string.hide_ip);
        hideIpCheck.setTextColor(0xFFcdd6f4);
        hideIpCheck.setChecked(state.hideIp);
        LinearLayout.LayoutParams hlp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        hlp.setMargins(0, px(8), 0, 0);
        hideIpCheck.setLayoutParams(hlp);
        layout.addView(hideIpCheck);

        divider(layout);

        layout.addView(sectionLabel(getString(R.string.pages_title)));
        LinearLayout pagesContainer = new LinearLayout(this);
        pagesContainer.setOrientation(LinearLayout.VERTICAL);
        layout.addView(pagesContainer);
        refreshPagesList(pagesContainer);

        layout.addView(createAddPageButton(pagesContainer));

        divider(layout);

        // Device info section — shows what mode is active
        layout.addView(sectionLabel(getString(R.string.current_layout)));
        layout.addView(createDeviceInfoText());

        divider(layout);

        layout.addView(sectionLabel(getString(R.string.how_to_use)));
        TextView tips = new TextView(this);
        tips.setText(R.string.usage_tips);
        tips.setTextColor(0xFFcdd6f4);
        tips.setTextSize(12f);
        tips.setLineSpacing(px(5), 1f);
        layout.addView(tips);

        ScrollView scroll = new ScrollView(this);
        scroll.addView(layout);

        new AlertDialog.Builder(this)
            .setTitle(R.string.settings_title)
            .setView(scroll)
            .setPositiveButton(R.string.save_ip, (d, w) -> {
                String newIp = ipField.getText().toString().trim();
                boolean newHide = hideIpCheck.isChecked();
                boolean changed = false;

                if (!newIp.isEmpty() && !newIp.equals(state.serverIp)) {
                    state.serverIp = newIp;
                    client.setIp(newIp);
                    client.ping(null);
                    changed = true;
                    Toast.makeText(this, R.string.ip_updated, Toast.LENGTH_SHORT).show();
                }

                if (newHide != state.hideIp) {
                    state.hideIp = newHide;
                    changed = true;
                }

                if (changed) {
                    state.save();
                    if (client.isConnected()) showConnected(); else showDisconnected();
                }
            })
            .setNegativeButton(R.string.close, null)
            .show();
    }

    private Button createAddPageButton(LinearLayout pagesContainer) {
        Button addPageBtn = new Button(this);
        addPageBtn.setText(R.string.add_page_btn);
        addPageBtn.setAllCaps(false);
        addPageBtn.setTextColor(0xFF00e5ff);
        addPageBtn.setBackgroundColor(0xFF1e2535);
        LinearLayout.LayoutParams alp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        alp.setMargins(0, px(6), 0, 0);
        addPageBtn.setLayoutParams(alp);
        addPageBtn.setOnClickListener(v -> promptAddPage(() -> refreshPagesList(pagesContainer)));
        return addPageBtn;
    }

    private TextView createDeviceInfoText() {
        String mode = gridColumns + " columns";
        boolean isTablet = getResources().getConfiguration().smallestScreenWidthDp >= 600;
        boolean isLand   = getResources().getConfiguration().orientation == Configuration.ORIENTATION_LANDSCAPE;
        String device = isTablet ? "Tablet" : "Phone";
        String orient = isLand   ? "landscape" : "portrait";
        TextView deviceInfo = new TextView(this);
        deviceInfo.setText(getString(R.string.layout_info, device, orient, mode, getString(R.string.layout_help)));
        deviceInfo.setTextColor(0xFFcdd6f4);
        deviceInfo.setTextSize(12f);
        deviceInfo.setLineSpacing(px(4), 1f);
        return deviceInfo;
    }

    private void refreshPagesList(LinearLayout container) {
        container.removeAllViews();
        for (int i = 0; i < state.pages.size(); i++) {
            container.addView(createPageRow(i, container));
        }
    }

    private View createPageRow(int idx, LinearLayout container) {
        DeckPage page  = state.pages.get(idx);
        int cnt        = page.buttons.size();

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(px(12), px(10), px(4), px(10));
        row.setBackgroundColor(0xFF1e2535);
        LinearLayout.LayoutParams rlp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        rlp.setMargins(0, 0, 0, px(3));
        row.setLayoutParams(rlp);

        TextView name = new TextView(this);
        name.setText(getString(R.string.button_count, page.name, cnt, cnt == 1 ? "" : "s"));
        name.setTextColor(0xFFcdd6f4);
        name.setTextSize(13f);
        name.setLayoutParams(new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        row.addView(name);

        Button renameBtn = smallBtn("✏", 0xFF888888);
        renameBtn.setOnClickListener(v -> promptRenamePage(idx, () -> refreshPagesList(container)));
        row.addView(renameBtn);

        if (state.pages.size() > 1) {
            Button deleteBtn = smallBtn("🗑", 0xFFff3c6e);
            deleteBtn.setOnClickListener(v -> promptDeletePage(idx, () -> refreshPagesList(container)));
            row.addView(deleteBtn);
        }
        return row;
    }

    private void promptAddPage(Runnable onDone) {
        EditText et = styledEdit("", getString(R.string.page_name_hint));
        new AlertDialog.Builder(this).setTitle(R.string.new_page).setView(et)
            .setPositiveButton(R.string.add, (d, w) -> {
                String n = et.getText().toString().trim();
                if (n.isEmpty()) n = "Page " + (state.pages.size() + 1);
                state.pages.add(new DeckPage(n));
                state.save();
                currentPage = state.pages.size() - 1;
                renderTabs(); renderGrid();
                if (onDone != null) onDone.run();
            }).setNegativeButton(R.string.cancel, null).show();
    }

    private void promptRenamePage(int idx, Runnable onDone) {
        EditText et = styledEdit(state.pages.get(idx).name, getString(R.string.page_name_hint));
        new AlertDialog.Builder(this).setTitle(R.string.rename_page).setView(et)
            .setPositiveButton(R.string.save, (d, w) -> {
                String n = et.getText().toString().trim();
                if (!n.isEmpty()) {
                    state.pages.get(idx).name = n;
                    state.save(); renderTabs();
                    if (onDone != null) onDone.run();
                }
            }).setNegativeButton(R.string.cancel, null).show();
    }

    private void promptDeletePage(int idx, Runnable onDone) {
        int cnt = state.pages.get(idx).buttons.size();
        new AlertDialog.Builder(this)
            .setTitle(getString(R.string.delete_page_title, state.pages.get(idx).name))
            .setMessage(getString(R.string.delete_page_msg, cnt, cnt == 1 ? "" : "s"))
            .setPositiveButton(R.string.delete, (d, w) -> {
                state.pages.remove(idx);
                state.save();
                if (currentPage >= state.pages.size()) currentPage = state.pages.size() - 1;
                renderTabs(); renderGrid();
                if (onDone != null) onDone.run();
            }).setNegativeButton(R.string.cancel, null).show();
    }

    // ── TABS ──────────────────────────────────────────────────────────────────
    private void renderTabs() {
        Resources r = getResources();
        int tabH    = pxR(r, R.dimen.tab_height);
        float tabTx = r.getDimension(R.dimen.tab_text_size) / dp;

        tabBar.removeAllViews();
        for (int i = 0; i < state.pages.size(); i++) {
            final int idx = i;
            Button btn = new Button(this);
            btn.setText(state.pages.get(i).name);
            btn.setAllCaps(false);
            btn.setTextSize(tabTx);
            btn.setPadding(px(14), px(4), px(14), px(4));
            btn.setBackgroundColor(i == currentPage ? 0xFF00e5ff : 0xFF1e2535);
            btn.setTextColor(i == currentPage ? 0xFF000000 : 0xFFaaaaaa);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, tabH);
            lp.setMargins(px(3), px(3), px(3), px(3));
            btn.setLayoutParams(lp);
            btn.setOnClickListener(v -> { currentPage = idx; renderTabs(); renderGrid(); });
            btn.setOnLongClickListener(v -> { promptRenamePage(idx, this::renderTabs); return true; });
            tabBar.addView(btn);
        }
    }

    // ── GRID ──────────────────────────────────────────────────────────────────
    private void renderGrid() {
        grid.removeAllViews();
        grid.setColumnCount(gridColumns);

        DeckPage page = state.pages.get(currentPage);
        for (int i = 0; i < page.buttons.size(); i++) {
            grid.addView(makeBtnCard(page.buttons.get(i), i));
        }
        grid.addView(makeAddSlot());
    }

    private View makeBtnCard(DeckButton btn, int idx) {
        int parsedColor;
        try { parsedColor = Color.parseColor(btn.color != null ? btn.color : "#00e5ff"); }
        catch (Exception e) { parsedColor = 0xFF00e5ff; }
        final int color = parsedColor;

        FrameLayout card = new FrameLayout(this);

        // Clamp widthSpan so it never exceeds the number of columns
        int span = Math.min(btn.widthSpan == 2 ? 2 : 1, gridColumns);
        GridLayout.LayoutParams glp = new GridLayout.LayoutParams();
        glp.height     = ViewGroup.LayoutParams.WRAP_CONTENT;
        glp.columnSpec = GridLayout.spec(GridLayout.UNDEFINED, span, 1f);
        glp.width      = 0;
        glp.setMargins(btnMargin, btnMargin, btnMargin, btnMargin);
        card.setLayoutParams(glp);

        LinearLayout inner = new LinearLayout(this);
        inner.setOrientation(LinearLayout.VERTICAL);
        inner.setGravity(Gravity.CENTER);
        inner.setPadding(btnPadH, btnPadV, btnPadH, btnPadV);
        inner.setBackgroundResource(R.drawable.btn_bg);

        // Left colour strip
        View strip = new View(this);
        strip.setBackgroundColor(color);
        strip.setLayoutParams(new FrameLayout.LayoutParams(px(5), FrameLayout.LayoutParams.MATCH_PARENT));

        // Icon
        TextView iconV = new TextView(this);
        iconV.setText(btn.icon != null && !btn.icon.isEmpty() ? btn.icon : "▶");
        iconV.setTextSize(btnIconSize);
        iconV.setGravity(Gravity.CENTER);
        inner.addView(iconV);

        // Label (+ lock badge if confirmTap)
        TextView labelV = new TextView(this);
        labelV.setText(btn.confirmTap ? btn.label + " 🔒" : btn.label);
        labelV.setTextColor(0xFFcdd6f4);
        labelV.setTextSize(btnLabelSize);
        labelV.setTypeface(null, android.graphics.Typeface.BOLD);
        labelV.setGravity(Gravity.CENTER);
        inner.addView(labelV);

        // Sub-hint — only show on larger form factors (≥3 columns) to save space on phones
        if (gridColumns >= 3) {
            TextView hintV = new TextView(this);
            hintV.setText(subHint(btn));
            hintV.setTextColor(0xFF555e7a);
            hintV.setTextSize(btnHintSize);
            hintV.setGravity(Gravity.CENTER);
            inner.addView(hintV);
        }

        // "hold to edit" ghost text
        TextView holdHint = new TextView(this);
        holdHint.setText(R.string.hold_to_edit);
        holdHint.setTextColor(0xFF1e2840);
        holdHint.setTextSize(7f);
        holdHint.setGravity(Gravity.CENTER);
        inner.addView(holdHint);

        card.addView(inner);
        card.addView(strip);

        card.setOnClickListener(v -> handleTap(btn, idx, inner, color));
        card.setOnLongClickListener(v -> { openEditor(idx); return true; });
        return card;
    }

    private String subHint(DeckButton btn) {
        switch (btn.type) {
            case "obs":    return "OBS: " + (btn.obsCommand != null ? btn.obsCommand : "");
            case "twitch": {
                String d = btn.twitchDescription != null ? btn.twitchDescription : "";
                return d.isEmpty() ? "Twitch marker" : "Marker: " + d;
            }
            case "sound":  return "🔊 sound";
            default:       return btn.keys != null ? btn.keys : "";
        }
    }

    private View makeAddSlot() {
        FrameLayout card = new FrameLayout(this);
        GridLayout.LayoutParams p = new GridLayout.LayoutParams();
        p.width      = 0;
        p.height     = ViewGroup.LayoutParams.WRAP_CONTENT;
        p.columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1f);
        p.setMargins(btnMargin, btnMargin, btnMargin, btnMargin);
        card.setLayoutParams(p);

        LinearLayout inner = new LinearLayout(this);
        inner.setOrientation(LinearLayout.VERTICAL);
        inner.setGravity(Gravity.CENTER);
        inner.setPadding(btnPadH, btnPadV, btnPadH, btnPadV);
        inner.setBackgroundResource(R.drawable.btn_add_bg);

        TextView plus = new TextView(this);
        plus.setText("+");
        plus.setTextSize(btnIconSize);
        plus.setTextColor(0xFF3a4460);
        plus.setGravity(Gravity.CENTER);
        inner.addView(plus);

        // Only show text label when there's room
        if (gridColumns >= 3) {
            TextView lbl = new TextView(this);
            lbl.setText(R.string.add_button);
            lbl.setTextColor(0xFF2a3045);
            lbl.setTextSize(btnHintSize);
            lbl.setGravity(Gravity.CENTER);
            inner.addView(lbl);
        }

        card.addView(inner);
        card.setOnClickListener(v -> openEditor(-1));
        return card;
    }

    // ── TAP HANDLING ──────────────────────────────────────────────────────────
    private void handleTap(DeckButton btn, int idx, LinearLayout inner, int color) {
        if (btn.confirmTap) {
            long now = System.currentTimeMillis();
            if (confirmPrimed == idx && (now - confirmPrimedAt) < CONFIRM_WINDOW_MS) {
                confirmPrimed = -1;
                doFire(btn, inner, color);
            } else {
                confirmPrimed   = idx;
                confirmPrimedAt = now;
                flashCard(inner, 0xFFff9f00);
                Toast.makeText(this, getString(R.string.confirm_tap, btn.label), Toast.LENGTH_SHORT).show();
            }
        } else {
            doFire(btn, inner, color);
        }
    }

    private void doFire(DeckButton btn, LinearLayout inner, int color) {
        if (btn.haptic && vibrator != null && vibrator.hasVibrator()) {
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                vibrator.vibrate(VibrationEffect.createOneShot(40, VibrationEffect.DEFAULT_AMPLITUDE));
            } else {
                // Deprecated in API 26, but required for API 21-25
                vibrator.vibrate(40);
            }
        }
        flashCard(inner, color);
        fireAction(btn);
    }

    private void flashCard(LinearLayout inner, int flashColor) {
        inner.setBackgroundColor((flashColor & 0x00FFFFFF) | 0x66000000);
        inner.postDelayed(() -> inner.setBackgroundResource(R.drawable.btn_bg), 150);
    }

    // ── FIRE ──────────────────────────────────────────────────────────────────
    private void fireAction(DeckButton btn) {
        ServerClient.Callback cb = (ok, msg) ->
            Toast.makeText(this, ok ? getString(R.string.action_success, btn.label) : getString(R.string.action_fail, msg), Toast.LENGTH_SHORT).show();
        switch (btn.type) {
            case "keys":  client.sendKeys(btn.keys, cb); break;
            case "sound": client.sendSound(btn.sound, cb); break;
            case "obs":    client.sendObs(btn.obsCommand, btn.obsScene, btn.obsSource, btn.obsVolume, cb); break;
            case "twitch": client.sendTwitch(btn.twitchCommand, btn.twitchDescription, btn.twitchAdLength, cb); break;
        }
    }

    // ── EDITOR ────────────────────────────────────────────────────────────────
    private void openEditor(int btnIdx) {
        needsRefresh = true;
        Intent i = new Intent(this, EditButtonActivity.class);
        i.putExtra("pageIdx", currentPage);
        i.putExtra("btnIdx",  btnIdx);
        startActivity(i);
    }

    // ── VIEW HELPERS ──────────────────────────────────────────────────────────
    private TextView sectionLabel(String text) {
        TextView tv = new TextView(this);
        tv.setText(text); tv.setTextSize(10f); tv.setTextColor(0xFFcdd6f4); tv.setLetterSpacing(0.1f);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, px(14), 0, px(5));
        tv.setLayoutParams(lp);
        return tv;
    }
    private TextView hintText(String text) {
        TextView tv = new TextView(this);
        tv.setText(text); tv.setTextSize(11f); tv.setTextColor(0xFFcdd6f4); tv.setLineSpacing(px(3), 1f);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, px(4), 0, 0);
        tv.setLayoutParams(lp);
        return tv;
    }
    private EditText styledEdit(String val, String hint) {
        EditText et = new EditText(this);
        et.setText(val);
        et.setHint(hint);
        et.setTextColor(0xFF000000);
        et.setHintTextColor(0xFF444444);
        et.setBackgroundColor(0xFF00e5ff);
        et.setPadding(px(12), px(12), px(12), px(12));
        return et;
    }
    private Button smallBtn(String text, int textColor) {
        Button b = new Button(this);
        b.setText(text); b.setTextColor(textColor); b.setBackgroundColor(0x00000000);
        b.setAllCaps(false);
        b.setTextSize(16f);
        b.setPadding(px(12), px(6), px(12), px(6));
        b.setMinimumWidth(px(40));
        b.setMinimumHeight(px(36));
        b.setLayoutParams(new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        return b;
    }
    private void divider(LinearLayout parent) {
        View div = new View(this);
        div.setBackgroundColor(0xFF1e2535);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, px(1));
        lp.setMargins(0, px(18), 0, px(2));
        div.setLayoutParams(lp);
        parent.addView(div);
    }
}

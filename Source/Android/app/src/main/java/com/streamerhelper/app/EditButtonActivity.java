package com.streamerhelper.app;

import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.widget.*;
import androidx.appcompat.app.AppCompatActivity;

public class EditButtonActivity extends AppCompatActivity {
    private int pageIdx, btnIdx;
    private AppState state;
    private boolean isNew;
    private float dp;

    private EditText    fIcon, fLabel;
    private RadioGroup  fTypeGroup;
    private RadioButton fTypeKeys, fTypeSound, fTypeObs, fTypeTwitch;
    private LinearLayout keysFields, soundFields, obsFields, twitchFields;
    private EditText    fKeys, fSound, fObsScene, fObsSource, fTwitchDesc, fTwitchClipTitle;
    private Spinner     fObsCommand, fTwitchAdLength;
    private RadioGroup  fTwitchTypeGroup;
    private RadioButton fTwitchTypeMarker, fTwitchTypeAd, fTwitchTypeClip;
    private LinearLayout twitchMarkerFields, twitchAdFields, twitchClipFields;
    private LinearLayout colorRow;
    private CheckBox    fConfirmTap, fHaptic;
    private RadioButton fWidth1, fWidth2;
    private String      selectedColor = "#00e5ff";

    private static final String[] COLORS = {
        "#00e5ff","#ff3c6e","#aaff00","#ff9f00",
        "#bf7af0","#ff6b35","#00ff99","#e879f9",
        "#38bdf8","#fbbf24","#9146ff","#ffffff"
    };

    private static final String[] OBS_COMMANDS = {
        "SetCurrentProgramScene","StartStream","StopStream",
        "StartRecord","StopRecord","ToggleMute","SetVolume",
        "ToggleSource"
    };

    private static final String[] TWITCH_AD_LENGTHS = {
        "30", "60", "90", "120", "150", "180"
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_edit_button);

        dp      = getResources().getDisplayMetrics().density;
        state   = AppState.get(this);
        pageIdx = getIntent().getIntExtra("pageIdx", 0);
        btnIdx  = getIntent().getIntExtra("btnIdx", -1);
        isNew   = (btnIdx == -1);

        fIcon         = findViewById(R.id.f_icon);
        fLabel        = findViewById(R.id.f_label);
        fKeys         = findViewById(R.id.f_keys);
        fSound        = findViewById(R.id.f_sound);
        fTypeGroup    = findViewById(R.id.f_type_group);
        fTypeKeys     = findViewById(R.id.f_type_keys);
        fTypeSound    = findViewById(R.id.f_type_sound);
        fTypeObs      = findViewById(R.id.f_type_obs);
        fTypeTwitch   = findViewById(R.id.f_type_twitch);
        keysFields    = findViewById(R.id.keys_fields);
        soundFields   = findViewById(R.id.sound_fields);
        obsFields     = findViewById(R.id.obs_fields);
        twitchFields  = findViewById(R.id.twitch_fields);
        fObsCommand   = findViewById(R.id.f_obs_command);
        fObsScene     = findViewById(R.id.f_obs_scene);
        fObsSource    = findViewById(R.id.f_obs_source);
        fTwitchDesc   = findViewById(R.id.f_twitch_desc);
        fTwitchTypeGroup = findViewById(R.id.f_twitch_type_group);
        fTwitchTypeMarker = findViewById(R.id.f_twitch_type_marker);
        fTwitchTypeAd     = findViewById(R.id.f_twitch_type_ad);
        fTwitchTypeClip   = findViewById(R.id.f_twitch_type_clip);
        twitchMarkerFields = findViewById(R.id.twitch_marker_fields);
        twitchAdFields     = findViewById(R.id.twitch_ad_fields);
        twitchClipFields   = findViewById(R.id.twitch_clip_fields);
        fTwitchAdLength    = findViewById(R.id.f_twitch_ad_length);
        fTwitchClipTitle   = findViewById(R.id.f_twitch_clip_title);
        colorRow      = findViewById(R.id.color_row);
        fConfirmTap   = findViewById(R.id.f_confirm_tap);
        fHaptic       = findViewById(R.id.f_haptic);
        fWidth1       = findViewById(R.id.f_width_1);
        fWidth2       = findViewById(R.id.f_width_2);

        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,
            android.R.layout.simple_spinner_item, OBS_COMMANDS);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        fObsCommand.setAdapter(adapter);

        ArrayAdapter<String> adAdapter = new ArrayAdapter<>(this,
            android.R.layout.simple_spinner_item, TWITCH_AD_LENGTHS);
        adAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        fTwitchAdLength.setAdapter(adAdapter);
        // Removed hardcoded setSelection(0) — restore logic handles initial value

        fTypeGroup.setOnCheckedChangeListener((group, id) -> updateTypeFields(id));
        fTwitchTypeGroup.setOnCheckedChangeListener((group, id) -> updateTwitchTypeFields(id));

        fObsCommand.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            public void onItemSelected(AdapterView<?> p, View v, int pos, long id) { updateObsFields(); }
            public void onNothingSelected(AdapterView<?> p) {}
        });

        buildColorSwatches();

        if (!isNew) {
            DeckButton btn = state.pages.get(pageIdx).buttons.get(btnIdx);
            fIcon.setText(btn.icon);
            fLabel.setText(btn.label);
            fKeys.setText(btn.keys);
            fSound.setText(btn.sound);
            fObsScene.setText(btn.obsScene);
            fObsSource.setText(btn.obsSource);
            fTwitchDesc.setText(btn.twitchDescription != null ? btn.twitchDescription : "");
            fTwitchClipTitle.setText(btn.twitchClipTitle != null ? btn.twitchClipTitle : "");
            selectedColor = btn.color != null ? btn.color : "#00e5ff";
            fConfirmTap.setChecked(btn.confirmTap);
            fHaptic.setChecked(btn.haptic);
            if (btn.widthSpan == 2) fWidth2.setChecked(true); else fWidth1.setChecked(true);

            switch (btn.type) {
                case "sound":  fTypeSound.setChecked(true);  break;
                case "obs":    fTypeObs.setChecked(true);    break;
                case "twitch": fTypeTwitch.setChecked(true); break;
                default:       fTypeKeys.setChecked(true);   break;
            }

            if ("ad".equals(btn.twitchCommand)) {
                fTwitchTypeAd.setChecked(true);
                // Use fallback to 30 if twitchAdLength was never set (e.g. old save data)
                int adLen = btn.twitchAdLength > 0 ? btn.twitchAdLength : 30;
                for (int i = 0; i < TWITCH_AD_LENGTHS.length; i++) {
                    if (TWITCH_AD_LENGTHS[i].equals(String.valueOf(adLen))) {
                        fTwitchAdLength.setSelection(i);
                        break;
                    }
                }
            } else if ("clip".equals(btn.twitchCommand)) {
                fTwitchTypeClip.setChecked(true);
            } else {
                fTwitchTypeMarker.setChecked(true);
            }
            updateTwitchTypeFields(fTwitchTypeGroup.getCheckedRadioButtonId());

            if (btn.obsCommand != null) {
                for (int i = 0; i < OBS_COMMANDS.length; i++) {
                    if (OBS_COMMANDS[i].equals(btn.obsCommand)) {
                        fObsCommand.setSelection(i); break;
                    }
                }
            }
            refreshSwatchSelection();
        } else {
            fTypeKeys.setChecked(true);
            fHaptic.setChecked(true);
            fWidth1.setChecked(true);
            // Default ad length to 30s for new buttons
            fTwitchAdLength.setSelection(0);
        }

        ((TextView) findViewById(R.id.editor_title)).setText(isNew ? R.string.new_button : R.string.edit_button);
        findViewById(R.id.btn_save).setOnClickListener(v -> save());
        findViewById(R.id.btn_cancel).setOnClickListener(v -> finish());
        View del = findViewById(R.id.btn_delete);
        del.setVisibility(isNew ? View.GONE : View.VISIBLE);
        del.setOnClickListener(v -> delete());
    }

    private void updateTypeFields(int checkedId) {
        keysFields.setVisibility(checkedId == R.id.f_type_keys    ? View.VISIBLE : View.GONE);
        soundFields.setVisibility(checkedId == R.id.f_type_sound  ? View.VISIBLE : View.GONE);
        obsFields.setVisibility(checkedId == R.id.f_type_obs      ? View.VISIBLE : View.GONE);
        twitchFields.setVisibility(checkedId == R.id.f_type_twitch ? View.VISIBLE : View.GONE);

        // Auto-set Twitch purple color when switching to Twitch type
        if (checkedId == R.id.f_type_twitch && isNew) {
            selectedColor = "#9146ff";
            refreshSwatchSelection();
        }
    }

    private void updateTwitchTypeFields(int checkedId) {
        twitchMarkerFields.setVisibility(checkedId == R.id.f_twitch_type_marker ? View.VISIBLE : View.GONE);
        twitchAdFields.setVisibility(checkedId == R.id.f_twitch_type_ad ? View.VISIBLE : View.GONE);
        twitchClipFields.setVisibility(checkedId == R.id.f_twitch_type_clip ? View.VISIBLE : View.GONE);
    }

    private void updateObsFields() {
        String cmd = (String) fObsCommand.getSelectedItem();
        boolean needsScene  = "SetCurrentProgramScene".equals(cmd) || "ToggleSource".equals(cmd);
        boolean needsSource = "ToggleMute".equals(cmd) || "SetVolume".equals(cmd) || "ToggleSource".equals(cmd);
        fObsScene.setVisibility(needsScene   ? View.VISIBLE : View.GONE);
        fObsSource.setVisibility(needsSource ? View.VISIBLE : View.GONE);
        findViewById(R.id.f_obs_scene_label).setVisibility(needsScene   ? View.VISIBLE : View.GONE);
        findViewById(R.id.f_obs_source_label).setVisibility(needsSource ? View.VISIBLE : View.GONE);
    }

    private void buildColorSwatches() {
        colorRow.removeAllViews();
        int size   = (int)(42 * dp);
        int margin = (int)(5  * dp);
        for (String hex : COLORS) {
            View s = new View(this);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(size, size);
            lp.setMargins(margin, margin, margin, margin);
            s.setLayoutParams(lp);
            s.setBackgroundColor(Color.parseColor(hex));
            s.setTag(hex);
            s.setOnClickListener(v -> { selectedColor = hex; refreshSwatchSelection(); });
            colorRow.addView(s);
        }
        refreshSwatchSelection();
    }

    private void refreshSwatchSelection() {
        for (int i = 0; i < colorRow.getChildCount(); i++) {
            View s = colorRow.getChildAt(i);
            boolean sel = selectedColor.equals(s.getTag());
            s.setScaleX(sel ? 1.3f : 1f);
            s.setScaleY(sel ? 1.3f : 1f);
            s.setAlpha(sel ? 1f : 0.55f);
        }
    }

    private void save() {
        String icon  = fIcon.getText().toString().trim();
        String label = fLabel.getText().toString().trim();
        if (label.isEmpty()) { fLabel.setError(getString(R.string.required)); return; }

        String type;
        if      (fTypeSound.isChecked())  type = "sound";
        else if (fTypeObs.isChecked())    type = "obs";
        else if (fTypeTwitch.isChecked()) type = "twitch";
        else                              type = "keys";

        // Clamp Twitch description to 140 chars (Twitch API limit)
        String twitchDesc = fTwitchDesc.getText().toString().trim();
        if (twitchDesc.length() > 140) twitchDesc = twitchDesc.substring(0, 140);

        DeckButton btn = new DeckButton();
        btn.id               = isNew ? AppState.uid() : state.pages.get(pageIdx).buttons.get(btnIdx).id;
        btn.icon             = icon.isEmpty() ? "▶" : icon;
        btn.label            = label;
        btn.type             = type;
        btn.keys             = fKeys.getText().toString().trim();
        btn.sound            = fSound.getText().toString().trim();
        btn.color            = selectedColor;
        btn.confirmTap       = fConfirmTap.isChecked();
        btn.haptic           = fHaptic.isChecked();
        btn.widthSpan        = fWidth2.isChecked() ? 2 : 1;
        btn.obsCommand       = (String) fObsCommand.getSelectedItem();
        btn.obsScene         = fObsScene.getText().toString().trim();
        btn.obsSource        = fObsSource.getText().toString().trim();
        btn.obsVolume        = -1f;
        btn.twitchCommand    = fTwitchTypeAd.isChecked() ? "ad" : (fTwitchTypeClip.isChecked() ? "clip" : "marker");
        btn.twitchDescription = twitchDesc;
        btn.twitchClipTitle  = fTwitchClipTitle.getText().toString().trim();

        // Always save ad length from spinner; only meaningful when twitchCommand == "ad"
        try {
            Object selected = fTwitchAdLength.getSelectedItem();
            btn.twitchAdLength = (selected != null) ? Integer.parseInt(selected.toString()) : 30;
        } catch (Exception e) {
            btn.twitchAdLength = 30;
        }

        if (isNew) state.pages.get(pageIdx).buttons.add(btn);
        else       state.pages.get(pageIdx).buttons.set(btnIdx, btn);
        state.save();
        finish();
    }

    private void delete() {
        new android.app.AlertDialog.Builder(this)
            .setTitle(R.string.delete_button_title)
            .setPositiveButton(R.string.delete, (d, w) -> {
                state.pages.get(pageIdx).buttons.remove(btnIdx);
                state.save(); finish();
            }).setNegativeButton(R.string.cancel, null).show();
    }
}
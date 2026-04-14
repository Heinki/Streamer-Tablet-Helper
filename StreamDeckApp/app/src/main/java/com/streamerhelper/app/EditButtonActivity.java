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
    private RadioButton fTypeKeys, fTypeSound, fTypeObs;
    private LinearLayout keysFields, soundFields, obsFields;
    private EditText    fKeys, fSound, fObsScene, fObsSource;
    private Spinner     fObsCommand;
    private LinearLayout colorRow;
    private CheckBox    fConfirmTap, fHaptic;
    private RadioGroup  fWidthGroup;
    private RadioButton fWidth1, fWidth2;
    private String      selectedColor = "#00e5ff";

    private static final String[] COLORS = {
        "#00e5ff","#ff3c6e","#aaff00","#ff9f00",
        "#bf7af0","#ff6b35","#00ff99","#e879f9",
        "#38bdf8","#fbbf24"
    };

    private static final String[] OBS_COMMANDS = {
        "SetCurrentProgramScene",
        "StartStream",
        "StopStream",
        "StartRecord",
        "StopRecord",
        "ToggleMute",
        "SetVolume"
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

        fIcon       = findViewById(R.id.f_icon);
        fLabel      = findViewById(R.id.f_label);
        fKeys       = findViewById(R.id.f_keys);
        fSound      = findViewById(R.id.f_sound);
        fTypeGroup  = findViewById(R.id.f_type_group);
        fTypeKeys   = findViewById(R.id.f_type_keys);
        fTypeSound  = findViewById(R.id.f_type_sound);
        fTypeObs    = findViewById(R.id.f_type_obs);
        keysFields  = findViewById(R.id.keys_fields);
        soundFields = findViewById(R.id.sound_fields);
        obsFields   = findViewById(R.id.obs_fields);
        fObsCommand = findViewById(R.id.f_obs_command);
        fObsScene   = findViewById(R.id.f_obs_scene);
        fObsSource  = findViewById(R.id.f_obs_source);
        colorRow    = findViewById(R.id.color_row);
        fConfirmTap = findViewById(R.id.f_confirm_tap);
        fHaptic     = findViewById(R.id.f_haptic);
        fWidthGroup = findViewById(R.id.f_width_group);
        fWidth1     = findViewById(R.id.f_width_1);
        fWidth2     = findViewById(R.id.f_width_2);

        // OBS command spinner
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,
            android.R.layout.simple_spinner_item, OBS_COMMANDS);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        fObsCommand.setAdapter(adapter);

        // Type radio toggles which panel is visible
        fTypeGroup.setOnCheckedChangeListener((group, id) -> {
            keysFields.setVisibility(id == R.id.f_type_keys  ? View.VISIBLE : View.GONE);
            soundFields.setVisibility(id == R.id.f_type_sound ? View.VISIBLE : View.GONE);
            obsFields.setVisibility(id == R.id.f_type_obs    ? View.VISIBLE : View.GONE);
        });

        // OBS command → show/hide scene and source fields
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
            selectedColor = btn.color != null ? btn.color : "#00e5ff";
            fConfirmTap.setChecked(btn.confirmTap);
            fHaptic.setChecked(btn.haptic);
            if (btn.widthSpan == 2) fWidth2.setChecked(true); else fWidth1.setChecked(true);

            if ("sound".equals(btn.type))     fTypeSound.setChecked(true);
            else if ("obs".equals(btn.type))  fTypeObs.setChecked(true);
            else                              fTypeKeys.setChecked(true);

            // Set spinner to saved command
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
        }

        ((TextView) findViewById(R.id.editor_title)).setText(isNew ? "New Button" : "Edit Button");

        findViewById(R.id.btn_save).setOnClickListener(v -> save());
        findViewById(R.id.btn_cancel).setOnClickListener(v -> finish());

        View deleteBtn = findViewById(R.id.btn_delete);
        deleteBtn.setVisibility(isNew ? View.GONE : View.VISIBLE);
        deleteBtn.setOnClickListener(v -> delete());
    }

    private void updateObsFields() {
        String cmd = (String) fObsCommand.getSelectedItem();
        boolean needsScene  = "SetCurrentProgramScene".equals(cmd);
        boolean needsSource = "ToggleMute".equals(cmd) || "SetVolume".equals(cmd);
        fObsScene.setVisibility(needsScene  ? View.VISIBLE : View.GONE);
        fObsSource.setVisibility(needsSource ? View.VISIBLE : View.GONE);
        findViewById(R.id.f_obs_scene_label).setVisibility(needsScene   ? View.VISIBLE : View.GONE);
        findViewById(R.id.f_obs_source_label).setVisibility(needsSource ? View.VISIBLE : View.GONE);
    }

    private void buildColorSwatches() {
        colorRow.removeAllViews();
        int size = (int)(44 * dp);
        int margin = (int)(6 * dp);
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
        if (label.isEmpty()) { fLabel.setError("Required"); return; }

        String type;
        if (fTypeSound.isChecked())    type = "sound";
        else if (fTypeObs.isChecked()) type = "obs";
        else                           type = "keys";

        DeckButton btn = new DeckButton();
        btn.id         = isNew ? AppState.uid()
                               : state.pages.get(pageIdx).buttons.get(btnIdx).id;
        btn.icon       = icon.isEmpty() ? "▶" : icon;
        btn.label      = label;
        btn.type       = type;
        btn.keys       = fKeys.getText().toString().trim();
        btn.sound      = fSound.getText().toString().trim();
        btn.color      = selectedColor;
        btn.confirmTap = fConfirmTap.isChecked();
        btn.haptic     = fHaptic.isChecked();
        btn.widthSpan  = fWidth2.isChecked() ? 2 : 1;
        btn.obsCommand = (String) fObsCommand.getSelectedItem();
        btn.obsScene   = fObsScene.getText().toString().trim();
        btn.obsSource  = fObsSource.getText().toString().trim();
        btn.obsVolume  = -1f;

        if (isNew) state.pages.get(pageIdx).buttons.add(btn);
        else       state.pages.get(pageIdx).buttons.set(btnIdx, btn);

        state.save();
        finish();
    }

    private void delete() {
        new android.app.AlertDialog.Builder(this)
            .setTitle("Delete button?")
            .setPositiveButton("Delete", (d, w) -> {
                state.pages.get(pageIdx).buttons.remove(btnIdx);
                state.save();
                finish();
            })
            .setNegativeButton("Cancel", null).show();
    }
}

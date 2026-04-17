package com.streamerhelper.app;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;

public class SetupActivity extends AppCompatActivity {
    private EditText ipInput;
    private Button connectBtn;
    private TextView statusText;
    private AppState state;
    private ServerClient client;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_setup);

        state = AppState.get(this);
        ipInput = findViewById(R.id.ip_input);
        connectBtn = findViewById(R.id.connect_btn);
        statusText = findViewById(R.id.status_text);

        if (!state.serverIp.isEmpty()) {
            ipInput.setText(state.serverIp);
        }

        connectBtn.setOnClickListener(v -> {
            String ip = ipInput.getText().toString().trim();
            if (ip.isEmpty()) return;

            statusText.setText(R.string.connecting);
            statusText.setTextColor(0xFFAAAAAA);
            connectBtn.setEnabled(false);

            client = new ServerClient(ip);
            client.ping((ok, msg) -> {
                connectBtn.setEnabled(true);
                if (ok) {
                    state.serverIp = ip;
                    state.save();
                    startActivity(new Intent(this, DeckActivity.class));
                    finish();
                } else {
                    statusText.setText(getString(R.string.server_unreachable, msg));
                    statusText.setTextColor(0xFFff3c6e);
                }
            });
        });

        // If already configured, try to go straight to deck
        if (!state.serverIp.isEmpty()) {
            statusText.setText(getString(R.string.reconnecting_to, state.serverIp));
            client = new ServerClient(state.serverIp);
            client.ping((ok, msg) -> {
                if (ok) {
                    startActivity(new Intent(this, DeckActivity.class));
                    finish();
                } else {
                    statusText.setText(R.string.last_server_unreachable);
                    statusText.setTextColor(0xFFAAAAAA);
                }
            });
        }
    }
}

package com.streamerhelper.app;

import java.util.ArrayList;
import java.util.List;

public class DeckPage {
    public String name;
    public List<DeckButton> buttons;

    public DeckPage() {
        buttons = new ArrayList<>();
    }

    public DeckPage(String name) {
        this.name = name;
        this.buttons = new ArrayList<>();
    }
}

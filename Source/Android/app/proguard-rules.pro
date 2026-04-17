# Keep our own classes intact (data models need their field names for JSON)
-keep class com.streamerhelper.app.** { *; }

# Keep org.json (built into Android, but be explicit)
-keep class org.json.** { *; }

# Remove logging in release builds (saves a tiny bit)
-assumenosideeffects class android.util.Log {
    public static *** d(...);
    public static *** v(...);
}

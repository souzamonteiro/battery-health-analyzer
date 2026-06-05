# Examples - Battery Collector Android App

## Save a BDF file

From the main screen:
- Tap **Save BDF File**.
- The app exports the latest collected samples into app internal storage.

## Upload to the server

From the main screen:
- Tap **Upload BDF to Server**.
- The app uploads the latest saved BDF file.

## Change server host and port

1. Tap **Server Settings**.
2. Enter host and port.
3. Tap **Save Settings**.

## Install APK

```bash
adb install -r /home/roberto/projects/battery-health-analyzer/android/app/build/outputs/apk/debug/app-debug.apk
```

## Rebuild APK

```bash
cd /home/roberto/projects/battery-health-analyzer/android
/home/roberto/projects/battery-health-analyzer/android/.gradle-dist/gradle-8.7/bin/gradle -p /home/roberto/projects/battery-health-analyzer/android :app:assembleDebug --no-daemon
```

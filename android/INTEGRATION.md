# Integration - Android Collector to Web/Server

## Goal

The Android app only collects and uploads raw battery data.
The server performs the same type of processing exposed by the web interface.

## Upload Target

`POST /api/analyze`

Base URL is configured in the app Settings screen:
- Host
- Port

Default value:
- `http://192.168.1.36:8001/api/analyze`

## Uploaded File

The app sends a multipart request with:
- field name: `batteryFile`
- file type: CSV/BDF

## BDF Columns

- `timestamp`
- `level`
- `temperature`
- `voltage`
- `current`
- `cycleCount`
- `health`
- `status`
- `plugged`

## Recommended Workflow

1. Start the Node/Python server on the local machine.
2. Connect phone and computer to the same Wi‑Fi network.
3. Open the Android app.
4. Let it collect samples.
5. Save a BDF file.
6. Upload the BDF file to the server.
7. View analysis in the web interface or through server responses.

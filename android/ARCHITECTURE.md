# Battery Collector Android - Technical Architecture

## Scope

The Android app is a data collector only.
It does not run analysis locally.
Battery prediction and plotting are handled by the remote server.

## Layers

- `MainActivity`: launches UI and starts the collector service.
- `CollectorScreen`: shows collection status and actions.
- `ServerSettingsScreen`: edits server host and port.
- `BatteryCollectorViewModel`: UI state and actions.
- `BatteryRepository`: battery access + Room database access.
- `BatteryCollectorService`: foreground background collector.
- `ServerUploader`: uploads BDF files to the server.
- `ServerSettingsStore`: persists host/port locally.

## Data Flow

1. `BatteryCollectorService` reads `ACTION_BATTERY_CHANGED`.
2. Repository stores samples in Room.
3. UI observes latest sample count and last values.
4. User saves BDF locally.
5. User uploads BDF to `http://<host>:<port>/api/analyze`.
6. Server performs all heavy processing.

## Default Server

- Host: `192.168.1.36`
- Port: `8001`

## Crash Prevention

- Foreground service type declared in manifest.
- Service start wrapped safely in `MainActivity`.
- Single collection loop guarded inside service.
- Stable system notification icon used.

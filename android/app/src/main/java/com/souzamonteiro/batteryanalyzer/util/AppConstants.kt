package com.souzamonteiro.batteryanalyzer.util

/**
 * Constantes da aplicação
 */
object AppConstants {
    const val MINIMUM_SAMPLES_FOR_EXPORT = 100
    const val COLLECTION_INTERVAL_MINUTES = 1
    const val DATA_RETENTION_DAYS = 90

    object Database {
        const val DB_NAME = "battery_database"
        const val DB_VERSION = 1
        const val TABLE_NAME = "battery_samples"
    }

    object Service {
        const val NOTIFICATION_ID = 1
        const val CHANNEL_ID = "battery_collector"
        const val CHANNEL_NAME = "Battery Collection"
    }

    object Export {
        const val FILE_EXTENSION = ".bdf.csv"
        const val FILENAME_FORMAT = "battery_yyyyMMdd_HHmmss"
        const val HEADER = "timestamp,level,temperature,voltage,current,cycleCount,health,status,plugged"
    }

    object Status {
        const val CHARGING = "CHARGING"
        const val DISCHARGING = "DISCHARGING"
        const val FULL = "FULL"
        const val UNKNOWN = "UNKNOWN"
    }

    object HealthThresholds {
        const val EXCELLENT = 80
        const val GOOD = 70
    }
}

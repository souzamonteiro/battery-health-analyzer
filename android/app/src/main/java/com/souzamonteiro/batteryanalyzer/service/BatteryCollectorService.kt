package com.souzamonteiro.batteryanalyzer.service

import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.os.Build
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.pm.ServiceInfo
import androidx.core.app.NotificationCompat
import com.souzamonteiro.batteryanalyzer.R
import com.souzamonteiro.batteryanalyzer.repository.BatteryRepository
import com.souzamonteiro.batteryanalyzer.util.BDFExporter
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.io.File

class BatteryCollectorService : Service() {
    private val serviceScope = CoroutineScope(Dispatchers.Default + Job())
    private lateinit var repository: BatteryRepository
    private var started = false

    companion object {
        private const val NOTIFICATION_ID = 1
        private const val NOTIFICATION_CHANNEL_ID = "battery_collector"
        private const val COLLECTION_INTERVAL_MS = 60000L // 1 minute
    }

    override fun onCreate() {
        super.onCreate()
        repository = BatteryRepository(this)
        createNotificationChannel()
        startForegroundService()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!started) {
            started = true
            serviceScope.launch {
                collectBatteryData()
            }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                "Battery Collection",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Collecting battery health data"
                setShowBadge(false)
            }
            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager?.createNotificationChannel(channel)
        }
    }

    private fun startForegroundService() {
        val notification = NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setContentTitle("Battery Analyzer")
            .setContentText("Collecting battery data...")
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private suspend fun collectBatteryData() {
        while (true) {
            try {
                val sample = repository.getCurrentBatteryStatus()
                sample?.let {
                    repository.insertSample(it)
                    repository.saveLiveSnapshot(File(filesDir, BDFExporter.LIVE_SNAPSHOT_FILENAME))
                }
                delay(COLLECTION_INTERVAL_MS)
            } catch (e: Exception) {
                e.printStackTrace()
                delay(COLLECTION_INTERVAL_MS)
            }
        }
    }
}

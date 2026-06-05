package com.souzamonteiro.batteryanalyzer.repository

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.ContentValues
import android.os.Build
import android.os.BatteryManager
import android.os.Environment
import android.provider.MediaStore
import com.souzamonteiro.batteryanalyzer.data.BatterySample
import com.souzamonteiro.batteryanalyzer.data.BatteryDatabase
import com.souzamonteiro.batteryanalyzer.util.BDFExporter
import kotlinx.coroutines.flow.Flow
import java.io.File

class BatteryRepository(private val context: Context) {
    private val database = BatteryDatabase.getInstance(context)
    private val dao = database.batterySampleDao()

    fun getAllSamples(): Flow<List<BatterySample>> = dao.getAllSamples()

    fun getRecentSamples(limit: Int = 1000): Flow<List<BatterySample>> = dao.getRecentSamples(limit)

    fun getSampleCount(): Flow<Int> = dao.getSampleCount()

    fun getAverageLevel(): Flow<Double> = dao.getAverageLevel()

    suspend fun insertSample(sample: BatterySample) {
        dao.insert(sample)
    }

    suspend fun deleteOldSamples(cutoffTime: Long) {
        dao.deleteOldSamples(cutoffTime)
    }

    suspend fun deleteAll() {
        dao.deleteAll()
    }

    suspend fun saveLiveSnapshot(outputFile: File): Boolean {
        val samples = dao.getAllSamplesOnce()
        return BDFExporter.exportSnapshot(samples, outputFile)
    }

    suspend fun saveBdfCopyToDownloads(fileName: String): File? {
        val samples = dao.getAllSamplesOnce()
        if (samples.isEmpty()) return null

        val content = BDFExporter.buildBdfContent(samples)

        val primary = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            saveToMediaStoreDownloads(fileName, content)
        } else {
            saveToAppExternalDocuments(fileName, content)
        }

        if (primary != null) return primary

        val fallback = File(context.filesDir, fileName)
        return try {
            fallback.writeText(content)
            fallback
        } catch (_: Exception) {
            null
        }
    }

    private fun saveToMediaStoreDownloads(fileName: String, content: String): File? {
        val resolver = context.contentResolver
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, fileName)
            put(MediaStore.MediaColumns.MIME_TYPE, "text/csv")
            put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/BatteryAnalyzer")
            put(MediaStore.MediaColumns.IS_PENDING, 1)
        }

        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values) ?: return null

        return try {
            resolver.openOutputStream(uri)?.use { output ->
                output.write(content.toByteArray())
            } ?: return null

            values.clear()
            values.put(MediaStore.MediaColumns.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
            File("/sdcard/${Environment.DIRECTORY_DOWNLOADS}/BatteryAnalyzer/$fileName")
        } catch (_: Exception) {
            resolver.delete(uri, null, null)
            null
        }
    }

    private fun saveToAppExternalDocuments(fileName: String, content: String): File? {
        val directory = context.getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS) ?: return null
        val outputFile = File(directory, fileName)
        return try {
            outputFile.writeText(content)
            outputFile
        } catch (_: Exception) {
            null
        }
    }

    fun getCurrentBatteryStatus(): BatterySample? {
        val iFilter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        val batteryStatus = context.registerReceiver(null, iFilter)

        return batteryStatus?.let {
            val level = it.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
            val scale = it.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
            val temp = it.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0)
            val voltage = it.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 0)
            val plugged = it.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0)
            val status = it.getIntExtra(BatteryManager.EXTRA_STATUS, BatteryManager.BATTERY_STATUS_UNKNOWN)
            val health = it.getIntExtra(BatteryManager.EXTRA_HEALTH, BatteryManager.BATTERY_HEALTH_UNKNOWN)

            val statusString = when (status) {
                BatteryManager.BATTERY_STATUS_CHARGING -> "CHARGING"
                BatteryManager.BATTERY_STATUS_DISCHARGING -> "DISCHARGING"
                BatteryManager.BATTERY_STATUS_FULL -> "FULL"
                else -> "UNKNOWN"
            }

            val levelPercent = (level * 100) / scale

            BatterySample(
                timestamp = System.currentTimeMillis(),
                level = levelPercent,
                temperature = temp,
                voltage = voltage,
                current = 0, // Cannot directly get current without privileged access
                cycleCount = 0, // Not available via public API
                health = health,
                status = statusString,
                plugged = plugged
            )
        }
    }
}

package com.souzamonteiro.batteryanalyzer.util

import com.souzamonteiro.batteryanalyzer.data.BatterySample
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object BDFExporter {
    const val MINIMUM_SAMPLES = 100
    const val BDF_EXTENSION = ".bdf.csv"
    const val LIVE_SNAPSHOT_FILENAME = "battery_live_snapshot.bdf.csv"

    fun exportToBDF(samples: List<BatterySample>, outputFile: File): Boolean {
        if (samples.size < MINIMUM_SAMPLES) {
            return false
        }

        return try {
            outputFile.writeText(generateBDFContent(samples))
            true
        } catch (e: Exception) {
            e.printStackTrace()
            false
        }
    }

    fun exportSnapshot(samples: List<BatterySample>, outputFile: File): Boolean {
        if (samples.isEmpty()) {
            return false
        }

        return try {
            outputFile.writeText(generateBDFContent(samples))
            true
        } catch (e: Exception) {
            e.printStackTrace()
            false
        }
    }

    private fun generateBDFContent(samples: List<BatterySample>): String {
        val header = "Test Time / s,Unix Time / s,Voltage / V,Current / A,Cycle Count / 1,Ambient Temperature / degC,Power / W,Capacity / %,Health / %,Status / 1,Plugged / 1\n"

        val sortedSamples = samples.sortedBy { it.timestamp }
        val startTimestamp = sortedSamples.firstOrNull()?.timestamp ?: 0L
        val dataLines = sortedSamples.joinToString("\n") { sample ->
            val testTimeSec = ((sample.timestamp - startTimestamp).coerceAtLeast(0L) / 1000.0)
            val unixTimeSec = sample.timestamp / 1000.0
            val voltageVolt = sample.voltage / 1000.0
            val currentAmpere = sample.current / 1000.0
            val temperatureC = sample.temperature / 10.0
            val powerWatt = voltageVolt * currentAmpere

            "${"%.3f".format(Locale.US, testTimeSec)},${"%.0f".format(Locale.US, unixTimeSec)},${"%.3f".format(Locale.US, voltageVolt)},${"%.3f".format(Locale.US, currentAmpere)},${sample.cycleCount},${"%.1f".format(Locale.US, temperatureC)},${"%.3f".format(Locale.US, powerWatt)},${sample.level},${sample.health},${sample.status},${sample.plugged}"
        }

        return header + dataLines + "\n"
    }

    fun buildBdfContent(samples: List<BatterySample>): String {
        return generateBDFContent(samples)
    }

    fun generateBDFFilename(): String {
        val sdf = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US)
        val timestamp = sdf.format(Date())
        return "battery_$timestamp$BDF_EXTENSION"
    }

    fun parseCSVLine(line: String): Map<String, String> {
        val columns = listOf(
            "timestamp", "level", "temperature", "voltage", "current",
            "cycleCount", "health", "status", "plugged"
        )
        val values = line.split(",")
        return columns.zip(values).toMap()
    }

    fun calculateStatistics(samples: List<BatterySample>): BatteryStatistics {
        if (samples.isEmpty()) {
            return BatteryStatistics()
        }

        val levels = samples.map { it.level }
        val temps = samples.map { it.temperature }
        val healths = samples.map { it.health }

        return BatteryStatistics(
            sampleCount = samples.size,
            avgLevel = levels.average(),
            minLevel = levels.minOrNull() ?: 0,
            maxLevel = levels.maxOrNull() ?: 100,
            avgTemperature = temps.average(),
            minHealth = healths.minOrNull() ?: 0,
            maxHealth = healths.maxOrNull() ?: 100,
            timeSpanDays = (samples.maxOfOrNull { it.timestamp }?.minus(
                samples.minOfOrNull { it.timestamp } ?: 0
            ) ?: 0) / (1000 * 60 * 60 * 24)
        )
    }
}

data class BatteryStatistics(
    val sampleCount: Int = 0,
    val avgLevel: Double = 0.0,
    val minLevel: Int = 0,
    val maxLevel: Int = 100,
    val avgTemperature: Double = 0.0,
    val minHealth: Int = 0,
    val maxHealth: Int = 100,
    val timeSpanDays: Long = 0
)

package com.souzamonteiro.batteryanalyzer.data

import android.content.Context
import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.Dao
import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.Insert
import androidx.room.Query
import androidx.room.Delete
import androidx.room.Room
import kotlinx.coroutines.flow.Flow
import java.time.LocalDateTime

@Entity(tableName = "battery_samples")
data class BatterySample(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val timestamp: Long, // Unix timestamp in milliseconds
    val level: Int, // Battery level 0-100
    val temperature: Int, // Temperature in Celsius * 10
    val voltage: Int, // Voltage in mV
    val current: Int, // Current in mA
    val cycleCount: Int, // Charge cycles
    val health: Int, // Battery health 0-100
    val status: String, // CHARGING, DISCHARGING, FULL, UNKNOWN
    val plugged: Int // 0=unplugged, 1=AC, 2=USB, 4=wireless
)

@Dao
interface BatterySampleDao {
    @Insert
    suspend fun insert(sample: BatterySample)

    @Query("SELECT * FROM battery_samples ORDER BY timestamp ASC")
    suspend fun getAllSamplesOnce(): List<BatterySample>

    @Query("SELECT * FROM battery_samples ORDER BY timestamp DESC")
    fun getAllSamples(): Flow<List<BatterySample>>

    @Query("SELECT * FROM battery_samples ORDER BY timestamp DESC LIMIT :limit")
    fun getRecentSamples(limit: Int = 1000): Flow<List<BatterySample>>

    @Query("SELECT COUNT(*) FROM battery_samples")
    fun getSampleCount(): Flow<Int>

    @Query("SELECT MIN(timestamp) FROM battery_samples")
    fun getFirstSampleTimestamp(): Flow<Long?>

    @Query("DELETE FROM battery_samples WHERE timestamp < :cutoffTime")
    suspend fun deleteOldSamples(cutoffTime: Long)

    @Query("DELETE FROM battery_samples")
    suspend fun deleteAll()

    @Query("SELECT AVG(level) FROM battery_samples")
    fun getAverageLevel(): Flow<Double>
}

@Database(entities = [BatterySample::class], version = 1, exportSchema = false)
abstract class BatteryDatabase : RoomDatabase() {
    abstract fun batterySampleDao(): BatterySampleDao

    companion object {
        @Volatile
        private var instance: BatteryDatabase? = null

        fun getInstance(context: Context): BatteryDatabase {
            return instance ?: synchronized(this) {
                Room.databaseBuilder(
                    context.applicationContext,
                    BatteryDatabase::class.java,
                    "battery_database"
                )
                    .fallbackToDestructiveMigration()
                    .build()
                    .also { instance = it }
            }
        }
    }
}

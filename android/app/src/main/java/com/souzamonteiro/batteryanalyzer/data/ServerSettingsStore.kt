package com.souzamonteiro.batteryanalyzer.data

import android.content.Context
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

class ServerSettingsStore(context: Context) {
    private val prefs = context.getSharedPreferences("server_settings", Context.MODE_PRIVATE)

    private val hostState = MutableStateFlow(
        prefs.getString(KEY_HOST, DEFAULT_HOST) ?: DEFAULT_HOST
    )
    private val portState = MutableStateFlow(
        migratePortIfNeeded(prefs.getInt(KEY_PORT, DEFAULT_PORT))
    )

    init {
        if (prefs.getInt(KEY_PORT, DEFAULT_PORT) == 8001) {
            prefs.edit().putInt(KEY_PORT, DEFAULT_PORT).apply()
        }
    }

    fun hostFlow(): Flow<String> = hostState.asStateFlow()
    fun portFlow(): Flow<Int> = portState.asStateFlow()

    fun getHost(): String = hostState.value
    fun getPort(): Int = portState.value

    fun save(host: String, port: Int) {
        val cleanHost = host.trim().ifEmpty { DEFAULT_HOST }
        val cleanPort = if (port in 1..65535) port else DEFAULT_PORT

        prefs.edit()
            .putString(KEY_HOST, cleanHost)
            .putInt(KEY_PORT, cleanPort)
            .apply()

        hostState.value = cleanHost
        portState.value = cleanPort
    }

    companion object {
        private const val KEY_HOST = "host"
        private const val KEY_PORT = "port"
        private const val DEFAULT_HOST = "192.168.1.36"
        private const val DEFAULT_PORT = 8000
    }

    private fun migratePortIfNeeded(storedPort: Int): Int {
        return if (storedPort == 8001) DEFAULT_PORT else storedPort
    }
}

package com.souzamonteiro.batteryanalyzer.ui

import android.content.Intent
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.ViewModelProvider
import com.souzamonteiro.batteryanalyzer.data.ServerSettingsStore
import com.souzamonteiro.batteryanalyzer.repository.BatteryRepository
import com.souzamonteiro.batteryanalyzer.service.BatteryCollectorService
import com.souzamonteiro.batteryanalyzer.ui.theme.BatteryAnalyzerTheme
import com.souzamonteiro.batteryanalyzer.viewmodel.BatteryCollectorViewModel
import com.souzamonteiro.batteryanalyzer.viewmodel.BatteryCollectorViewModelFactory

class MainActivity : ComponentActivity() {
    private lateinit var viewModel: BatteryCollectorViewModel

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Initialize ViewModel
        val repository = BatteryRepository(this)
        val settingsStore = ServerSettingsStore(this)
        val factory = BatteryCollectorViewModelFactory(repository, settingsStore, filesDir)
        viewModel = ViewModelProvider(this, factory)[BatteryCollectorViewModel::class.java]

        // Start background collector service
        startBatteryCollectorService()

        setContent {
            BatteryAnalyzerTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = Color(0xFFF4F7FB)
                ) {
                    var showSettings by remember { mutableStateOf(false) }
                    val state by viewModel.uiState.collectAsStateWithLifecycle()

                    Scaffold(
                        modifier = Modifier.fillMaxSize(),
                        contentColor = Color(0xFF1B2430)
                    ) { _ ->
                        if (showSettings) {
                            ServerSettingsScreen(
                                initialHost = state.serverHost,
                                initialPort = state.serverPort,
                                onSave = { host, port -> viewModel.saveServerSettings(host, port) },
                                onBack = { showSettings = false }
                            )
                        } else {
                            CollectorScreen(
                                viewModel = viewModel,
                                state = state,
                                onOpenSettings = { showSettings = true }
                            )
                        }
                    }
                }
            }
        }
    }

    private fun startBatteryCollectorService() {
        val serviceIntent = Intent(this, BatteryCollectorService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(serviceIntent)
            } else {
                startService(serviceIntent)
            }
        } catch (_: Exception) {
            // App remains usable even if service start fails on specific OEM restrictions.
        }
    }
}

package com.souzamonteiro.batteryanalyzer.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.souzamonteiro.batteryanalyzer.data.ServerSettingsStore
import com.souzamonteiro.batteryanalyzer.network.AnalysisPlot
import com.souzamonteiro.batteryanalyzer.network.AnalysisReport
import com.souzamonteiro.batteryanalyzer.network.ServerUploader
import com.souzamonteiro.batteryanalyzer.repository.BatteryRepository
import com.souzamonteiro.batteryanalyzer.util.BDFExporter
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class CollectorUiState(
    val sampleCount: Int = 0,
    val firstTimestamp: Long? = null,
    val latestLevel: Int? = null,
    val latestTemp: Int? = null,
    val latestTimestamp: Long? = null,
    val statusMessage: String = "",
    val liveSnapshotPath: String = "",
    val lastSavedPath: String? = null,
    val isBusy: Boolean = false,
    val serverHost: String = "192.168.1.36",
    val serverPort: Int = 8000,
    val eolThreshold: String = "70",
    val svrDays: String = "30",
    val analysisReport: AnalysisReport? = null,
    val plots: List<AnalysisPlot> = emptyList()
)

class BatteryCollectorViewModel(
    private val repository: BatteryRepository,
    private val settingsStore: ServerSettingsStore,
    private val filesDir: File
) : ViewModel() {

    private companion object {
        const val MIN_SAMPLES_FOR_SERVER_ANALYSIS = 2
    }

    private val liveSnapshotFile = File(filesDir, BDFExporter.LIVE_SNAPSHOT_FILENAME)
    private val _uiState = MutableStateFlow(CollectorUiState(liveSnapshotPath = liveSnapshotFile.absolutePath))
    val uiState: StateFlow<CollectorUiState> = _uiState.asStateFlow()

    init {
        observeData()
        observeSettings()
    }

    private fun observeData() {
        viewModelScope.launch {
            repository.getSampleCount().collect { count ->
                _uiState.value = _uiState.value.copy(sampleCount = count)
            }
        }

        viewModelScope.launch {
            repository.getFirstSampleTimestamp().collect { first ->
                _uiState.value = _uiState.value.copy(firstTimestamp = first)
            }
        }

        viewModelScope.launch {
            repository.getRecentSamples(1).collect { samples ->
                val latest = samples.firstOrNull()
                _uiState.value = _uiState.value.copy(
                    latestLevel = latest?.level,
                    latestTemp = latest?.temperature,
                    latestTimestamp = latest?.timestamp
                )
            }
        }
    }

    private fun observeSettings() {
        viewModelScope.launch {
            settingsStore.hostFlow().collect { host ->
                _uiState.value = _uiState.value.copy(serverHost = host)
            }
        }
        viewModelScope.launch {
            settingsStore.portFlow().collect { port ->
                _uiState.value = _uiState.value.copy(serverPort = port)
            }
        }
    }

    fun saveServerSettings(host: String, portText: String) {
        val port = portText.toIntOrNull() ?: 9543
        settingsStore.save(host, port)
        _uiState.value = _uiState.value.copy(statusMessage = "Settings saved")
    }

    fun updateAnalysisParams(eolThreshold: String, svrDays: String) {
        _uiState.value = _uiState.value.copy(
            eolThreshold = eolThreshold,
            svrDays = svrDays
        )
    }

    fun saveBdfCopy() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isBusy = true)
            val file = repository.saveBdfCopyToDownloads(BDFExporter.generateBDFFilename())
            if (file == null) {
                _uiState.value = _uiState.value.copy(
                    isBusy = false,
                    statusMessage = "Not enough samples yet. Keep collecting and try again."
                )
                return@launch
            }

            _uiState.value = _uiState.value.copy(
                isBusy = false,
                statusMessage = "Saved file to Downloads/BatteryAnalyzer",
                lastSavedPath = file.absolutePath
            )
        }
    }

    fun runServerAnalysis() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isBusy = true, plots = emptyList())

            if (_uiState.value.sampleCount < MIN_SAMPLES_FOR_SERVER_ANALYSIS) {
                _uiState.value = _uiState.value.copy(
                    isBusy = false,
                    statusMessage = "Not enough samples yet. Keep collecting until at least 2 samples are available."
                )
                return@launch
            }

            var bdfFile = resolveLatestBdfFile()

            if (bdfFile == null) {
                repository.saveLiveSnapshot(liveSnapshotFile)
                bdfFile = resolveLatestBdfFile()
            }

            if (bdfFile == null || !bdfFile.exists()) {
                _uiState.value = _uiState.value.copy(
                    isBusy = false,
                    statusMessage = "No live BDF snapshot found yet. Keep the collector running for at least one minute."
                )
                return@launch
            }

            val eol = _uiState.value.eolThreshold.toDoubleOrNull() ?: 70.0
            val svrDays = _uiState.value.svrDays.toIntOrNull() ?: 30

            val result = ServerUploader.uploadBdf(
                file = bdfFile,
                host = _uiState.value.serverHost,
                port = _uiState.value.serverPort,
                eol = eol,
                svrDays = svrDays
            )

            _uiState.value = result.fold(
                onSuccess = { response ->
                    _uiState.value.copy(
                        isBusy = false,
                        statusMessage = "Analysis complete. Job ID: ${response.jobId}",
                        analysisReport = response.report,
                        plots = response.plots,
                        lastSavedPath = bdfFile.absolutePath
                    )
                },
                onFailure = { error ->
                    _uiState.value.copy(
                        isBusy = false,
                        analysisReport = null,
                        plots = emptyList(),
                        statusMessage = "Upload failed: ${error.message ?: "Unknown error"}"
                    )
                }
            )
        }
    }

    private fun resolveLatestBdfFile(): File? {
        if (liveSnapshotFile.exists()) return liveSnapshotFile

        val lastSaved = _uiState.value.lastSavedPath?.let(::File)
        if (lastSaved != null && lastSaved.exists()) return lastSaved

        return filesDir.listFiles()
            ?.filter { it.name.endsWith(".bdf.csv") }
            ?.maxByOrNull { it.lastModified() }
    }

    fun formatTimestamp(ts: Long?): String {
        if (ts == null) return "Unknown"
        return SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date(ts))
    }

    fun estimateCollectionDays(firstTs: Long?, latestTs: Long?): Int? {
        if (firstTs == null || latestTs == null || latestTs < firstTs) return null
        val millisPerDay = 24L * 60L * 60L * 1000L
        return ((latestTs - firstTs) / millisPerDay).toInt()
    }
}

class BatteryCollectorViewModelFactory(
    private val repository: BatteryRepository,
    private val settingsStore: ServerSettingsStore,
    private val filesDir: File
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(BatteryCollectorViewModel::class.java)) {
            @Suppress("UNCHECKED_CAST")
            return BatteryCollectorViewModel(repository, settingsStore, filesDir) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}

package com.souzamonteiro.batteryanalyzer.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.souzamonteiro.batteryanalyzer.network.AnalysisReport
import com.souzamonteiro.batteryanalyzer.viewmodel.BatteryCollectorViewModel
import com.souzamonteiro.batteryanalyzer.viewmodel.CollectorUiState

@Composable
fun CollectorScreen(
    viewModel: BatteryCollectorViewModel,
    state: CollectorUiState,
    onOpenSettings: () -> Unit
) {
    var eolInput by remember(state.eolThreshold) { mutableStateOf(state.eolThreshold) }
    var svrDaysInput by remember(state.svrDays) { mutableStateOf(state.svrDays) }
    var consentAccepted by rememberSaveable { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFFF4F7FB))
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        HeroCard()

        Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp), color = Color.White) {
            Column(modifier = Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Collector Status", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
                KeyValueRow("Samples collected", state.sampleCount.toString())
                KeyValueRow("Latest battery level", state.latestLevel?.let { "$it%" } ?: "Unknown")
                KeyValueRow("Latest temperature", state.latestTemp?.let { "${it / 10.0}°C" } ?: "Unknown")
                KeyValueRow("Last sample time", viewModel.formatTimestamp(state.latestTimestamp))
                KeyValueRow("Live BDF snapshot", state.liveSnapshotPath)
                Text(
                    if (state.sampleCount < 100) "Data is still limited. More samples improve server-side prediction quality."
                    else "Enough data collected for a stronger analysis run.",
                    color = if (state.sampleCount < 100) Color(0xFFB26A00) else Color(0xFF0F9D58),
                    fontSize = 12.sp
                )
            }
        }

        Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp), color = Color.White) {
            BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
                val isCompact = maxWidth < 560.dp

                Column(modifier = Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Analyze Current Snapshot", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)

                    if (isCompact) {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                            OutlinedTextField(
                                value = eolInput,
                                onValueChange = {
                                    eolInput = it
                                    viewModel.updateAnalysisParams(eolInput, svrDaysInput)
                                },
                                label = { Text("EOL threshold (%)") },
                                modifier = Modifier.fillMaxWidth(),
                                singleLine = true
                            )
                            OutlinedTextField(
                                value = svrDaysInput,
                                onValueChange = {
                                    svrDaysInput = it.filter { c -> c.isDigit() }
                                    viewModel.updateAnalysisParams(eolInput, svrDaysInput)
                                },
                                label = { Text("SVR horizon (days)") },
                                modifier = Modifier.fillMaxWidth(),
                                singleLine = true
                            )
                        }
                    } else {
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                            OutlinedTextField(
                                value = eolInput,
                                onValueChange = {
                                    eolInput = it
                                    viewModel.updateAnalysisParams(eolInput, svrDaysInput)
                                },
                                label = { Text("EOL threshold (%)") },
                                modifier = Modifier.weight(1f),
                                singleLine = true
                            )
                            OutlinedTextField(
                                value = svrDaysInput,
                                onValueChange = {
                                    svrDaysInput = it.filter { c -> c.isDigit() }
                                    viewModel.updateAnalysisParams(eolInput, svrDaysInput)
                                },
                                label = { Text("SVR horizon (days)") },
                                modifier = Modifier.weight(1f),
                                singleLine = true
                            )
                        }
                    }

                    if (isCompact) {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                            Button(
                                onClick = { viewModel.runServerAnalysis() },
                                enabled = !state.isBusy && consentAccepted,
                                modifier = Modifier.fillMaxWidth().height(48.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF2A6CF6)),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Text("Run Analysis", color = Color.White, maxLines = 1)
                            }
                            OutlinedButton(
                                onClick = { viewModel.saveBdfCopy() },
                                enabled = !state.isBusy,
                                modifier = Modifier.fillMaxWidth().height(48.dp),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Text("Save Snapshot Copy", maxLines = 1)
                            }
                        }
                    } else {
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                            Button(
                                onClick = { viewModel.runServerAnalysis() },
                                enabled = !state.isBusy && consentAccepted,
                                modifier = Modifier.weight(1f).height(48.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF2A6CF6)),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Text("Run Analysis", color = Color.White, maxLines = 1)
                            }
                            OutlinedButton(
                                onClick = { viewModel.saveBdfCopy() },
                                enabled = !state.isBusy,
                                modifier = Modifier.weight(1f).height(48.dp),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Text("Save Snapshot Copy", maxLines = 1)
                            }
                        }
                    }

                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        color = Color(0xFFF3F6FC),
                        shape = RoundedCornerShape(10.dp)
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { consentAccepted = !consentAccepted }
                                .padding(12.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalAlignment = Alignment.Top
                        ) {
                            Checkbox(
                                checked = consentAccepted,
                                onCheckedChange = { consentAccepted = it },
                                modifier = Modifier.padding(top = 1.dp)
                            )
                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(
                                    "By submitting battery data files, I agree to dedicate the submitted data to the public domain under Creative Commons CC0 1.0 (No Copyright).",
                                    color = Color(0xFF1B2430),
                                    fontSize = 13.sp,
                                    lineHeight = 18.sp
                                )
                                Text(
                                    "You must accept these conditions before sending the snapshot to the server.",
                                    color = Color(0xFF5A6778),
                                    fontSize = 12.sp
                                )
                            }
                        }
                    }

                    OutlinedButton(onClick = onOpenSettings, modifier = Modifier.fillMaxWidth()) {
                        Text("Server Settings (${state.serverHost}:${state.serverPort})", maxLines = 2)
                    }
                }
            }
        }

        state.analysisReport?.let { report ->
            AnalysisResultCard(report)
            PlotGrid(state)
        }

        if (state.statusMessage.isNotBlank()) {
            Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp), color = Color(0xFFEAF1FF)) {
                Text(state.statusMessage, modifier = Modifier.padding(12.dp), color = Color(0xFF1D3C76), fontSize = 13.sp)
            }
        }
    }
}

@Composable
private fun HeroCard() {
    Surface(modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)), color = Color(0xFF2A6CF6), shape = RoundedCornerShape(18.dp)) {
        Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Battery Health Analyzer", color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.Bold)
            Text("The app continuously saves battery data locally and sends the current snapshot to the server, just like the web interface.", color = Color.White, fontSize = 14.sp)
        }
    }
}

@Composable
private fun AnalysisResultCard(report: AnalysisReport) {
    Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp), color = Color.White) {
        Column(modifier = Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Text("Server Analysis Result", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            BatteryHealthVisual(report.currentSohPercent, report.linearRulHuman, report.svrRulHuman)
            Surface(color = Color(0xFFEAF1FF), shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Input: ${report.inputFile}")
                    Text("Samples: ${report.samples}")
                    Text("Linear R²: ${"%.4f".format(report.linearR2)} | SVR R²: ${"%.4f".format(report.svrR2)}")
                }
            }
        }
    }
}

@Composable
private fun BatteryHealthVisual(sohPercent: Double, linearRul: String, svrRul: String) {
    val fillColor = when {
        sohPercent > 80.0 -> Color(0xFF188038)
        sohPercent >= 70.0 -> Color(0xFFF9AB00)
        else -> Color(0xFFD93025)
    }
    val statusText = when {
        sohPercent > 80.0 -> "Excellent Health"
        sohPercent >= 70.0 -> "Good Health"
        else -> "Poor Health"
    }

    BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
        val isCompact = maxWidth < 640.dp
        val batteryBodyWidth = when {
            maxWidth > 360.dp -> 240.dp
            maxWidth > 310.dp -> 210.dp
            else -> 170.dp
        }

        if (isCompact) {
            Column(verticalArrangement = Arrangement.spacedBy(14.dp), modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(0.dp)) {
                        Box(
                            modifier = Modifier
                                .width(batteryBodyWidth)
                                .height(88.dp)
                                .border(3.dp, Color(0xFF1B2430), RoundedCornerShape(12.dp))
                                .clip(RoundedCornerShape(12.dp))
                                .background(Color(0xFFF0F0F0))
                                .padding(4.dp)
                        ) {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(80.dp)
                                    .clip(RoundedCornerShape(9.dp))
                                    .background(Color(0xFFE7EBF0))
                            )
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth((sohPercent / 100.0).toFloat().coerceIn(0f, 1f))
                                    .height(80.dp)
                                    .clip(RoundedCornerShape(9.dp))
                                    .background(fillColor)
                            )
                        }
                        Box(
                            modifier = Modifier
                                .width(12.dp)
                                .height(30.dp)
                                .clip(RoundedCornerShape(topEnd = 4.dp, bottomEnd = 4.dp))
                                .background(Color(0xFF1B2430))
                        )
                    }
                    Text("${"%.1f".format(sohPercent)}%", fontSize = 26.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 8.dp))
                    Text(statusText, color = fillColor, fontWeight = FontWeight.SemiBold, fontSize = 13.sp, modifier = Modifier.padding(top = 4.dp))
                }

                Column(modifier = Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    BadgeRow("Current SOH", "${"%.2f".format(sohPercent)}%")
                    BadgeRow("Linear RUL", linearRul)
                    BadgeRow("SVR RUL", svrRul)
                }
            }
        } else {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(0.dp)) {
                            Box(
                                modifier = Modifier
                                    .width(240.dp)
                                    .height(100.dp)
                                    .border(3.dp, Color(0xFF1B2430), RoundedCornerShape(12.dp))
                                    .clip(RoundedCornerShape(12.dp))
                                    .background(Color(0xFFF0F0F0))
                                    .padding(4.dp)
                            ) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(92.dp)
                                        .clip(RoundedCornerShape(9.dp))
                                        .background(Color(0xFFE7EBF0))
                                )
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth((sohPercent / 100.0).toFloat().coerceIn(0f, 1f))
                                        .height(92.dp)
                                        .clip(RoundedCornerShape(9.dp))
                                        .background(fillColor)
                                )
                            }
                            Box(
                                modifier = Modifier
                                    .width(14.dp)
                                    .height(34.dp)
                                    .clip(RoundedCornerShape(topEnd = 4.dp, bottomEnd = 4.dp))
                                    .background(Color(0xFF1B2430))
                            )
                        }
                        Text("${"%.1f".format(sohPercent)}%", fontSize = 28.sp, fontWeight = FontWeight.Bold)
                    }
                    Text(statusText, color = fillColor, fontWeight = FontWeight.SemiBold, fontSize = 13.sp, modifier = Modifier.padding(top = 8.dp))
                }

                Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    BadgeRow("Current SOH", "${"%.2f".format(sohPercent)}%")
                    BadgeRow("Linear RUL", linearRul)
                    BadgeRow("SVR RUL", svrRul)
                }
            }
        }
    }
}

@Composable
private fun PlotGrid(state: CollectorUiState) {
    if (state.plots.isEmpty()) return

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Generated Plots", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
        state.plots.forEach { plot ->
            Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp), color = Color.White) {
                Column {
                    Text(plot.name, modifier = Modifier.padding(12.dp), fontWeight = FontWeight.SemiBold)
                    AsyncImage(
                        model = plot.url,
                        contentDescription = plot.name,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.fillMaxWidth().height(220.dp)
                    )
                }
            }
        }
    }
}

@Composable
private fun BadgeRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = Color(0xFF5A6778), fontSize = 13.sp)
        Text(value, color = Color(0xFF1B2430), fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
    }
}

@Composable
fun ServerSettingsScreen(
    initialHost: String,
    initialPort: Int,
    onSave: (String, String) -> Unit,
    onBack: () -> Unit
) {
    var host by remember { mutableStateOf(initialHost) }
    var port by remember { mutableStateOf(initialPort.toString()) }

    Column(
        modifier = Modifier.fillMaxSize().background(Color(0xFFF4F7FB)).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp), color = Color.White) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Server Settings", fontWeight = FontWeight.SemiBold, fontSize = 18.sp)
                OutlinedTextField(value = host, onValueChange = { host = it }, label = { Text("Server Host") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OutlinedTextField(value = port, onValueChange = { port = it.filter { c -> c.isDigit() } }, label = { Text("Server Port") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                    OutlinedButton(onClick = onBack, modifier = Modifier.weight(1f)) { Text("Back") }
                    Button(onClick = { onSave(host, port); onBack() }, modifier = Modifier.weight(1f)) { Text("Save Settings") }
                }
            }
        }
    }
}

@Composable
private fun KeyValueRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
        Text(label, color = Color(0xFF5A6778), fontSize = 13.sp)
        Text(value, color = Color(0xFF1B2430), fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
    }
}

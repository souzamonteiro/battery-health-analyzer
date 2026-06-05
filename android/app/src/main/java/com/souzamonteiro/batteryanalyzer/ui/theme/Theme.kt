package com.souzamonteiro.batteryanalyzer.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColorScheme = lightColorScheme(
    primary = Color(0xFF2A6CF6),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFEAF1FF),
    onPrimaryContainer = Color(0xFF1D3C76),
    secondary = Color(0xFF0F9D58),
    onSecondary = Color.White,
    tertiary = Color(0xFFD93025),
    onTertiary = Color.White,
    background = Color(0xFFF4F7FB),
    onBackground = Color(0xFF1B2430),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF1B2430),
    outlineVariant = Color(0xFFD9E2EF)
)

@Composable
fun BatteryAnalyzerTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LightColorScheme,
        typography = androidx.compose.material3.Typography(),
        content = content
    )
}

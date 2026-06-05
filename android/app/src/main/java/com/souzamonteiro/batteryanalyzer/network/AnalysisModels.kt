package com.souzamonteiro.batteryanalyzer.network

data class AnalysisResponse(
    val jobId: String,
    val reportUrl: String,
    val uploadedFile: String?,
    val report: AnalysisReport,
    val plots: List<AnalysisPlot>
)

data class AnalysisReport(
    val inputFile: String,
    val samples: Int,
    val currentSohPercent: Double,
    val linearRulHuman: String,
    val linearR2: Double,
    val svrRulHuman: String,
    val svrR2: Double
)

data class AnalysisPlot(
    val name: String,
    val url: String
)

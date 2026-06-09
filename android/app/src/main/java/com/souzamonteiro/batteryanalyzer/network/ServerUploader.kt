package com.souzamonteiro.batteryanalyzer.network

import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.OutputStream
import java.net.ConnectException
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.net.SocketTimeoutException
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

object ServerUploader {
    suspend fun uploadBdf(
        file: File,
        host: String,
        port: Int,
        eol: Double,
        svrDays: Int,
        telemetryDeviceId: String
    ): Result<AnalysisResponse> {
        return withContext(Dispatchers.IO) {
            val normalizedHost = host.trim()
            val parsed = parseHostInput(normalizedHost)
            val hosts = when {
                parsed.host.equals("localhost", ignoreCase = true) -> listOf("localhost", "10.0.2.2", "127.0.0.1")
                parsed.host.isBlank() -> listOf("maia.maiascript.com")
                else -> listOf(parsed.host)
            }
            val scheme = parsed.scheme
            val effectivePort = parsed.port ?: port

            var lastFailure: Throwable? = null
            for (candidateHost in hosts) {
                val result = runCatching {
                    uploadOnce(file, scheme, candidateHost, effectivePort, eol, svrDays, telemetryDeviceId)
                }
                if (result.isSuccess) return@withContext result

                val error = result.exceptionOrNull()
                lastFailure = error
                if (error !is ConnectException && error !is SocketTimeoutException) {
                    return@withContext result
                }
            }

            Result.failure(lastFailure ?: IllegalStateException("Upload failed"))
        }
    }

    private fun uploadOnce(
        file: File,
        scheme: String,
        host: String,
        port: Int,
        eol: Double,
        svrDays: Int,
        telemetryDeviceId: String
    ): AnalysisResponse {
        val boundary = "Boundary-${UUID.randomUUID()}"
        val baseUrl = "$scheme://$host:$port"
        val connection = (URL("$baseUrl/api/analyze").openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            doOutput = true
            connectTimeout = 15_000
            readTimeout = 90_000
            setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
            setRequestProperty("Accept", "application/json")
        }

        if (connection is HttpsURLConnection) {
            connection.sslSocketFactory = insecureSslSocketFactory()
            connection.hostnameVerifier = HostnameVerifier { _, _ -> true }
        }

        connection.outputStream.use { output ->
            writeField(output, boundary, "eol", eol.toString())
            writeField(output, boundary, "svrDays", svrDays.toString())
            writeField(output, boundary, "deviceMetadata", buildDeviceMetadataJson(telemetryDeviceId))
            output.write("--$boundary\r\n".toByteArray())
            output.write("Content-Disposition: form-data; name=\"batteryFile\"; filename=\"${file.name}\"\r\n".toByteArray())
            output.write("Content-Type: text/csv\r\n\r\n".toByteArray())
            file.inputStream().use { it.copyTo(output) }
            output.write("\r\n--$boundary--\r\n".toByteArray())
        }

        val code = connection.responseCode
        val body = try {
            if (code in 200..299) connection.inputStream.bufferedReader().readText()
            else connection.errorStream?.bufferedReader()?.readText().orEmpty()
        } finally {
            connection.disconnect()
        }

        if (code !in 200..299) {
            error("HTTP $code ${if (body.isNotBlank()) "- $body" else ""}")
        }

        return parseResponse(body, baseUrl)
    }

    private fun writeField(output: OutputStream, boundary: String, name: String, value: String) {
        output.write("--$boundary\r\n".toByteArray())
        output.write("Content-Disposition: form-data; name=\"$name\"\r\n\r\n".toByteArray())
        output.write(value.toByteArray())
        output.write("\r\n".toByteArray())
    }

    private fun parseResponse(body: String, baseUrl: String): AnalysisResponse {
        val json = JSONObject(body)
        val reportJson = json.getJSONObject("report")
        val currentJson = reportJson.getJSONObject("current_health")
        val linearJson = reportJson.getJSONObject("linear_model")
        val svrJson = reportJson.getJSONObject("svr_model")
        val plotsJson = json.optJSONArray("plots") ?: JSONArray()

        val plots = buildList {
            for (i in 0 until plotsJson.length()) {
                val item = plotsJson.getJSONObject(i)
                add(
                    AnalysisPlot(
                        name = item.optString("name", "plot"),
                        url = absoluteUrl(baseUrl, item.optString("url", ""))
                    )
                )
            }
        }

        return AnalysisResponse(
            jobId = json.optString("jobId", ""),
            reportUrl = absoluteUrl(baseUrl, json.optString("reportUrl", "")),
            uploadedFile = if (json.has("uploadedFile") && !json.isNull("uploadedFile")) {
                json.optString("uploadedFile", "")
            } else {
                null
            },
            report = AnalysisReport(
                inputFile = reportJson.optString("input_file", ""),
                samples = reportJson.optInt("samples", 0),
                currentSohPercent = currentJson.optDouble("current_soh_percent", 0.0),
                linearRulHuman = linearJson.optString("rul_human", "Unknown"),
                linearR2 = linearJson.optDouble("r2", 0.0),
                svrRulHuman = svrJson.optString("rul_human", "Unknown"),
                svrR2 = svrJson.optDouble("r2", 0.0)
            ),
            plots = plots
        )
    }

    private fun absoluteUrl(baseUrl: String, value: String): String {
        return when {
            value.startsWith("http://") || value.startsWith("https://") -> value
            value.startsWith("/") -> baseUrl + value
            value.isBlank() -> baseUrl
            else -> "$baseUrl/$value"
        }
    }

    private data class ParsedHost(val scheme: String, val host: String, val port: Int?)

    private fun parseHostInput(raw: String): ParsedHost {
        if (raw.isBlank()) return ParsedHost("https", "maia.maiascript.com", null)

        return if (raw.startsWith("http://", ignoreCase = true) || raw.startsWith("https://", ignoreCase = true)) {
            val uri = URI(raw)
            ParsedHost(
                scheme = uri.scheme?.lowercase() ?: "http",
                host = uri.host ?: raw,
                port = if (uri.port > 0) uri.port else null
            )
        } else {
            ParsedHost("http", raw, null)
        }
    }

    private fun buildDeviceMetadataJson(telemetryDeviceId: String): String {
        val metadata = JSONObject()
        metadata.put("source", "android")
        metadata.put("platform", "mobile")
        metadata.put("osName", "Android")
        metadata.put("osVersion", Build.VERSION.RELEASE ?: "unknown")
        metadata.put("osApiLevel", Build.VERSION.SDK_INT)
        metadata.put("manufacturer", Build.MANUFACTURER ?: "unknown")
        metadata.put("brand", Build.BRAND ?: "unknown")
        metadata.put("model", Build.MODEL ?: "unknown")
        metadata.put("device", Build.DEVICE ?: "unknown")
        metadata.put("product", Build.PRODUCT ?: "unknown")
        metadata.put("hardware", Build.HARDWARE ?: "unknown")
        metadata.put("fingerprint", Build.FINGERPRINT ?: "unknown")
        metadata.put("telemetryDeviceId", telemetryDeviceId)
        metadata.put("capturedAt", System.currentTimeMillis())
        return metadata.toString()
    }

    private fun insecureSslSocketFactory() = SSLContext.getInstance("TLS").apply {
        init(null, arrayOf<TrustManager>(object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) = Unit
            override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) = Unit
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
        }), SecureRandom())
    }.socketFactory
}

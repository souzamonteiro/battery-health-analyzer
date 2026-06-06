package com.souzamonteiro.batteryanalyzer

import android.app.Application
import coil.ImageLoader
import coil.ImageLoaderFactory
import okhttp3.OkHttpClient
import java.security.SecureRandom
import java.security.cert.X509Certificate
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

/**
 * Custom Application that provides Coil with an [ImageLoader] backed by a trust-all
 * [OkHttpClient].  This is required because the server uses a mkcert self-signed
 * certificate that is not in Android's system trust store, so Coil's default
 * OkHttpClient rejects the connection when loading plot images.
 *
 * The same trust-all approach is used in [com.souzamonteiro.batteryanalyzer.network.ServerUploader]
 * for the API calls, so this just extends that behaviour to image loading.
 */
class BatteryAnalyzerApp : Application(), ImageLoaderFactory {

    override fun newImageLoader(): ImageLoader {
        val trustAllManager = object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) = Unit
            override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) = Unit
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
        }

        val sslContext = SSLContext.getInstance("TLS").apply {
            init(null, arrayOf<TrustManager>(trustAllManager), SecureRandom())
        }

        val okHttpClient = OkHttpClient.Builder()
            .sslSocketFactory(sslContext.socketFactory, trustAllManager)
            .hostnameVerifier { _, _ -> true }
            .build()

        return ImageLoader.Builder(this)
            .okHttpClient(okHttpClient)
            .build()
    }
}

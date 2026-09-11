package com.aegis.mobile.network

import android.content.Context
import com.aegis.mobile.data.DEFAULT_SERVER_URL
import com.aegis.mobile.data.PrefKeys
import com.aegis.mobile.data.dataStore
import com.google.gson.GsonBuilder
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Response
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/**
 * Builds API clients. API key and server URL are read from DataStore on each
 * request so Settings changes apply without restarting the capture service.
 */
object RetrofitClient {

    private val latestBaseUrl = AtomicReference(DEFAULT_SERVER_URL)

    private suspend fun resolveBaseUrl(context: Context): String {
        val prefs = context.dataStore.data.first()

        prefs[PrefKeys.SERVER_URL]?.let { url ->
            if (url.isNotBlank()) {
                val normalized = if (url.endsWith("/")) url else "$url/"
                // Reject accidental website URL
                if (normalized.contains("leveragefx.co") && !normalized.contains("api")) {
                    return DEFAULT_SERVER_URL
                }
                return normalized
            }
        }

        prefs[PrefKeys.SERVER_IP]?.let { ip ->
            if (ip.isNotBlank()) {
                return "http://$ip:5000/"
            }
        }

        return DEFAULT_SERVER_URL
    }

    private suspend fun resolveApiKey(context: Context): String {
        return context.dataStore.data.first()[PrefKeys.API_KEY]?.trim().orEmpty()
    }

    fun getApiService(context: Context): ApiService {
        val appCtx = context.applicationContext
        val baseUrl = runBlocking { resolveBaseUrl(appCtx) }
        latestBaseUrl.set(baseUrl)

        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }

        // Fresh key + optional host rewrite every request (settings can change mid-session)
        val authInterceptor = Interceptor { chain ->
            val prefsKey = runBlocking { resolveApiKey(appCtx) }
            val prefsUrl = runBlocking { resolveBaseUrl(appCtx) }
            latestBaseUrl.set(prefsUrl)

            var req = chain.request()
            val target = prefsUrl.toHttpUrlOrNull()
            if (target != null) {
                val newUrl = req.url.newBuilder()
                    .scheme(target.scheme)
                    .host(target.host)
                    .port(target.port)
                    .build()
                req = req.newBuilder().url(newUrl).build()
            }

            val builder = req.newBuilder()
            if (prefsKey.isNotBlank()) {
                builder.header("X-API-Key", prefsKey)
            }
            chain.proceed(builder.build())
        }

        val client = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(logging)
            .connectTimeout(45, TimeUnit.SECONDS)
            .readTimeout(90, TimeUnit.SECONDS)
            .writeTimeout(90, TimeUnit.SECONDS)
            .callTimeout(150, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .pingInterval(15, TimeUnit.SECONDS)
            .build()

        val gson = GsonBuilder()
            .setLenient()
            .create()

        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
            .create(ApiService::class.java)
    }
}

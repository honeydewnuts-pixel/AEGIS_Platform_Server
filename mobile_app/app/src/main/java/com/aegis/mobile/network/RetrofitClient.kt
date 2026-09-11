package com.aegis.mobile.network

import android.content.Context
import com.aegis.mobile.data.DEFAULT_SERVER_URL
import com.aegis.mobile.data.PrefKeys
import com.aegis.mobile.data.dataStore
import com.google.gson.GsonBuilder
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/**
 * Proven upload client pattern (matches older working sideload builds):
 * - Preferences loaded ONCE when building the client (not inside OkHttp threads)
 * - No runBlocking on the interceptor path (that caused NETWORK failures / hangs)
 * - No host-rewrite
 */
object RetrofitClient {

    private val cachedApiKey = AtomicReference("")
    private val cachedBaseUrl = AtomicReference(
        if (DEFAULT_SERVER_URL.endsWith("/")) DEFAULT_SERVER_URL else "$DEFAULT_SERVER_URL/"
    )

    fun currentBaseUrl(): String = cachedBaseUrl.get()
    fun currentApiKeyMasked(): String {
        val k = cachedApiKey.get()
        if (k.isBlank()) return "(empty)"
        if (k.length <= 8) return "***"
        return k.take(4) + "…" + k.takeLast(4)
    }

    private fun normalizeBaseUrl(raw: String): String {
        var u = raw.trim()
        if (u.isEmpty()) {
            u = DEFAULT_SERVER_URL
        }
        if (!u.startsWith("http://") && !u.startsWith("https://")) {
            u = "https://$u"
        }
        // Strip path accidents like .../api or website paths
        u = u.trimEnd('/')
        // If user pasted website domain without api host, force API default
        val host = u.substringAfter("://").substringBefore("/")
        if (host.equals("leveragefx.co", true) ||
            host.equals("www.leveragefx.co", true) ||
            host.equals("leveragefx-website.vercel.app", true)
        ) {
            u = DEFAULT_SERVER_URL.trimEnd('/')
        }
        return "$u/"
    }

    /** Call from coroutine or service thread before creating client. */
    fun loadPreferences(context: Context) {
        val appCtx = context.applicationContext
        runBlocking {
            val prefs = appCtx.dataStore.data.first()
            val url = prefs[PrefKeys.SERVER_URL]?.trim().orEmpty()
            val ip = prefs[PrefKeys.SERVER_IP]?.trim().orEmpty()
            val key = prefs[PrefKeys.API_KEY]?.trim().orEmpty()
            cachedApiKey.set(key)
            val base = when {
                url.isNotBlank() -> normalizeBaseUrl(url)
                ip.isNotBlank() -> "http://${ip.trim()}:5000/"
                else -> normalizeBaseUrl(DEFAULT_SERVER_URL)
            }
            cachedBaseUrl.set(base)
        }
    }

    fun getApiService(context: Context): ApiService {
        loadPreferences(context)
        val baseUrl = cachedBaseUrl.get()

        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }

        // Header only — never touch DataStore / runBlocking here
        val authInterceptor = Interceptor { chain ->
            val key = cachedApiKey.get()
            val req = if (key.isNotBlank()) {
                chain.request().newBuilder().header("X-API-Key", key).build()
            } else {
                chain.request()
            }
            chain.proceed(req)
        }

        val client = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(logging)
            .connectTimeout(45, TimeUnit.SECONDS)
            .readTimeout(90, TimeUnit.SECONDS)
            .writeTimeout(90, TimeUnit.SECONDS)
            .callTimeout(120, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()

        val gson = GsonBuilder().setLenient().create()

        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
            .create(ApiService::class.java)
    }

    /**
     * Lightweight reachability probe (no Retrofit). Returns null on success,
     * or a short error string on failure.
     */
    fun pingBackend(context: Context): String? {
        return try {
            loadPreferences(context)
            val base = cachedBaseUrl.get().trimEnd('/')
            val client = OkHttpClient.Builder()
                .connectTimeout(20, TimeUnit.SECONDS)
                .readTimeout(20, TimeUnit.SECONDS)
                .retryOnConnectionFailure(true)
                .build()
            // Prefer /health then /
            for (path in listOf("/health", "/")) {
                val req = Request.Builder().url("$base$path").get().build()
                client.newCall(req).execute().use { resp ->
                    if (resp.isSuccessful) return null
                }
            }
            "HTTP non-2xx from $base"
        } catch (e: Exception) {
            "${e.javaClass.simpleName}: ${e.message}"
        }
    }
}

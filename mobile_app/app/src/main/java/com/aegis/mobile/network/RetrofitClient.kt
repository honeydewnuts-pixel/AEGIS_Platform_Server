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
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

/**
 * Network client matching the working sideload builds.
 * - Simple base URL from Settings (or DEFAULT_SERVER_URL)
 * - API key header read live from DataStore on each request
 * - No host-rewrite tricks (those broke uploads on some devices)
 */
object RetrofitClient {

    private suspend fun resolveBaseUrl(context: Context): String {
        val prefs = context.dataStore.data.first()
        prefs[PrefKeys.SERVER_URL]?.trim()?.takeIf { it.isNotBlank() }?.let { url ->
            var u = url
            if (!u.startsWith("http://") && !u.startsWith("https://")) {
                u = "https://$u"
            }
            return if (u.endsWith("/")) u else "$u/"
        }
        prefs[PrefKeys.SERVER_IP]?.trim()?.takeIf { it.isNotBlank() }?.let { ip ->
            return "http://$ip:5000/"
        }
        val d = DEFAULT_SERVER_URL
        return if (d.endsWith("/")) d else "$d/"
    }

    fun getApiService(context: Context): ApiService {
        val appCtx = context.applicationContext
        val baseUrl = runBlocking { resolveBaseUrl(appCtx) }

        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }

        val authInterceptor = Interceptor { chain ->
            val key = runBlocking {
                appCtx.dataStore.data.first()[PrefKeys.API_KEY]?.trim().orEmpty()
            }
            val b = chain.request().newBuilder()
            if (key.isNotBlank()) {
                b.header("X-API-Key", key)
            }
            chain.proceed(b.build())
        }

        val client = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(logging)
            .connectTimeout(60, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS)
            .writeTimeout(120, TimeUnit.SECONDS)
            .callTimeout(180, TimeUnit.SECONDS)
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
}

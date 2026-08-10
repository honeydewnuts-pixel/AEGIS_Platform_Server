package com.aegis.mobile.network

import android.content.Context
import com.aegis.mobile.data.DEFAULT_SERVER_IP
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

object RetrofitClient {

    fun getApiService(context: Context): ApiService {

        val savedServer = runBlocking {
            context.dataStore.data.first()[PrefKeys.SERVER_IP]
                ?: DEFAULT_SERVER_IP
        }

        val baseUrl = when {

            savedServer.isBlank() -> {
                DEFAULT_SERVER_IP.ensureTrailingSlash()
            }

            savedServer.startsWith("http://", true) ||
            savedServer.startsWith("https://", true) -> {
                savedServer.ensureTrailingSlash()
            }

            else -> {
                "https://$savedServer".ensureTrailingSlash()
            }
        }

        val apiKey = runBlocking {
            context.dataStore.data.first()[PrefKeys.API_KEY] ?: ""
        }

        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        val authInterceptor = Interceptor { chain ->

            val builder = chain.request()
                .newBuilder()

            if (apiKey.isNotBlank()) {
                builder.addHeader(
                    "X-API-Key",
                    apiKey
                )
            }

            chain.proceed(builder.build())
        }

        val client = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(logging)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()

        val gson = GsonBuilder()
            .setLenient()
            .create()

        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(
                GsonConverterFactory.create(gson)
            )
            .build()
            .create(ApiService::class.java)
    }

    private fun String.ensureTrailingSlash(): String {
        return if (endsWith("/")) this else "$this/"
    }
}

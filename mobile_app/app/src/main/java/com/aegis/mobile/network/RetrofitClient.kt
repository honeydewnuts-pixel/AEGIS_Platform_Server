package com.aegis.mobile.network

import android.content.Context
import com.aegis.mobile.data.DEFAULT_SERVER_IP
import com.aegis.mobile.data.PrefKeys
import com.aegis.mobile.data.dataStore
import com.google.gson.GsonBuilder
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {

    private const val PORT = "5000"

    fun getApiService(context: Context): ApiService {
        val serverIp = runBlocking {
            context.dataStore.data.first()[PrefKeys.SERVER_IP] ?: DEFAULT_SERVER_IP
        }
        val baseUrl = "http://$serverIp:$PORT/"

        val apiKey = runBlocking {
            context.dataStore.data.first()[PrefKeys.API_KEY] ?: ""
        }

        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        val authInterceptor = okhttp3.Interceptor { chain ->
            val newRequest = chain.request().newBuilder()
                .addHeader("X-API-Key", apiKey)
                .build()
            chain.proceed(newRequest)
        }

        val client = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(logging)
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
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

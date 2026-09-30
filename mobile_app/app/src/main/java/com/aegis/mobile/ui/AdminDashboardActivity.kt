package com.aegis.mobile.ui

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.aegis.mobile.R
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

class AdminDashboardActivity : AppCompatActivity() {

    private val http = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private lateinit var meta: TextView
    private lateinit var health: TextView
    private lateinit var monitor: TextView
    private lateinit var withdrawal: TextView
    private lateinit var summary: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_admin_dashboard)
        title = "Ops Dashboard"

        meta = findViewById(R.id.adminDashMeta)
        health = findViewById(R.id.adminHealth)
        monitor = findViewById(R.id.adminMonitor)
        withdrawal = findViewById(R.id.adminWithdrawal)
        summary = findViewById(R.id.adminSummary)

        findViewById<Button>(R.id.adminBtnRefresh).setOnClickListener { refresh() }
        findViewById<Button>(R.id.adminBtnLogout).setOnClickListener {
            getSharedPreferences("aegis_admin", MODE_PRIVATE).edit().remove("key").apply()
            finish()
        }
        refresh()
    }

    private fun refresh() {
        val prefs = getSharedPreferences("aegis_admin", MODE_PRIVATE)
        val base = prefs.getString("url", "")?.trimEnd('/') ?: ""
        val key = prefs.getString("key", "") ?: ""
        meta.text = "Server: $base"
        if (base.isBlank() || key.isBlank()) {
            health.text = "Not logged in."
            return
        }
        lifecycleScope.launch {
            health.text = "Loading…"
            monitor.text = "Loading…"
            withdrawal.text = "Loading…"
            summary.text = "Loading…"
            val h = getJson(base, "/", key)
            val m = getJson(base, "/api/demo-monitor", key)
            val w = getJson(base, "/api/withdrawal/status", key)
            val s = getJson(base, "/api/admin/summary", key)
            health.text = h
            monitor.text = m
            withdrawal.text = w
            summary.text = s
        }
    }

    private suspend fun getJson(base: String, path: String, adminKey: String): String =
        withContext(Dispatchers.IO) {
            try {
                val req = Request.Builder()
                    .url("$base$path")
                    .header("X-Admin-Key", adminKey)
                    .header("Authorization", "Bearer $adminKey")
                    .header("X-API-Key", adminKey)
                    .get()
                    .build()
                http.newCall(req).execute().use { resp ->
                    val body = resp.body?.string()?.take(2500) ?: ""
                    "HTTP ${resp.code}\n$body"
                }
            } catch (e: Exception) {
                "Error: ${e.message}"
            }
        }
}

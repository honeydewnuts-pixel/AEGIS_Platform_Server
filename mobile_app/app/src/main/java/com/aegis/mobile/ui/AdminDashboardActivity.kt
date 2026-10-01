package com.aegis.mobile.ui

import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.aegis.mobile.R
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
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
    private lateinit var kpiApi: TextView
    private lateinit var kpiSubs: TextView
    private lateinit var kpiDevices: TextView
    private lateinit var etAccount: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_admin_dashboard)
        title = "AEGIS Ops"

        meta = findViewById(R.id.adminDashMeta)
        health = findViewById(R.id.adminHealth)
        monitor = findViewById(R.id.adminMonitor)
        withdrawal = findViewById(R.id.adminWithdrawal)
        summary = findViewById(R.id.adminSummary)
        kpiApi = findViewById(R.id.kpiApi)
        kpiSubs = findViewById(R.id.kpiSubs)
        kpiDevices = findViewById(R.id.kpiDevices)
        etAccount = findViewById(R.id.adminEtAccount)

        val prefs = getSharedPreferences("aegis_admin", MODE_PRIVATE)
        etAccount.setText(prefs.getString("inspect_account", "") ?: "")

        findViewById<Button>(R.id.adminBtnRefresh).setOnClickListener { refresh() }
        findViewById<Button>(R.id.adminBtnLogout).setOnClickListener {
            prefs.edit().remove("key").apply()
            finish()
        }
        refresh()
    }

    private fun refresh() {
        val prefs = getSharedPreferences("aegis_admin", MODE_PRIVATE)
        val base = prefs.getString("url", "")?.trimEnd('/') ?: ""
        val key = prefs.getString("key", "") ?: ""
        val account = etAccount.text.toString().trim()
        prefs.edit().putString("inspect_account", account).apply()
        meta.text = "Server · $base"
        if (base.isBlank() || key.isBlank()) {
            health.text = "Not logged in."
            return
        }
        lifecycleScope.launch {
            kpiApi.text = "…"
            health.text = "Refreshing…"
            monitor.text = "Refreshing…"
            withdrawal.text = "Refreshing…"
            summary.text = "Refreshing…"

            val h = getPair(base, "/", key)
            val monPath = if (account.isNotBlank()) "/api/demo-monitor/$account" else "/api/demo-monitor"
            val m = getPair(base, monPath, key)
            val w = getPair(base, "/api/withdrawal/status", key)
            val s = getPair(base, "/api/admin/summary", key)

            kpiApi.text = if (h.first in 200..299) "ONLINE" else "HTTP ${h.first}"
            kpiApi.setTextColor(if (h.first in 200..299) 0xFF00FF88.toInt() else 0xFFF87171.toInt())

            health.text = formatHealth(h.first, h.second)
            monitor.text = formatMonitor(m.first, m.second, account)
            withdrawal.text = formatWithdrawal(w.first, w.second)
            summary.text = formatSummary(s.first, s.second)

            // KPIs from summary
            try {
                if (s.first in 200..299) {
                    val jo = JSONObject(s.second)
                    val subs = jo.optJSONObject("subscriptions")
                    val devices = jo.optJSONObject("devices")
                    val paid = subs?.opt("paid_active")
                    val totalSubs = subs?.opt("total")
                    kpiSubs.text = if (paid != null) "P$paid/${totalSubs ?: "—"}" else totalSubs?.toString() ?: "—"
                    val online = devices?.opt("online")
                    val total = devices?.opt("total")
                    kpiDevices.text = if (online != null && total != null) "$online/$total" else total?.toString() ?: "—"
                }
            } catch (_: Exception) {
            }
        }
    }

    private fun formatHealth(code: Int, body: String): String {
        if (code !in 200..299) return "● DOWN  HTTP $code\n${body.take(400)}"
        return try {
            val jo = JSONObject(body)
            buildString {
                appendLine("● ${jo.optString("status", "OK").uppercase()}")
                appendLine("Application  ${jo.optString("application", "AEGIS")}")
                appendLine("Company      ${jo.optString("company", "—")}")
                appendLine("Version      ${jo.optString("version", "—")}")
                appendLine("Description  ${jo.optString("description", "—")}")
            }.trim()
        } catch (_: Exception) {
            "HTTP $code\n${body.take(500)}"
        }
    }

    private fun formatMonitor(code: Int, body: String, account: String): String {
        if (code == 404) {
            return "● NO DATA\nUse account id above (e.g. ACC-…).\nPath: /api/demo-monitor/{account_id}\nHTTP 404 without account is expected on older deploys."
        }
        if (code !in 200..299) return "● ERROR HTTP $code\n${body.take(500)}"
        return try {
            val jo = JSONObject(body)
            if (jo.has("monitor") && jo.optString("monitor") == "ready") {
                return "● MONITOR READY\nEnter an account id and refresh for the full 10-stage pipeline.\n${jo.optString("hint")}"
            }
            buildString {
                appendLine("Account  ${jo.optString("account_id", account)}")
                appendLine("Overall  ${jo.optString("overall", jo.optString("status", "—"))}")
                val stages = jo.optJSONArray("stages")
                if (stages != null) {
                    appendLine("— Stages —")
                    for (i in 0 until stages.length()) {
                        val st = stages.optJSONObject(i) ?: continue
                        val name = st.optString("name", st.optString("stage", "stage"))
                        val state = st.optString("state", st.optString("status", "?"))
                        val detail = st.optString("detail", st.optString("message", ""))
                        appendLine("• $name  [$state]")
                        if (detail.isNotBlank()) appendLine("  $detail")
                    }
                } else {
                    append(body.take(800))
                }
            }.trim()
        } catch (_: Exception) {
            "HTTP $code\n${body.take(800)}"
        }
    }

    private fun formatWithdrawal(code: Int, body: String): String {
        if (code !in 200..299) return "HTTP $code\n${body.take(300)}"
        return try {
            val jo = JSONObject(body)
            val on = jo.optBoolean("module_enabled", false)
            buildString {
                appendLine(if (on) "● MODULE ACTIVE" else "● MODULE OFF")
                appendLine(jo.optString("note", ""))
            }.trim()
        } catch (_: Exception) {
            body.take(400)
        }
    }

    private fun formatSummary(code: Int, body: String): String {
        if (code !in 200..299) return "HTTP $code\n${body.take(400)}"
        return try {
            val jo = JSONObject(body)
            val devices = jo.optJSONObject("devices")
            val subs = jo.optJSONObject("subscriptions")
            val by = subs?.optJSONObject("by_status")
            val byPlan = subs?.optJSONObject("by_plan")
            buildString {
                appendLine("Devices   online ${devices?.opt("online") ?: 0} / total ${devices?.opt("total") ?: 0}")
                appendLine("Subs      total ${subs?.opt("total") ?: 0}  ·  paid active ${subs?.opt("paid_active") ?: 0}  ·  demo ${subs?.opt("demo_count") ?: 0}")
                if (byPlan != null) {
                    appendLine("— By plan —")
                    val keys = byPlan.keys()
                    while (keys.hasNext()) {
                        val k = keys.next()
                        appendLine("  · $k  ${byPlan.opt(k)}")
                    }
                }
                if (by != null) {
                    appendLine("— By status —")
                    val keys = by.keys()
                    while (keys.hasNext()) {
                        val k = keys.next()
                        appendLine("  · $k  ${by.opt(k)}")
                    }
                }
                val paid = subs?.optJSONArray("paid_accounts")
                if (paid != null && paid.length() > 0) {
                    appendLine("— Paid accounts —")
                    for (i in 0 until minOf(paid.length(), 25)) {
                        val a = paid.optJSONObject(i) ?: continue
                        appendLine("  ${a.optString("account_id")}  ${a.optString("plan")}  ${a.optString("status")}")
                    }
                }
                appendLine("Workers   ${jo.opt("active_workers_this_instance")}/${jo.opt("max_concurrent_workers")}")
            }.trim()
        } catch (_: Exception) {
            body.take(800)
        }
    }

    private suspend fun getPair(base: String, path: String, adminKey: String): Pair<Int, String> =
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
                    Pair(resp.code, resp.body?.string()?.take(4000) ?: "")
                }
            } catch (e: Exception) {
                Pair(0, e.message ?: "error")
            }
        }
}

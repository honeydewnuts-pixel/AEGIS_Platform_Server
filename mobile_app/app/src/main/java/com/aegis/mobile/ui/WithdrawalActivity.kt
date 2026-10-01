package com.aegis.mobile.ui

import android.graphics.drawable.ColorDrawable
import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.aegis.mobile.R
import com.aegis.mobile.data.PrefKeys
import com.aegis.mobile.data.dataStore
import com.aegis.mobile.network.RetrofitClient
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.util.UUID

class WithdrawalActivity : AppCompatActivity() {

    private lateinit var moduleStatus: TextView
    private lateinit var dashboardText: TextView
    private lateinit var historyText: TextView
    private lateinit var etStartEquity: EditText
    private lateinit var etRisk: EditText
    private lateinit var spinnerMode: Spinner
    private lateinit var etAmount: EditText
    private lateinit var btnConfigure: Button
    private lateinit var btnRefresh: Button

    private val modeOptions = listOf(
        "portfolio" to "Portfolio (all pairs)",
        "per_pair" to "Per-pair (advanced)",
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_withdrawal)
        title = "Withdrawals"

        moduleStatus = findViewById(R.id.wdModuleStatus)
        dashboardText = findViewById(R.id.wdDashboardText)
        historyText = findViewById(R.id.wdHistoryText)
        etStartEquity = findViewById(R.id.wdEtStartEquity)
        etRisk = findViewById(R.id.wdEtRisk)
        spinnerMode = findViewById(R.id.wdSpinnerMode)
        etAmount = findViewById(R.id.wdEtAmount)
        btnConfigure = findViewById(R.id.wdBtnConfigure)
        btnRefresh = findViewById(R.id.wdBtnRefresh)

        val modeAdapter = ArrayAdapter(this, R.layout.spinner_item_dark, modeOptions.map { it.second })
        modeAdapter.setDropDownViewResource(R.layout.spinner_dropdown_item_dark)
        spinnerMode.adapter = modeAdapter
        spinnerMode.setPopupBackgroundDrawable(ColorDrawable(0xFF0F1C2E.toInt()))

        btnRefresh.setOnClickListener {
            btnRefresh.isEnabled = false
            btnRefresh.text = "Refreshing…"
            refreshAll {
                btnRefresh.isEnabled = true
                btnRefresh.text = "Refresh dashboard"
            }
        }
        btnConfigure.setOnClickListener { configure() }
        findViewById<Button>(R.id.wdBtnRequest).setOnClickListener { requestWithdrawal() }

        refreshAll(null)
    }

    private fun num(b: Map<String, Any?>, vararg keys: String): String {
        for (k in keys) {
            val v = b[k] ?: continue
            if (v.toString().equals("null", true)) continue
            return v.toString()
        }
        return "0"
    }

    private fun refreshAll(onDone: (() -> Unit)?) {
        lifecycleScope.launch {
            try {
                val api = RetrofitClient.getApiService(this@WithdrawalActivity)
                val st = api.withdrawalModuleStatus()
                val enabled = st.body()?.get("module_enabled") == true
                moduleStatus.text = when {
                    !st.isSuccessful -> "Module status: HTTP ${st.code()}"
                    enabled -> "Module: ENABLED on server"
                    else -> "Module: DISABLED (WITHDRAWAL_MODULE_ENABLED=false)"
                }

                val prefs = applicationContext.dataStore.data.first()
                val accountId = prefs[PrefKeys.ACCOUNT_ID]?.trim().orEmpty()
                if (accountId.isBlank()) {
                    dashboardText.text = "No account ID — log in first."
                    historyText.text = "—"
                    btnConfigure.text = "Configure withdrawal account"
                    return@launch
                }

                val dash = api.withdrawalDashboard(accountId)
                if (dash.isSuccessful) {
                    val b = (dash.body() ?: emptyMap()).mapKeys { it.key.toString() }
                    if (b["configured"] == true) {
                        dashboardText.text = buildString {
                            appendLine("Configured: YES  (you can update equity below)")
                            appendLine("Start equity: ${num(b, "start_equity")}")
                            appendLine("Equity (ledger): ${num(b, "equity", "current_equity")}")
                            appendLine("CAP: ${num(b, "cap")}")
                            appendLine("Lean ceiling: ${num(b, "lean_cap_ceiling")}  Locked: ${b["lean_locked"]}")
                            appendLine("Armed: ${b["armed"]}  Paused: ${b["paused"]}")
                            appendLine("Eligible balance: ${num(b, "eligible_balance")}")
                            appendLine("Total withdrawn: ${num(b, "total_withdrawn", "cumulative_withdrawals")}")
                            appendLine("Total value: ${num(b, "total_value")}")
                            appendLine("Mode: ${b["mode"]}")
                        }.trim()
                        btnConfigure.text = "Update equity / settings"
                        // Prefill fields from server
                        val se = num(b, "start_equity")
                        if (etStartEquity.text.isNullOrBlank()) etStartEquity.setText(se)
                        val risk = num(b, "risk_per_trade_pct")
                        if (risk != "0" && etRisk.text.isNullOrBlank()) etRisk.setText(risk)
                    } else {
                        dashboardText.text =
                            "Not configured yet.\nType your account equity and tap Configure."
                        btnConfigure.text = "Configure withdrawal account"
                    }
                } else {
                    dashboardText.text =
                        "Dashboard HTTP ${dash.code()}: ${dash.errorBody()?.string()?.take(180)}"
                    Toast.makeText(
                        this@WithdrawalActivity,
                        "Refresh failed: HTTP ${dash.code()}",
                        Toast.LENGTH_SHORT,
                    ).show()
                }

                val hist = api.withdrawalHistory(accountId, 30)
                if (hist.isSuccessful) {
                    val entries = hist.body()?.get("entries")
                    historyText.text = when (entries) {
                        is List<*> ->
                            if (entries.isEmpty()) "No history yet."
                            else entries.joinToString("\n") { it.toString().take(120) }
                        else -> hist.body().toString().take(400)
                    }
                } else {
                    historyText.text = "History HTTP ${hist.code()}"
                }
            } catch (e: Exception) {
                dashboardText.text = "Error: ${e.message}"
                Toast.makeText(this@WithdrawalActivity, "Refresh error: ${e.message}", Toast.LENGTH_LONG).show()
            } finally {
                onDone?.invoke()
            }
        }
    }

    private fun configure() {
        lifecycleScope.launch {
            try {
                val prefs = applicationContext.dataStore.data.first()
                val accountId = prefs[PrefKeys.ACCOUNT_ID]?.trim().orEmpty()
                if (accountId.isBlank()) {
                    Toast.makeText(this@WithdrawalActivity, "Log in first", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                val start = etStartEquity.text.toString().trim().toDoubleOrNull()
                val risk = etRisk.text.toString().trim().toDoubleOrNull() ?: 1.0
                if (start == null || start <= 0) {
                    Toast.makeText(
                        this@WithdrawalActivity,
                        "Enter your equity (any positive USD amount)",
                        Toast.LENGTH_LONG,
                    ).show()
                    return@launch
                }
                if (risk <= 0 || risk > 50) {
                    Toast.makeText(this@WithdrawalActivity, "Risk % must be between 0 and 50", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                val mode = modeOptions.getOrElse(spinnerMode.selectedItemPosition) { modeOptions[0] }.first
                val api = RetrofitClient.getApiService(this@WithdrawalActivity)
                val body = mutableMapOf<String, Any>(
                    "account_id" to accountId,
                    "start_equity" to start,
                    "mode" to mode,
                    "risk_per_trade_pct" to risk,
                )
                btnConfigure.isEnabled = false
                val resp = api.withdrawalConfigure(body)
                btnConfigure.isEnabled = true
                if (resp.isSuccessful) {
                    Toast.makeText(this@WithdrawalActivity, "Saved — equity updated", Toast.LENGTH_SHORT).show()
                    refreshAll(null)
                } else {
                    val err = resp.errorBody()?.string()?.take(220) ?: "HTTP ${resp.code()}"
                    Toast.makeText(this@WithdrawalActivity, err, Toast.LENGTH_LONG).show()
                }
            } catch (e: Exception) {
                btnConfigure.isEnabled = true
                Toast.makeText(this@WithdrawalActivity, e.message, Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun requestWithdrawal() {
        lifecycleScope.launch {
            try {
                val prefs = applicationContext.dataStore.data.first()
                val accountId = prefs[PrefKeys.ACCOUNT_ID]?.trim().orEmpty()
                val amount = etAmount.text.toString().toDoubleOrNull()
                if (accountId.isBlank() || amount == null || amount <= 0) {
                    Toast.makeText(this@WithdrawalActivity, "Enter a valid amount", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                val api = RetrofitClient.getApiService(this@WithdrawalActivity)
                val body = mapOf(
                    "account_id" to accountId,
                    "amount" to amount,
                    "idempotency_key" to UUID.randomUUID().toString(),
                )
                val resp = api.withdrawalRequest(body)
                if (resp.isSuccessful) {
                    Toast.makeText(
                        this@WithdrawalActivity,
                        "Request recorded (ledger only until payout rail is connected)",
                        Toast.LENGTH_LONG,
                    ).show()
                    refreshAll(null)
                } else {
                    val err = resp.errorBody()?.string()?.take(200) ?: "HTTP ${resp.code()}"
                    Toast.makeText(this@WithdrawalActivity, err, Toast.LENGTH_LONG).show()
                }
            } catch (e: Exception) {
                Toast.makeText(this@WithdrawalActivity, e.message, Toast.LENGTH_LONG).show()
            }
        }
    }
}

package com.aegis.mobile.ui

import android.graphics.drawable.ColorDrawable
import android.os.Bundle
import android.widget.ArrayAdapter
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

        val modeAdapter = ArrayAdapter(this, R.layout.spinner_item_dark, modeOptions.map { it.second })
        modeAdapter.setDropDownViewResource(R.layout.spinner_dropdown_item_dark)
        spinnerMode.adapter = modeAdapter
        spinnerMode.setPopupBackgroundDrawable(ColorDrawable(0xFF0F1C2E.toInt()))

        findViewById<android.widget.Button>(R.id.wdBtnRefresh).setOnClickListener { refreshAll() }
        findViewById<android.widget.Button>(R.id.wdBtnConfigure).setOnClickListener { configure() }
        findViewById<android.widget.Button>(R.id.wdBtnRequest).setOnClickListener { requestWithdrawal() }

        refreshAll()
    }

    private fun refreshAll() {
        lifecycleScope.launch {
            try {
                val api = RetrofitClient.getApiService(this@WithdrawalActivity)
                val st = api.withdrawalModuleStatus()
                val enabled = st.body()?.get("module_enabled") == true
                moduleStatus.text = if (st.isSuccessful) {
                    if (enabled) "Module: ENABLED on server"
                    else "Module: DISABLED on server (set WITHDRAWAL_MODULE_ENABLED=true)"
                } else {
                    "Module status: HTTP ${st.code()}"
                }

                val prefs = applicationContext.dataStore.data.first()
                val accountId = prefs[PrefKeys.ACCOUNT_ID]?.trim().orEmpty()
                if (accountId.isBlank()) {
                    dashboardText.text = "No account ID — log in first."
                    historyText.text = "—"
                    return@launch
                }

                val dash = api.withdrawalDashboard(accountId)
                if (dash.isSuccessful) {
                    val b = dash.body() ?: emptyMap()
                    if (b["configured"] == true) {
                        dashboardText.text = buildString {
                            appendLine("Configured: YES")
                            appendLine("Start equity: ${b["start_equity"]}")
                            appendLine("Equity (ledger): ${b["equity"]}")
                            appendLine("CAP: ${b["cap"]}")
                            appendLine("Armed: ${b["armed"]}  Paused: ${b["paused"]}")
                            appendLine("Eligible balance: ${b["eligible_balance"]}")
                            appendLine("Total withdrawn: ${b["total_withdrawn"]}")
                            appendLine("Total value: ${b["total_value"]}")
                            appendLine("Mode: ${b["mode"]}")
                        }.trim()
                    } else {
                        dashboardText.text =
                            "Not configured yet.\nType your account equity (any amount) and tap Configure."
                    }
                } else {
                    dashboardText.text = "Dashboard HTTP ${dash.code()}: ${dash.errorBody()?.string()?.take(160)}"
                }

                val hist = api.withdrawalHistory(accountId, 30)
                if (hist.isSuccessful) {
                    val entries = hist.body()?.get("entries")
                    historyText.text = when (entries) {
                        is List<*> -> if (entries.isEmpty()) "No history yet." else entries.joinToString("\n") { it.toString().take(120) }
                        else -> hist.body().toString().take(400)
                    }
                } else {
                    historyText.text = "History HTTP ${hist.code()}"
                }
            } catch (e: Exception) {
                dashboardText.text = "Error: ${e.message}"
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
                        "Enter your starting equity (any positive USD amount)",
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
                val resp = api.withdrawalConfigure(body)
                if (resp.isSuccessful) {
                    Toast.makeText(this@WithdrawalActivity, "Configured", Toast.LENGTH_SHORT).show()
                    refreshAll()
                } else {
                    val err = resp.errorBody()?.string()?.take(220) ?: "HTTP ${resp.code()}"
                    Toast.makeText(this@WithdrawalActivity, err, Toast.LENGTH_LONG).show()
                }
            } catch (e: Exception) {
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
                    refreshAll()
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

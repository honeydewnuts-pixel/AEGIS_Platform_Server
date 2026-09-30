package com.aegis.mobile.ui

import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.EditText
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.AppCompatButton
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
    private lateinit var spinnerStart: Spinner
    private lateinit var spinnerRisk: Spinner
    private lateinit var spinnerMode: Spinner
    private lateinit var etAmount: EditText

    private val startOptions = listOf(50.0, 100.0, 250.0, 500.0, 1000.0, 10000.0)
    private val riskOptions = listOf(0.5, 1.0)
    private val modeOptions = listOf("portfolio" to "Portfolio (all pairs)", "per_pair" to "Per-pair (advanced)")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_withdrawal)
        title = "Withdrawals"

        moduleStatus = findViewById(R.id.wdModuleStatus)
        dashboardText = findViewById(R.id.wdDashboardText)
        historyText = findViewById(R.id.wdHistoryText)
        spinnerStart = findViewById(R.id.wdSpinnerStartEquity)
        spinnerRisk = findViewById(R.id.wdSpinnerRisk)
        spinnerMode = findViewById(R.id.wdSpinnerMode)
        etAmount = findViewById(R.id.wdEtAmount)

        spinnerStart.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            startOptions.map { "$${"%.0f".format(it)}" }
        )
        spinnerRisk.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            riskOptions.map { "${it}% risk / trade (label)" }
        )
        spinnerMode.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            modeOptions.map { it.second }
        )
        // default $1000 / 1%
        spinnerStart.setSelection(startOptions.indexOf(1000.0).coerceAtLeast(0))
        spinnerRisk.setSelection(1)

        findViewById<AppCompatButton>(R.id.wdBtnRefresh).setOnClickListener { refreshAll() }
        findViewById<AppCompatButton>(R.id.wdBtnConfigure).setOnClickListener { configure() }
        findViewById<AppCompatButton>(R.id.wdBtnRequest).setOnClickListener { requestWithdrawal() }

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
                    else "Module: DISABLED on server (WITHDRAWAL_MODULE_ENABLED=false) — dashboard may be read-only"
                } else {
                    "Module status: HTTP ${st.code()}"
                }

                val prefs = applicationContext.dataStore.data.first()
                val accountId = prefs[PrefKeys.ACCOUNT_ID]?.trim().orEmpty()
                if (accountId.isBlank()) {
                    dashboardText.text = "No account_id — log in / set Account ID in Settings."
                    return@launch
                }

                val dash = api.withdrawalDashboard(accountId)
                if (!dash.isSuccessful || dash.body() == null) {
                    dashboardText.text = "Dashboard HTTP ${dash.code()}: ${dash.errorBody()?.string()?.take(200) ?: ""}"
                } else {
                    dashboardText.text = formatDashboard(dash.body()!!)
                }

                val hist = api.withdrawalHistory(accountId, 30)
                if (!hist.isSuccessful || hist.body() == null) {
                    historyText.text = "History HTTP ${hist.code()}"
                } else {
                    val entries = hist.body()!!["entries"] as? List<*>
                    if (entries.isNullOrEmpty()) {
                        historyText.text = "No ledger entries yet."
                    } else {
                        historyText.text = entries.take(25).joinToString("\n") { row ->
                            val m = row as? Map<*, *> ?: return@joinToString ""
                            val et = m["event_type"]?.toString() ?: "?"
                            val tid = m["trade_id"]?.toString()?.take(18) ?: ""
                            val pnl = m["realized_pnl"]
                            val elig = m["to_eligible"]
                            val cap = m["to_cap"]
                            "$et $tid pnl=$pnl elig=$elig cap+=$cap"
                        }
                    }
                }
            } catch (e: Exception) {
                dashboardText.text = "Error: ${e.message}"
            }
        }
    }

    private fun formatDashboard(b: Map<String, Any?>): String {
        if (b["configured"] == false) {
            return "Not configured yet.\nChoose starting equity and tap Configure.\n(Requires module enabled on server.)"
        }
        fun n(key: String) = b[key]?.toString() ?: "—"
        return buildString {
            appendLine("Start equity: ${n("start_equity")}")
            appendLine("Current equity: ${n("current_equity")}")
            appendLine("CAP: ${n("cap")}")
            appendLine("Armed: ${n("armed")} · Paused: ${n("paused")}")
            appendLine("Realized trading PnL: ${n("realized_trading_pnl")}")
            appendLine("Eligible balance: ${n("eligible_balance")}")
            appendLine("Retained (in CAP): ${n("retained_profit")}")
            appendLine("Cumulative withdrawals: ${n("cumulative_withdrawals")}")
            appendLine("Total value (equity + withdrawn): ${n("total_value")}")
            appendLine("DD from CAP %: ${n("drawdown_from_cap_pct")}")
            appendLine("Mode: ${n("mode")} · Risk label: ${n("risk_per_trade_pct")}%")
            appendLine()
            append(b["note"]?.toString() ?: "")
        }.trim()
    }

    private fun configure() {
        lifecycleScope.launch {
            try {
                val prefs = applicationContext.dataStore.data.first()
                val accountId = prefs[PrefKeys.ACCOUNT_ID]?.trim().orEmpty()
                if (accountId.isBlank()) {
                    Toast.makeText(this@WithdrawalActivity, "Set Account ID first", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                val start = startOptions.getOrElse(spinnerStart.selectedItemPosition) { 1000.0 }
                val risk = riskOptions.getOrElse(spinnerRisk.selectedItemPosition) { 0.5 }
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
                    val err = resp.errorBody()?.string()?.take(180) ?: "HTTP ${resp.code()}"
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
                        "Request recorded (pending transfer process)",
                        Toast.LENGTH_LONG
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

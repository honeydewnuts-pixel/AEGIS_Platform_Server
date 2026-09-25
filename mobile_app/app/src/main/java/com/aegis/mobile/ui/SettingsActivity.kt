package com.aegis.mobile.ui

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.ArrayAdapter
import android.widget.Spinner
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.datastore.preferences.core.edit
import androidx.lifecycle.lifecycleScope
import com.aegis.mobile.R
import com.aegis.mobile.data.AegisInstruments
import com.aegis.mobile.data.DEFAULT_BROKER_NAME
import com.aegis.mobile.data.DEFAULT_MIN_CONFIDENCE
import com.aegis.mobile.data.DEFAULT_SERVER_URL
import com.aegis.mobile.data.PrefKeys
import com.aegis.mobile.data.dataStore
import com.aegis.mobile.models.Mt5ConnectRequest
import com.aegis.mobile.network.RetrofitClient
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class SettingsActivity : AppCompatActivity() {

    companion object {
        val TOLERANCE_OPTIONS = listOf(0.5, 1.0, 2.5, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0)
        val MODE_OPTIONS = listOf(
            "MultiSymbol (auto pairs within risk)" to "multi_symbol",
            "Chart only (selected pair)" to "chart_only",
        )
        /** Display label → seconds */
        val INTERVAL_OPTIONS = listOf(
            "2 seconds (scalp / M1)" to 2,
            "3 seconds" to 3,
            "5 seconds (default)" to 5,
            "10 seconds (M5)" to 10,
            "15 seconds" to 15,
            "30 seconds (M15)" to 30,
            "60 seconds (H1+)" to 60,
        )
    }

    private lateinit var etUrl: EditText
    private lateinit var etApiKey: EditText
    private lateinit var etAccountId: EditText
    private lateinit var spinnerInterval: Spinner
    private lateinit var etMt5Broker: EditText
    private lateinit var etMt5Server: EditText
    private lateinit var etMt5Login: EditText
    private lateinit var etMt5Password: EditText
    private lateinit var spinnerMt5Symbol: Spinner
    private lateinit var cbMt5Execution: CheckBox
    private lateinit var cbAutoExecute: CheckBox
    private lateinit var cbKeepNetwork: CheckBox
    private lateinit var etMinConfidence: EditText
    private lateinit var etAccountEquity: EditText
    private lateinit var spinnerRiskTolerance: Spinner
    private lateinit var spinnerTradingMode: Spinner
    private lateinit var tvPortfolioStatus: android.widget.TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        etUrl = findViewById(R.id.etServerIp)
        etApiKey = findViewById(R.id.etApiKey)
        etAccountId = findViewById(R.id.etAccountId)
        spinnerInterval = findViewById(R.id.spinnerCaptureInterval)
        val labels = INTERVAL_OPTIONS.map { it.first }
        spinnerInterval.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            labels
        )

        etMt5Broker = findViewById(R.id.etMt5Broker)
        etMt5Server = findViewById(R.id.etMt5Server)
        etMt5Login = findViewById(R.id.etMt5Login)
        etMt5Password = findViewById(R.id.etMt5Password)
        spinnerMt5Symbol = findViewById(R.id.spinnerMt5Symbol)
        spinnerMt5Symbol.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            AegisInstruments.ALL_LABELS
        )
        cbMt5Execution = findViewById(R.id.cbMt5Execution)
        cbAutoExecute = findViewById(R.id.cbAutoExecute)
        cbKeepNetwork = findViewById(R.id.cbKeepNetwork)
        etMinConfidence = findViewById(R.id.etMinConfidence)
        etAccountEquity = findViewById(R.id.etAccountEquity)
        spinnerRiskTolerance = findViewById(R.id.spinnerRiskTolerance)
        spinnerTradingMode = findViewById(R.id.spinnerTradingMode)
        tvPortfolioStatus = findViewById(R.id.tvPortfolioStatus)
        spinnerRiskTolerance.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            TOLERANCE_OPTIONS.map { "$it% of equity" }
        )
        spinnerTradingMode.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            MODE_OPTIONS.map { it.first }
        )
        findViewById<Button>(R.id.btnAlertChannels).setOnClickListener {
            startActivity(Intent(this, AlertChannelsActivity::class.java))
        }
        val btnSave = findViewById<Button>(R.id.btnSave)
        val btnSaveAndConnect = findViewById<Button>(R.id.btnSaveAndConnect)

        lifecycleScope.launch {
            val prefs = applicationContext.dataStore.data.first()
            etUrl.setText(prefs[PrefKeys.SERVER_URL] ?: DEFAULT_SERVER_URL)
            etApiKey.setText(prefs[PrefKeys.API_KEY] ?: "")
            etAccountId.setText(prefs[PrefKeys.ACCOUNT_ID] ?: "")
            val sec = prefs[PrefKeys.CAPTURE_INTERVAL_SEC] ?: com.aegis.mobile.data.DEFAULT_CAPTURE_INTERVAL_SEC
            val idx = INTERVAL_OPTIONS.indexOfFirst { it.second == sec }.let { if (it < 0) 2 else it }
            spinnerInterval.setSelection(idx)

            etMt5Broker.setText(prefs[PrefKeys.MT5_BROKER_NAME] ?: DEFAULT_BROKER_NAME)
            etMt5Server.setText(prefs[PrefKeys.MT5_SERVER] ?: "")
            etMt5Login.setText(prefs[PrefKeys.MT5_LOGIN] ?: "")
            etMt5Password.setText(prefs[PrefKeys.MT5_PASSWORD] ?: "")
            val savedSym = prefs[PrefKeys.MT5_SYMBOL] ?: "EURUSD"
            spinnerMt5Symbol.setSelection(AegisInstruments.indexOfSymbol(savedSym))
            cbMt5Execution.isChecked = prefs[PrefKeys.MT5_EXECUTION_ENABLED] ?: true
            cbAutoExecute.isChecked = prefs[PrefKeys.AUTO_EXECUTE] ?: false
            cbKeepNetwork.isChecked = prefs[PrefKeys.KEEP_NETWORK_ALIVE] ?: true
            etMinConfidence.setText(
                prefs[PrefKeys.MIN_CONFIDENCE] ?: DEFAULT_MIN_CONFIDENCE.toString()
            )
            etAccountEquity.setText(prefs[PrefKeys.ACCOUNT_EQUITY_USD] ?: "")
            val tol = prefs[PrefKeys.RISK_TOLERANCE_PCT]?.toDoubleOrNull() ?: 25.0
            val tolIdx = TOLERANCE_OPTIONS.indexOfFirst { it == tol }.let { if (it < 0) TOLERANCE_OPTIONS.indexOf(25.0).coerceAtLeast(0) else it }
            spinnerRiskTolerance.setSelection(tolIdx)
            val mode = prefs[PrefKeys.TRADING_MODE] ?: "multi_symbol"
            val modeIdx = MODE_OPTIONS.indexOfFirst { it.second == mode }.let { if (it < 0) 0 else it }
            spinnerTradingMode.setSelection(modeIdx)
        }

        btnSave.setOnClickListener {
            lifecycleScope.launch {
                persistSettings()
                val sym = AegisInstruments.symbolFromLabel(spinnerMt5Symbol.selectedItem?.toString() ?: "")
                val msg = if (AegisInstruments.isGood(sym)) {
                    "Settings saved — $sym (Good)"
                } else {
                    "Saved $sym — Not Good (V2-OPT only). Demo/live path disabled on server."
                }
                Toast.makeText(this@SettingsActivity, msg, Toast.LENGTH_LONG).show()
                finish()
            }
        }

        btnSaveAndConnect.setOnClickListener {
            lifecycleScope.launch {
                persistSettings()
                val ok = connectMt5()
                if (ok) {
                    Toast.makeText(
                        this@SettingsActivity,
                        "Saved and MT5 connect requested",
                        Toast.LENGTH_LONG
                    ).show()
                    finish()
                }
            }
        }
    }

    private suspend fun persistSettings() {
        val apiKey = etApiKey.text.toString().trim()
        val serverUrl = etUrl.text.toString().trim()
        var accountId = etAccountId.text.toString().trim()

        applicationContext.dataStore.edit { settings ->
            settings[PrefKeys.SERVER_URL] = serverUrl
            settings[PrefKeys.API_KEY] = apiKey
            settings[PrefKeys.ACCOUNT_ID] = accountId
            settings[PrefKeys.MT5_BROKER_NAME] =
                etMt5Broker.text.toString().trim().ifBlank { DEFAULT_BROKER_NAME }
            settings[PrefKeys.MT5_SERVER] = etMt5Server.text.toString().trim()
            settings[PrefKeys.MT5_LOGIN] = etMt5Login.text.toString().trim()
            settings[PrefKeys.MT5_PASSWORD] = etMt5Password.text.toString()
            settings[PrefKeys.MT5_SYMBOL] = AegisInstruments.symbolFromLabel(
                spinnerMt5Symbol.selectedItem?.toString() ?: ""
            )
            settings[PrefKeys.MT5_EXECUTION_ENABLED] = cbMt5Execution.isChecked
            settings[PrefKeys.AUTO_EXECUTE] = cbAutoExecute.isChecked
            settings[PrefKeys.KEEP_NETWORK_ALIVE] = cbKeepNetwork.isChecked
            val i = spinnerInterval.selectedItemPosition.coerceIn(0, INTERVAL_OPTIONS.lastIndex)
            settings[PrefKeys.CAPTURE_INTERVAL_SEC] = INTERVAL_OPTIONS[i].second

            settings[PrefKeys.MIN_CONFIDENCE] =
                etMinConfidence.text.toString().trim().ifBlank {
                    DEFAULT_MIN_CONFIDENCE.toString()
                }
            settings[PrefKeys.ACCOUNT_EQUITY_USD] =
                etAccountEquity.text.toString().trim()
            val ti = spinnerRiskTolerance.selectedItemPosition.coerceIn(0, TOLERANCE_OPTIONS.lastIndex)
            settings[PrefKeys.RISK_TOLERANCE_PCT] = TOLERANCE_OPTIONS[ti].toString()
            val mi = spinnerTradingMode.selectedItemPosition.coerceIn(0, MODE_OPTIONS.lastIndex)
            settings[PrefKeys.TRADING_MODE] = MODE_OPTIONS[mi].second
        }

        // Account ID must match the key — resolve from server to prevent 403
        if (apiKey.isNotBlank() && serverUrl.isNotBlank()) {
            try {
                val api = RetrofitClient.getApiService(this)
                val me = api.deviceMe()
                if (me.isSuccessful) {
                    val resolved = me.body()?.get("account_id")?.toString()?.trim().orEmpty()
                    if (resolved.isNotEmpty() && resolved != accountId) {
                        accountId = resolved
                        applicationContext.dataStore.edit { it[PrefKeys.ACCOUNT_ID] = resolved }
                        runOnUiThread {
                            etAccountId.setText(resolved)
                            Toast.makeText(
                                this,
                                "Account ID corrected to match API key: $resolved",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    } else if (resolved.isNotEmpty()) {
                        runOnUiThread {
                            Toast.makeText(this, "Credentials OK for $resolved", Toast.LENGTH_SHORT).show()
                        }
                    }
                    pushPortfolioRisk(api, accountId.ifBlank { resolved })
                } else if (me.code() == 401) {
                    runOnUiThread {
                        Toast.makeText(
                            this,
                            "API key rejected. Use portal → Connect mobile to generate a new key.",
                            Toast.LENGTH_LONG
                        ).show()
                    }
                }
            } catch (_: Exception) {
            }
        }
    }

    private suspend fun pushPortfolioRisk(api: com.aegis.mobile.network.ApiService, accountId: String) {
        if (accountId.isBlank()) return
        try {
            val equityStr = etAccountEquity.text.toString().trim()
            if (equityStr.isNotEmpty()) {
                val equity = equityStr.toDoubleOrNull()
                if (equity != null && equity >= 0) {
                    api.setPortfolioEquity(
                        mapOf(
                            "account_id" to accountId,
                            "equity_usd" to equity,
                            "source" to "mobile"
                        )
                    )
                }
            }
            val ti = spinnerRiskTolerance.selectedItemPosition.coerceIn(0, TOLERANCE_OPTIONS.lastIndex)
            api.setRiskTolerance(
                mapOf(
                    "account_id" to accountId,
                    "risk_tolerance_pct" to TOLERANCE_OPTIONS[ti]
                )
            )
            val mi = spinnerTradingMode.selectedItemPosition.coerceIn(0, MODE_OPTIONS.lastIndex)
            api.setTradingMode(
                mapOf(
                    "account_id" to accountId,
                    "trading_mode" to MODE_OPTIONS[mi].second
                )
            )
            val st = api.getPortfolioStatus(accountId)
            if (st.isSuccessful) {
                val b = st.body()
                val budget = b?.get("risk_budget_usd")
                val maxP = b?.get("max_concurrent_pairs")
                val halted = b?.get("trading_halted")
                val msg = "Budget $$budget · max pairs $maxP · halted=$halted"
                runOnUiThread { tvPortfolioStatus.text = msg }
            }
        } catch (e: Exception) {
            runOnUiThread {
                tvPortfolioStatus.text = "Portfolio sync: ${e.message}"
            }
        }
    }

    private suspend fun connectMt5(): Boolean {
        val login = etMt5Login.text.toString().trim()
        val password = etMt5Password.text.toString()
        val server = etMt5Server.text.toString().trim()
        if (login.isEmpty() || password.isEmpty() || server.isEmpty()) {
            Toast.makeText(
                this,
                "MT5 login, password and server are required to connect",
                Toast.LENGTH_LONG
            ).show()
            return false
        }

        val prefs = applicationContext.dataStore.data.first()
        val accountId = prefs[PrefKeys.ACCOUNT_ID]?.takeIf { it.isNotBlank() }
        if (accountId.isNullOrBlank()) {
            Toast.makeText(this, "Save settings first so Account ID is resolved from the API key.", Toast.LENGTH_LONG).show()
            return false
        }
        val broker = etMt5Broker.text.toString().trim().ifBlank { DEFAULT_BROKER_NAME }

        return try {
            val api = RetrofitClient.getApiService(this)
            val body = Mt5ConnectRequest(
                account_id = accountId,
                broker_name = broker,
                server = server,
                login = login,
                trading_password = password,
                execution_enabled = cbMt5Execution.isChecked
            )
            val response = api.connectMt5(body)
            if (response.isSuccessful) {
                true
            } else {
                val err = try {
                    response.errorBody()?.string()?.take(300)
                } catch (_: Exception) {
                    null
                }
                Toast.makeText(
                    this,
                    "Connect failed ${response.code()}: ${err ?: ""}",
                    Toast.LENGTH_LONG
                ).show()
                false
            }
        } catch (e: Exception) {
            Toast.makeText(this, "Connect error: ${e.message}", Toast.LENGTH_LONG).show()
            false
        }
    }
}

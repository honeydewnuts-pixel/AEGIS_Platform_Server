package com.aegis.mobile.ui

import android.os.Bundle
import android.widget.Button
import android.widget.EditText
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

/**
 * Simple Trade Copier setup on the phone:
 * activate tier → add slave MT5 logins → list status.
 * Master remains this AEGIS install; slaves follow executed trades.
 */
class CopierActivity : AppCompatActivity() {

    private lateinit var statusText: TextView
    private lateinit var slaveListText: TextView
    private lateinit var etLabel: EditText
    private lateinit var etServer: EditText
    private lateinit var etLogin: EditText
    private lateinit var etRisk: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_copier)

        statusText = findViewById(R.id.copierStatusText)
        slaveListText = findViewById(R.id.slaveListText)
        etLabel = findViewById(R.id.etSlaveLabel)
        etServer = findViewById(R.id.etSlaveServer)
        etLogin = findViewById(R.id.etSlaveLogin)
        etRisk = findViewById(R.id.etSlaveRisk)

        findViewById<Button>(R.id.btnCopier3).setOnClickListener { activate("copier_3") }
        findViewById<Button>(R.id.btnCopier10).setOnClickListener { activate("copier_10") }
        findViewById<Button>(R.id.btnCopier25).setOnClickListener { activate("copier_25") }
        findViewById<Button>(R.id.btnAddSlave).setOnClickListener { addSlave() }
        findViewById<Button>(R.id.btnRefreshCopier).setOnClickListener { refresh() }

        refresh()
    }

    private suspend fun accountId(): String? {
        val prefs = applicationContext.dataStore.data.first()
        return prefs[PrefKeys.ACCOUNT_ID]?.takeIf { it.isNotBlank() }
    }

    private fun refresh() {
        lifecycleScope.launch {
            try {
                val id = accountId()
                if (id.isNullOrBlank()) {
                    statusText.text = "Set API key in Settings first (Account ID is filled from the key)."
                    return@launch
                }
                val api = RetrofitClient.getApiService(this@CopierActivity)
                val res = api.copierStatus(id)
                if (!res.isSuccessful) {
                    statusText.text = "Status error ${res.code()}: ${res.errorBody()?.string()?.take(200)}"
                    return@launch
                }
                val body = res.body() ?: emptyMap()
                val active = body["active"] == true
                if (!active) {
                    statusText.text = "Copier: OFF\nAccount: $id\nActivate a tier below (3 / 10 / 25 slaves)."
                    slaveListText.text = "No slaves — activate first, then add."
                    return@launch
                }
                val tier = body["tier"]?.toString() ?: "—"
                val max = body["max_slaves"]
                val count = body["slave_count"]
                statusText.text = "Copier: ON · tier $tier\nAccount: $id\nSlaves: $count / $max"
                val slaves = body["slaves"] as? List<*>
                if (slaves.isNullOrEmpty()) {
                    slaveListText.text = "No slaves yet. Add server + login below."
                } else {
                    val lines = slaves.mapNotNull { row ->
                        val m = row as? Map<*, *> ?: return@mapNotNull null
                        val on = if (m["enabled"] == true) "ON" else "OFF"
                        "#${m["id"]} ${m["label"]} · ${m["login"]} @ ${m["server"]}\n  risk ${m["risk_mode"]}=${m["risk_value"]} · $on"
                    }
                    slaveListText.text = lines.joinToString("\n\n")
                }
            } catch (e: Exception) {
                statusText.text = "Network error: ${e.message}"
            }
        }
    }

    private fun activate(tier: String) {
        lifecycleScope.launch {
            try {
                val id = accountId()
                if (id.isNullOrBlank()) {
                    Toast.makeText(this@CopierActivity, "Save Settings (API key) first", Toast.LENGTH_LONG).show()
                    return@launch
                }
                val api = RetrofitClient.getApiService(this@CopierActivity)
                val res = api.copierActivate(mapOf("account_id" to id, "tier" to tier))
                if (res.isSuccessful) {
                    Toast.makeText(this@CopierActivity, "Trade Copier activated ($tier)", Toast.LENGTH_LONG).show()
                    refresh()
                } else {
                    val err = res.errorBody()?.string()?.take(300)
                    Toast.makeText(this@CopierActivity, "Activate failed ${res.code()}: $err", Toast.LENGTH_LONG).show()
                }
            } catch (e: Exception) {
                Toast.makeText(this@CopierActivity, e.message, Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun addSlave() {
        lifecycleScope.launch {
            try {
                val id = accountId()
                if (id.isNullOrBlank()) {
                    Toast.makeText(this@CopierActivity, "Save Settings first", Toast.LENGTH_LONG).show()
                    return@launch
                }
                val server = etServer.text.toString().trim()
                val login = etLogin.text.toString().trim()
                if (server.isEmpty() || login.isEmpty()) {
                    Toast.makeText(this@CopierActivity, "Server and login required", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                val risk = etRisk.text.toString().toDoubleOrNull() ?: 1.0
                val api = RetrofitClient.getApiService(this@CopierActivity)
                val res = api.copierAddSlave(
                    mapOf(
                        "account_id" to id,
                        "label" to etLabel.text.toString().trim().ifBlank { "Slave" },
                        "server" to server,
                        "login" to login,
                        "risk_mode" to "multiplier",
                        "risk_value" to risk,
                    )
                )
                if (res.isSuccessful) {
                    Toast.makeText(this@CopierActivity, "Slave added", Toast.LENGTH_SHORT).show()
                    etLogin.text.clear()
                    refresh()
                } else {
                    val err = res.errorBody()?.string()?.take(300)
                    Toast.makeText(this@CopierActivity, "Add failed ${res.code()}: $err", Toast.LENGTH_LONG).show()
                }
            } catch (e: Exception) {
                Toast.makeText(this@CopierActivity, e.message, Toast.LENGTH_LONG).show()
            }
        }
    }
}

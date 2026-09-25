package com.aegis.mobile.ui

import android.os.Bundle
import android.widget.Button
import android.widget.CheckBox
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
 * Client UI for email / Telegram / SMS / WhatsApp alert destinations.
 * Saves to PUT /api/notifications/preferences (server-side delivery when configured).
 */
class AlertChannelsActivity : AppCompatActivity() {

    private lateinit var cbSignal: CheckBox
    private lateinit var cbExecution: CheckBox
    private lateinit var cbSystem: CheckBox
    private lateinit var etMinConf: EditText
    private lateinit var cbEmail: CheckBox
    private lateinit var etEmail: EditText
    private lateinit var cbTelegram: CheckBox
    private lateinit var etTelegram: EditText
    private lateinit var cbSms: CheckBox
    private lateinit var etSms: EditText
    private lateinit var cbWhatsapp: CheckBox
    private lateinit var etWhatsapp: EditText
    private lateinit var status: TextView
    private var accountId: String = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_alert_channels)
        title = "Alert channels"

        cbSignal = findViewById(R.id.cbSignalAlerts)
        cbExecution = findViewById(R.id.cbExecutionAlerts)
        cbSystem = findViewById(R.id.cbSystemAlerts)
        etMinConf = findViewById(R.id.etMinConfidence)
        cbEmail = findViewById(R.id.cbEmail)
        etEmail = findViewById(R.id.etEmail)
        cbTelegram = findViewById(R.id.cbTelegram)
        etTelegram = findViewById(R.id.etTelegram)
        cbSms = findViewById(R.id.cbSms)
        etSms = findViewById(R.id.etSms)
        cbWhatsapp = findViewById(R.id.cbWhatsapp)
        etWhatsapp = findViewById(R.id.etWhatsapp)
        status = findViewById(R.id.tvAlertStatus)

        findViewById<Button>(R.id.btnSaveAlerts).setOnClickListener { save() }

        lifecycleScope.launch {
            accountId = dataStore.data.first()[PrefKeys.ACCOUNT_ID]?.trim().orEmpty()
            if (accountId.isEmpty()) {
                status.text = "Set Account ID and API key in Settings first."
                Toast.makeText(this@AlertChannelsActivity, "Account ID required", Toast.LENGTH_LONG).show()
                return@launch
            }
            load()
        }
    }

    private fun load() {
        lifecycleScope.launch {
            try {
                val api = RetrofitClient.getApiService(this@AlertChannelsActivity)
                val resp = api.getNotificationPreferences(accountId)
                if (!resp.isSuccessful) {
                    status.text = "Could not load preferences (HTTP ${resp.code()}). You can still enter values and Save."
                    return@launch
                }
                val b = resp.body() ?: return@launch
                runOnUiThread {
                    cbSignal.isChecked = b["signal_alerts"] as? Boolean ?: true
                    cbExecution.isChecked = b["execution_alerts"] as? Boolean ?: true
                    cbSystem.isChecked = b["system_alerts"] as? Boolean ?: true
                    val mc = b["min_confidence"]
                    etMinConf.setText(
                        when (mc) {
                            is Number -> mc.toString()
                            is String -> mc
                            else -> "0.55"
                        }
                    )
                    cbEmail.isChecked = b["email_enabled"] as? Boolean ?: false
                    etEmail.setText((b["email_address"] ?: "").toString())
                    cbTelegram.isChecked = b["telegram_enabled"] as? Boolean ?: false
                    etTelegram.setText((b["telegram_chat_id"] ?: "").toString())
                    cbSms.isChecked = b["sms_enabled"] as? Boolean ?: false
                    etSms.setText((b["sms_number"] ?: "").toString())
                    cbWhatsapp.isChecked = b["whatsapp_enabled"] as? Boolean ?: false
                    etWhatsapp.setText((b["whatsapp_number"] ?: "").toString())
                    status.text = "Loaded saved preferences for $accountId"
                }
            } catch (e: Exception) {
                status.text = e.message ?: "Load error"
            }
        }
    }

    private fun save() {
        if (accountId.isEmpty()) {
            Toast.makeText(this, "Account ID required in Settings", Toast.LENGTH_SHORT).show()
            return
        }
        val minConf = etMinConf.text?.toString()?.trim()?.toDoubleOrNull() ?: 0.55
        val body = mapOf(
            "signal_alerts" to cbSignal.isChecked,
            "execution_alerts" to cbExecution.isChecked,
            "system_alerts" to cbSystem.isChecked,
            "min_confidence" to minConf,
            "email_enabled" to cbEmail.isChecked,
            "email_address" to etEmail.text?.toString()?.trim().orEmpty(),
            "telegram_enabled" to cbTelegram.isChecked,
            "telegram_chat_id" to etTelegram.text?.toString()?.trim().orEmpty(),
            "sms_enabled" to cbSms.isChecked,
            "sms_number" to etSms.text?.toString()?.trim().orEmpty(),
            "whatsapp_enabled" to cbWhatsapp.isChecked,
            "whatsapp_number" to etWhatsapp.text?.toString()?.trim().orEmpty(),
        )
        lifecycleScope.launch {
            try {
                val api = RetrofitClient.getApiService(this@AlertChannelsActivity)
                val resp = api.putNotificationPreferences(accountId, body)
                if (!resp.isSuccessful) {
                    status.text = "Save failed (HTTP ${resp.code()})"
                    Toast.makeText(this@AlertChannelsActivity, "Save failed", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                status.text = "Saved. Alerts will use enabled channels when the server has SMTP/Telegram/Twilio configured."
                Toast.makeText(this@AlertChannelsActivity, "Alert preferences saved", Toast.LENGTH_SHORT).show()
            } catch (e: Exception) {
                status.text = e.message ?: "error"
                Toast.makeText(this@AlertChannelsActivity, e.message ?: "error", Toast.LENGTH_SHORT).show()
            }
        }
    }
}

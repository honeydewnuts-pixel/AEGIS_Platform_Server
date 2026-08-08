package com.aegis.mobile.ui

import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import androidx.appcompat.app.AppCompatActivity
import androidx.datastore.preferences.core.edit
import androidx.lifecycle.lifecycleScope
import com.aegis.mobile.R
import com.aegis.mobile.data.DEFAULT_SERVER_IP
import com.aegis.mobile.data.PrefKeys
import com.aegis.mobile.data.dataStore
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class SettingsActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        val etIp = findViewById<EditText>(R.id.etServerIp)
        val etApiKey = findViewById<EditText>(R.id.etApiKey)
        val etAccountId = findViewById<EditText>(R.id.etAccountId)
        val btnSave = findViewById<Button>(R.id.btnSave)

        lifecycleScope.launch {
            val prefs = applicationContext.dataStore.data.first()
            etIp.setText(prefs[PrefKeys.SERVER_IP] ?: DEFAULT_SERVER_IP)
            etApiKey.setText(prefs[PrefKeys.API_KEY] ?: "")
            etAccountId.setText(prefs[PrefKeys.ACCOUNT_ID] ?: "")
        }

        btnSave.setOnClickListener {
            lifecycleScope.launch {
                applicationContext.dataStore.edit { settings ->
                    settings[PrefKeys.SERVER_IP] = etIp.text.toString()
                    settings[PrefKeys.API_KEY] = etApiKey.text.toString()
                    settings[PrefKeys.ACCOUNT_ID] = etAccountId.text.toString()
                }
                finish()
            }
        }
    }
}

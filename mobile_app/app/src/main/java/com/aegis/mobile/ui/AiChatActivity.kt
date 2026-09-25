package com.aegis.mobile.ui

import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.ScrollView
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

class AiChatActivity : AppCompatActivity() {
    private lateinit var log: TextView
    private lateinit var input: EditText
    private lateinit var scroll: ScrollView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_ai_chat)
        log = findViewById(R.id.chatLog)
        input = findViewById(R.id.aiInput)
        scroll = findViewById(R.id.chatScroll)
        findViewById<Button>(R.id.aiSendBtn).setOnClickListener { ask() }
        loadHistory()
    }

    private fun append(line: String) {
        log.append(line + "\n\n")
        scroll.post { scroll.fullScroll(ScrollView.FOCUS_DOWN) }
    }

    private fun loadHistory() {
        lifecycleScope.launch {
            try {
                val prefs = dataStore.data.first()
                val accountId = prefs[PrefKeys.ACCOUNT_ID]?.trim().orEmpty()
                if (accountId.isEmpty()) return@launch
                val api = RetrofitClient.getApiService(this@AiChatActivity)
                val resp = api.aiHistory(accountId, 40)
                if (!resp.isSuccessful) return@launch
                @Suppress("UNCHECKED_CAST")
                val rows = (resp.body()?.get("messages") as? List<Map<String, Any?>>) ?: emptyList()
                val sb = StringBuilder()
                rows.forEach {
                    val role = (it["role"] ?: "").toString()
                    val body = (it["body"] ?: "").toString()
                    val who = if (role == "user") "You" else "AEGIS AI"
                    sb.append("$who:\n$body\n\n")
                }
                runOnUiThread {
                    if (sb.isNotEmpty()) log.text = sb.toString()
                }
            } catch (_: Exception) {}
        }
    }

    private fun ask() {
        val q = input.text?.toString()?.trim().orEmpty()
        if (q.isEmpty()) return
        append("You:\n$q")
        input.setText("")
        lifecycleScope.launch {
            try {
                val prefs = dataStore.data.first()
                val accountId = prefs[PrefKeys.ACCOUNT_ID]?.trim().orEmpty()
                if (accountId.isEmpty()) {
                    Toast.makeText(this@AiChatActivity, "Set Account ID in Settings", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                val api = RetrofitClient.getApiService(this@AiChatActivity)
                val resp = api.aiChat(mapOf("account_id" to accountId, "message" to q))
                if (!resp.isSuccessful) {
                    append("AEGIS AI:\n(HTTP ${resp.code()})")
                    return@launch
                }
                val body = (resp.body()?.get("body") ?: "").toString()
                append("AEGIS AI:\n$body")
            } catch (e: Exception) {
                append("AEGIS AI:\n${e.message ?: "error"}")
            }
        }
    }
}

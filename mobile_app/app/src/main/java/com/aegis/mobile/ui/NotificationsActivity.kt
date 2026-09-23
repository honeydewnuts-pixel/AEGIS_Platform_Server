package com.aegis.mobile.ui

import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.view.View
import android.widget.LinearLayout
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

class NotificationsActivity : AppCompatActivity() {

    private lateinit var list: LinearLayout
    private lateinit var empty: TextView
    private lateinit var badge: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_notifications)
        list = findViewById(R.id.notifList)
        empty = findViewById(R.id.notifEmpty)
        badge = findViewById(R.id.notifUnreadBadge)
        findViewById<AppCompatButton>(R.id.notifRefreshBtn).setOnClickListener { load() }
        findViewById<AppCompatButton>(R.id.notifReadAllBtn).setOnClickListener { markAll() }
        findViewById<AppCompatButton>(R.id.notifCloseBtn).setOnClickListener { finish() }
        load()
    }

    private fun load() {
        lifecycleScope.launch {
            try {
                val prefs = dataStore.data.first()
                val accountId = prefs[PrefKeys.ACCOUNT_ID]?.trim().orEmpty()
                if (accountId.isEmpty()) {
                    Toast.makeText(this@NotificationsActivity, "Set Account ID in Settings", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                val api = RetrofitClient.getApiService(this@NotificationsActivity)
                val resp = api.listNotifications(accountId, 50, false)
                if (!resp.isSuccessful) {
                    Toast.makeText(this@NotificationsActivity, "HTTP ${resp.code()}", Toast.LENGTH_SHORT).show()
                    return@launch
                }
                val body = resp.body() ?: emptyMap()
                val unread = (body["unread_count"] as? Number)?.toInt() ?: 0
                @Suppress("UNCHECKED_CAST")
                val rows = (body["notifications"] as? List<Map<String, Any?>>) ?: emptyList()
                runOnUiThread {
                    badge.text = "$unread unread"
                    list.removeAllViews()
                    if (rows.isEmpty()) {
                        empty.visibility = View.VISIBLE
                    } else {
                        empty.visibility = View.GONE
                        for (row in rows) {
                            list.addView(rowView(row, accountId))
                        }
                    }
                }
            } catch (e: Exception) {
                Toast.makeText(this@NotificationsActivity, "Alerts: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun markAll() {
        lifecycleScope.launch {
            try {
                val prefs = dataStore.data.first()
                val accountId = prefs[PrefKeys.ACCOUNT_ID]?.trim().orEmpty()
                if (accountId.isEmpty()) return@launch
                val api = RetrofitClient.getApiService(this@NotificationsActivity)
                api.markAllNotificationsRead(accountId)
                load()
            } catch (e: Exception) {
                Toast.makeText(this@NotificationsActivity, "Mark all failed: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun rowView(row: Map<String, Any?>, accountId: String): View {
        val unread = row["unread"] == true || row["read_at"] == null
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16, 14, 16, 14)
            setBackgroundColor(if (unread) Color.parseColor("#152238") else Color.parseColor("#0F1A2A"))
            val lp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            lp.bottomMargin = 8
            layoutParams = lp
        }
        box.addView(TextView(this).apply {
            text = row["title"]?.toString() ?: row["type"]?.toString() ?: "Alert"
            setTextColor(Color.WHITE)
            textSize = 15f
            setTypeface(typeface, Typeface.BOLD)
        })
        box.addView(TextView(this).apply {
            val pair = row["pair"]?.toString() ?: ""
            val sig = row["signal"]?.toString() ?: ""
            val conf = row["confidence"]
            val whenStr = row["created_at"]?.toString()?.take(19)?.replace('T', ' ') ?: ""
            text = listOf(whenStr, pair, sig, conf?.let { "conf=$it" })
                .filter { !it.isNullOrBlank() }.joinToString(" · ")
            setTextColor(Color.parseColor("#90A4AE"))
            textSize = 12f
        })
        box.addView(TextView(this).apply {
            text = row["message"]?.toString() ?: ""
            setTextColor(Color.parseColor("#CFD8DC"))
            textSize = 13f
        })
        val id = (row["id"] as? Number)?.toInt()
        if (id != null && unread) {
            box.setOnClickListener {
                lifecycleScope.launch {
                    try {
                        RetrofitClient.getApiService(this@NotificationsActivity)
                            .markNotificationRead(id, accountId)
                        load()
                    } catch (_: Exception) {
                    }
                }
            }
        }
        return box
    }
}

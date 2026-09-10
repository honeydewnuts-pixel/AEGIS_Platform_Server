package com.aegis.mobile.ui

import android.os.Bundle
import android.widget.Button
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.aegis.mobile.R
import com.aegis.mobile.network.RetrofitClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Shows tradeable pairs + rulebook registry.
 * MT5 charts do NOT need indicator templates installed.
 */
class RegistryActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val scroll = ScrollView(this)
        val body = TextView(this).apply {
            setPadding(32, 32, 32, 32)
            textSize = 13f
            text = "Loading registry…"
        }
        val refresh = Button(this).apply { text = "Refresh" }
        val markDone = Button(this).apply { text = "OK — no indicators needed" }
        val root = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            addView(refresh)
            addView(markDone)
            addView(body)
        }
        scroll.addView(root)
        setContentView(scroll)
        title = "Pairs & Rulebooks"

        fun load() {
            lifecycleScope.launch {
                try {
                    val api = RetrofitClient.getApiService(this@RegistryActivity)
                    val data = withContext(Dispatchers.IO) {
                        val resp = try {
                            api.getRegistryActive()
                        } catch (_: Exception) {
                            api.getActiveTemplates()
                        }
                        resp.body() ?: emptyMap()
                    }
                    val sb = StringBuilder()
                    sb.append("AEGIS does NOT require MT5 indicators.\n")
                    sb.append("Use a plain price chart. Pair selection is registry-driven.\n\n")
                    val pairs = (data["tradeable_pairs"] as? List<*>) ?: emptyList<Any>()
                    sb.append("Tradeable pairs (${pairs.size}):\n")
                    pairs.forEach { sb.append("  • $it\n") }
                    sb.append("\n")
                    val instruments = data["instruments"] as? List<*>
                    if (instruments != null) {
                        sb.append("Instrument detail:\n")
                        for (row in instruments) {
                            val m = row as? Map<*, *> ?: continue
                            sb.append("  ${m["instrument"]}  ${m["router_status"]}  ${m["registry_status"]}\n")
                            val books = m["eligible_rulebooks"] as? List<*>
                            if (!books.isNullOrEmpty()) sb.append("    rules: ${books.joinToString()}\n")
                        }
                    }
                    val active = data["active"] as? Map<*, *>
                    if (active != null) {
                        sb.append("\nActive: rulebook=${active["rulebook_version"]} registry=${active["registry_version"]}\n")
                    }
                    sb.append("\nRulebooks are evaluated on the server from chart screenshots.\n")
                    body.text = sb.toString()
                } catch (e: Exception) {
                    body.text = "Error loading registry: ${e.message}\n\nNo MT5 indicators are required."
                }
            }
        }

        refresh.setOnClickListener { load() }
        markDone.setOnClickListener {
            getSharedPreferences("aegis_prefs", MODE_PRIVATE)
                .edit()
                .putBoolean("registry_confirmed", true)
                .putBoolean("indicator_template_confirmed", true) // legacy flag so old checks pass
                .putLong("registry_confirmed_at", System.currentTimeMillis())
                .apply()
            Toast.makeText(this, "Registry acknowledged", Toast.LENGTH_SHORT).show()
            finish()
        }
        load()
    }
}

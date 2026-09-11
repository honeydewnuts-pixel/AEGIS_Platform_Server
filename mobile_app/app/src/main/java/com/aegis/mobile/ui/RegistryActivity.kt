package com.aegis.mobile.ui

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.aegis.mobile.R
import com.aegis.mobile.network.RetrofitClient
import kotlinx.coroutines.launch

/**
 * Full pairs + rulebook registry viewer.
 * Shows tradeable and non-tradeable instruments so operators see the complete V40 registry.
 */
open class RegistryActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_registry)

        val body = findViewById<TextView>(R.id.registryBody)
        val refresh = findViewById<Button>(R.id.registryRefresh)
        val markDone = findViewById<Button>(R.id.registryDone)

        fun load() {
            body.text = "Loading full registry…"
            lifecycleScope.launch {
                try {
                    val api = RetrofitClient.getApiService(this@RegistryActivity)
                    // Full instrument list (includes rejected / disabled)
                    val pairsResp = api.getRegistryPairs(tradeableOnly = false)
                    val activeResp = api.getRegistryActive()

                    val sb = StringBuilder()
                    sb.append("AEGIS registry (full)\n")
                    sb.append("Plain MT5 price chart only — no indicator pack.\n\n")

                    if (!pairsResp.isSuccessful) {
                        sb.append("Pairs HTTP ${pairsResp.code()}\n")
                    } else {
                        val data = pairsResp.body() ?: emptyMap()
                        val pairs = (data["pairs"] as? List<*>) ?: emptyList<Any>()
                        val tradeable = pairs.filterIsInstance<Map<*, *>>().filter {
                            it["tradeable"] == true
                        }
                        val blocked = pairs.filterIsInstance<Map<*, *>>().filter {
                            it["tradeable"] != true
                        }

                        sb.append("Tradeable / research-eligible (${tradeable.size})\n")
                        for (m in tradeable) {
                            val inst = m["instrument"] ?: "?"
                            val tf = m["timeframe"] ?: ""
                            val rs = m["router_status"] ?: ""
                            val reg = m["registry_status"] ?: ""
                            val reason = (m["reason"] as? String)?.take(80) ?: ""
                            val books = (m["eligible_rulebooks"] as? List<*>)?.map { it.toString() } ?: emptyList()
                            sb.append("  ✓ $inst $tf\n")
                            sb.append("      $rs · $reg\n")
                            if (reason.isNotBlank()) sb.append("      $reason\n")
                            if (books.isNotEmpty()) sb.append("      rules: ${books.joinToString()}\n")
                        }

                        sb.append("\nNot tradeable / blocked (${blocked.size})\n")
                        for (m in blocked) {
                            val inst = m["instrument"] ?: "?"
                            val tf = m["timeframe"] ?: ""
                            val rs = m["router_status"] ?: ""
                            val reg = m["registry_status"] ?: ""
                            val reason = (m["reason"] as? String)?.take(100) ?: ""
                            sb.append("  ✗ $inst $tf\n")
                            sb.append("      $rs · $reg\n")
                            if (reason.isNotBlank()) sb.append("      $reason\n")
                        }

                        if (pairs.isEmpty()) {
                            sb.append("(no instruments returned)\n")
                        }
                    }

                    if (activeResp.isSuccessful) {
                        val data = activeResp.body()
                        val active = data?.get("active") as? Map<*, *>
                        if (active != null) {
                            sb.append(
                                "\nProfile: rulebook=${active["rulebook_version"]} " +
                                    "registry=${active["registry_version"]}\n"
                            )
                        }
                        val rc = data?.get("rulebook_count")
                        val ic = data?.get("instrument_count")
                        if (rc != null || ic != null) {
                            sb.append("Counts: rulebooks=$rc instruments=$ic\n")
                        }
                    }

                    sb.append("\nRulebooks run on the server from chart screenshots.\n")
                    body.text = sb.toString()
                } catch (e: Exception) {
                    body.text =
                        "Error loading registry: ${e.message}\n\nNo MT5 indicators are required."
                }
            }
        }

        refresh.setOnClickListener { load() }
        markDone.setOnClickListener {
            getSharedPreferences("aegis_prefs", MODE_PRIVATE)
                .edit()
                .putBoolean("registry_confirmed", true)
                .putBoolean("indicator_template_confirmed", true)
                .putLong("registry_confirmed_at", System.currentTimeMillis())
                .apply()
            Toast.makeText(this, "Registry acknowledged", Toast.LENGTH_SHORT).show()
            finish()
        }
        load()
    }
}

package com.aegis.mobile.ui

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.aegis.mobile.R

class AdminLoginActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_admin_login)
        title = "AEGIS Ops"

        val prefs = getSharedPreferences("aegis_admin", MODE_PRIVATE)
        val etUrl = findViewById<EditText>(R.id.adminEtUrl)
        val etKey = findViewById<EditText>(R.id.adminEtKey)
        val msg = findViewById<TextView>(R.id.adminLoginMsg)

        etUrl.setText(prefs.getString("url", "https://aegis-api-0z1p.onrender.com") ?: "")
        etKey.setText(prefs.getString("key", "") ?: "")

        findViewById<Button>(R.id.adminBtnLogin).setOnClickListener {
            val url = etUrl.text.toString().trim().trimEnd('/')
            val key = etKey.text.toString().trim()
            if (url.isBlank() || key.isBlank()) {
                msg.text = "Server URL and ADMIN_API_KEY are required."
                return@setOnClickListener
            }
            prefs.edit().putString("url", url).putString("key", key).apply()
            startActivity(Intent(this, AdminDashboardActivity::class.java))
        }
    }
}

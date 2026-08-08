package com.aegis.mobile.ui

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.ViewModelProvider
import com.aegis.mobile.R
import com.aegis.mobile.automation.Mt5AccessibilityService
import com.aegis.mobile.capture.ScreenCaptureService
import com.aegis.mobile.data.HealthStatus

class MainActivity : AppCompatActivity() {

    private lateinit var viewModel: StatusViewModel
    private lateinit var statusText: TextView
    private lateinit var detailsText: TextView
    private lateinit var healthText: TextView
    private lateinit var startBtn: Button
    private lateinit var settingsBtn: Button
    private lateinit var batteryBtn: Button

    private val minConfidenceToExecute = 0.70f

    private val screenCaptureLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            val serviceIntent = Intent(this, ScreenCaptureService::class.java).apply {
                putExtra(ScreenCaptureService.EXTRA_RESULT_CODE, result.resultCode)
                putExtra(ScreenCaptureService.EXTRA_RESULT_DATA, result.data)
            }
            startForegroundService(serviceIntent)
            Toast.makeText(this, "AEGIS Started", Toast.LENGTH_SHORT).show()
            maybePromptBatteryExemption()
        } else {
            Toast.makeText(this, "Screen capture permission denied", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusText = findViewById(R.id.statusText)
        detailsText = findViewById(R.id.detailsText)
        healthText = findViewById(R.id.healthText)
        startBtn = findViewById(R.id.startBtn)
        settingsBtn = findViewById(R.id.settingsBtn)
        batteryBtn = findViewById(R.id.batteryBtn)

        viewModel = ViewModelProvider(this)[StatusViewModel::class.java]

        viewModel.signal.observe(this) { signal ->
            statusText.text = "Signal: $signal"

            val confidence = viewModel.confidence.value ?: 0f
            if (signal == "BUY" || signal == "SELL") {
                if (!isAccessibilityEnabled()) {
                    Toast.makeText(this, "Enable Accessibility Service first!", Toast.LENGTH_LONG).show()
                    openAccessibilitySettings()
                } else if (confidence < minConfidenceToExecute) {
                    Toast.makeText(
                        this,
                        "Ignored $signal - confidence $confidence below threshold",
                        Toast.LENGTH_SHORT
                    ).show()
                } else {
                    val attempted = Mt5AccessibilityService.executeTrade(signal)
                    if (attempted) {
                        Toast.makeText(this, "Executing $signal on MT5", Toast.LENGTH_SHORT).show()
                    } else {
                        Toast.makeText(this, "$signal skipped (cooldown active)", Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }

        viewModel.details.observe(this) { details ->
            detailsText.text = details
        }

        // Live health readout - lets you SEE the capture loop is actually alive
        // (last capture time, failures, whether the projection got revoked) rather
        // than just trusting the notification.
        val refreshHealth = {
            val lastCapture = HealthStatus.lastCaptureTimeMs.value ?: 0L
            val secondsAgo = if (lastCapture > 0) (System.currentTimeMillis() - lastCapture) / 1000 else -1
            val failures = HealthStatus.consecutiveFailures.value ?: 0
            val projectionOk = HealthStatus.mediaProjectionActive.value ?: false
            val pendingCache = HealthStatus.pendingCacheCount.value ?: 0
            val cacheSuffix = if (pendingCache > 0) " · $pendingCache queued offline" else ""

            healthText.text = when {
                lastCapture == 0L -> "Not started"
                !projectionOk -> "⚠ Capture stopped - tap START to resume"
                failures > 0 -> "⚠ $failures consecutive failures - last capture ${secondsAgo}s ago$cacheSuffix"
                else -> "✓ Healthy - last capture ${secondsAgo}s ago$cacheSuffix"
            }
        }
        HealthStatus.lastCaptureTimeMs.observe(this) { refreshHealth() }
        HealthStatus.consecutiveFailures.observe(this) { refreshHealth() }
        HealthStatus.mediaProjectionActive.observe(this) { refreshHealth() }
        HealthStatus.pendingCacheCount.observe(this) { refreshHealth() }

        startBtn.setOnClickListener {
            requestScreenCapturePermission()
        }

        settingsBtn.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }

        batteryBtn.setOnClickListener {
            requestBatteryExemption()
        }

        updateBatteryButtonLabel()
    }

    override fun onResume() {
        super.onResume()
        updateBatteryButtonLabel()
    }

    private fun requestScreenCapturePermission() {
        val projectionManager =
            getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        screenCaptureLauncher.launch(projectionManager.createScreenCaptureIntent())
    }

    private fun isIgnoringBatteryOptimizations(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return true
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        return pm.isIgnoringBatteryOptimizations(packageName)
    }

    private fun updateBatteryButtonLabel() {
        batteryBtn.text = if (isIgnoringBatteryOptimizations()) {
            "BACKGROUND RUNNING: ALLOWED ✓"
        } else {
            "ALLOW BACKGROUND RUNNING (recommended)"
        }
    }

    /**
     * Without this, Android's Doze/App Standby (and on some phones - Xiaomi,
     * Huawei, Samsung, OnePlus - even more aggressive OEM battery managers)
     * can throttle or kill the capture service over time. This system dialog
     * is the one thing a normal app is allowed to ask for; OEM-specific
     * "auto-start"/"protected apps" whitelisting has to be done manually by
     * the user in their phone's own battery settings - there's no public API
     * for that, so the best I can do is point people to it.
     */
    private fun requestBatteryExemption() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M || isIgnoringBatteryOptimizations()) {
            Toast.makeText(this, "Already allowed to run in the background.", Toast.LENGTH_SHORT).show()
            return
        }
        try {
            val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                data = Uri.parse("package:$packageName")
            }
            startActivity(intent)
        } catch (e: Exception) {
            // Some OEMs block this intent outright - fall back to the general battery settings screen.
            startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
        }
    }

    private fun maybePromptBatteryExemption() {
        if (!isIgnoringBatteryOptimizations()) {
            Toast.makeText(
                this,
                "Tip: tap 'Allow background running' below so Android doesn't kill AEGIS.",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    private fun isAccessibilityEnabled(): Boolean {
        val service = "$packageName/com.aegis.mobile.automation.Mt5AccessibilityService"
        val enabledServices = Settings.Secure.getString(
            contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        )
        return enabledServices?.contains(service) == true
    }

    private fun openAccessibilitySettings() {
        startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
    }
}

package com.aegis.mobile.automation

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.aegis.mobile.data.SignalRepository

class Mt5AccessibilityService : AccessibilityService() {

    companion object {
        @Volatile
        var instance: Mt5AccessibilityService? = null

        // Minimum time between two executed trades, even if the signal keeps firing
        // every capture cycle (every 3s). Prevents spamming orders on a persistent signal.
        private const val COOLDOWN_MS = 60_000L

        /**
         * @param signal "BUY" or "SELL"
         * @return true if a click was attempted, false if blocked by cooldown or service not ready
         */
        fun executeTrade(signal: String): Boolean {
            val now = System.currentTimeMillis()
            if (now - SignalRepository.lastExecutionTimeMs < COOLDOWN_MS) {
                Log.d("AEGIS-Auto", "Skipped $signal - still in cooldown")
                return false
            }
            val svc = instance ?: run {
                Log.e("AEGIS-Auto", "Accessibility service not connected")
                return false
            }
            SignalRepository.lastExecutionTimeMs = now
            svc.performMt5Click(signal)
            return true
        }
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        val info = AccessibilityServiceInfo().apply {
            eventTypes = AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED
            packageNames = arrayOf("net.metaquotes.metatrader5") // MT5 package
            feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
            flags = AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
        }
        this.serviceInfo = info
        Log.d("AEGIS-Auto", "Accessibility Service Connected")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}
    override fun onInterrupt() {}

    private fun performMt5Click(signal: String) {
        val root = rootInActiveWindow ?: return
        // NOTE: This only searches for a clickable node whose text contains "Buy"/"Sell".
        // Real order placement in MT5 involves opening the order panel, setting volume,
        // and confirming - this single click is a starting point, not a complete flow.
        // You will need to inspect MT5's actual accessibility node tree on your device
        // (e.g. with the "Accessibility Scanner" app) and extend this to walk through
        // each step of the real order dialog.
        val buttonText = if (signal == "BUY") "Buy" else "Sell"

        val found = findAndClick(root, buttonText)
        Log.d("AEGIS-Auto", "Attempted to click: $buttonText, found=$found")
    }

    private fun findAndClick(node: AccessibilityNodeInfo, text: String): Boolean {
        if (node.text?.toString()?.contains(text, ignoreCase = true) == true && node.isClickable) {
            return node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
        }
        for (i in 0 until node.childCount) {
            node.getChild(i)?.let {
                if (findAndClick(it, text)) return true
            }
        }
        return false
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
    }
}

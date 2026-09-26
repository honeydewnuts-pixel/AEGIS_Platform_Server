package com.aegis.mobile.data

import java.util.Calendar
import java.util.Locale
import java.util.TimeZone

/**
 * Mirrors server market_hours_service (approx UTC FX weekend).
 * ALWAYS_OPEN symbols (crypto / vol) never pause.
 */
object MarketHours {
    private val alwaysOpenPrefixes = listOf(
        "BTC", "ETH", "XBT", "LTC", "XRP", "SOL", "DOGE", "ADA", "BNB",
        "VOL", "VIX", "STEP", "BOOM", "CRASH", "JUMP"
    )
    private val metalPrefixes = listOf("XAU", "XAG", "XPT", "XPD", "GOLD", "SILVER")

    fun normalize(symbol: String?): String {
        if (symbol.isNullOrBlank()) return ""
        var s = symbol.trim().uppercase(Locale.US)
        if ('.' in s) s = s.substringBefore('.')
        return s.filter { it.isLetterOrDigit() }
    }

    fun isAlwaysOpen(symbol: String?): Boolean {
        val b = normalize(symbol)
        if (b.isEmpty()) return false
        if (alwaysOpenPrefixes.any { b.startsWith(it) }) return true
        if (b.contains("VOLATILITY") || b.contains("CRYPTO")) return true
        if (Regex("^V(OL)?\\d+").containsMatchIn(b)) return true
        return false
    }

    /** Approximate FX session open in UTC. */
    fun fxSessionOpenUtc(nowMs: Long = System.currentTimeMillis()): Boolean {
        val cal = Calendar.getInstance(TimeZone.getTimeZone("UTC"))
        cal.timeInMillis = nowMs
        val wd = cal.get(Calendar.DAY_OF_WEEK) // Sun=1 … Sat=7
        val hour = cal.get(Calendar.HOUR_OF_DAY)
        return when (wd) {
            Calendar.SATURDAY -> false
            Calendar.SUNDAY -> hour >= 22
            Calendar.FRIDAY -> hour < 21
            else -> true
        }
    }

    /**
     * @return null if uploads may continue; message if should pause.
     */
    fun pauseUploadMessage(symbol: String?): String? {
        if (isAlwaysOpen(symbol)) return null
        if (fxSessionOpenUtc()) return null
        val s = normalize(symbol).ifBlank { "this FX/metal pair" }
        return "Market closed for $s (weekend break). Crypto/volatility can still run. Uploads paused until session reopens."
    }
}

package com.aegis.mobile.data

/**
 * AEGIS instrument catalog for Settings dropdown.
 *
 * GOOD: Stage 2 research-qualified (RSI9 SHORT transfer and/or Native LONG transfer).
 * NOT GOOD: not transfer-qualified for autonomous research path (shown for visibility).
 *
 * Server remains source of truth for router_status / tradeable flags.
 */
object AegisInstruments {
    /** Research-eligible pairs (RSI9 SHORT + Native LONG transfer set). */
    val GOOD: List<String> = listOf(
        "AUDUSD",
        "EURCHF",
        "EURGBP",
        "EURJPY",
        "EURUSD",
        "GBPJPY",
        "GBPNZD",
        "GBPUSD",
        "NZDCHF",
        "NZDJPY",
        "USDCAD",
        "USDCHF",
    )

    val NOT_GOOD: List<String> = listOf(
        "NZDUSD",
        "USDJPY",
        "GBPAUD",
        "BTCUSD",
        "ETHUSD",
    )

    val ALL_LABELS: List<String> = GOOD.map { "$it  · Good" } +
        NOT_GOOD.map { "$it  · Not Good (research)" }

    val ALL: List<String> = GOOD + NOT_GOOD

    fun isGood(symbol: String?): Boolean {
        if (symbol.isNullOrBlank()) return false
        return GOOD.any { it.equals(symbol.trim(), ignoreCase = true) }
    }

    fun indexOfSymbol(symbol: String?): Int {
        if (symbol.isNullOrBlank()) return 0
        val u = symbol.trim().uppercase()
        val i = ALL.indexOfFirst { it.equals(u, ignoreCase = true) }
        return if (i >= 0) i else 0
    }

    fun symbolFromLabel(label: String): String =
        label.substringBefore("·").trim().uppercase()
}

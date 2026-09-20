package com.aegis.mobile.data

/**
 * AEGIS instrument catalog for Settings dropdown.
 *
 * GOOD / research-eligible: non-V2OPT rulebooks (V31/V35/V53.6).
 * NOT GOOD (shown but labeled): V2-OPT-only pairs — insufficient gates
 * (not val_n>300 / PF>1.6 / 6-block); demo/live path disabled on server.
 */
object AegisInstruments {
    /** Research-eligible / "Good" pairs (V2-OPT removed). */
    val GOOD: List<String> = listOf(
        "GBPUSD",
        "AUDUSD",
        "USDCHF",
        "NZDUSD",
        "EURCHF",
        "EURGBP",
        "GBPJPY",
        "GBPNZD",
        "NZDCHF",
        "NZDJPY",
        "USDCAD",
    )

    /**
     * V2-OPT-only — server router_status=TRADING_DISABLED.
     * Kept in list for visibility; not selectable as a "Good" trade pair.
     */
    val NOT_GOOD: List<String> = listOf(
        "EURUSD",
        "USDJPY",
        "EURJPY",
        "GBPAUD",
    )

    /** Display labels for spinner (Good first, then blocked). */
    val ALL_LABELS: List<String> = GOOD.map { "$it  · Good" } +
        NOT_GOOD.map { "$it  · Not Good (V2-OPT only)" }

    /** Maps spinner index → symbol. */
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

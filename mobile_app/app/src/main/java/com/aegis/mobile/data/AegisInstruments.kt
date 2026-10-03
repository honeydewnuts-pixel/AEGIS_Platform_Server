package com.aegis.mobile.data

/**
 * AEGIS instrument catalog for Settings dropdown (display labels only).
 *
 * Source of truth for execution is the server registry:
 *   GET /api/registry/pairs
 *
 * GOOD = research-eligible on server (V53.6 / RSI9 transfer / native discovery).
 * NOT GOOD = no qualified research rulebook (kept visible for operators).
 *
 * Updated 2026-10-03 to match V40 registry after RSI9 + native Stage 2.
 */
object AegisInstruments {
    /** Research-eligible / "Good" pairs (server router RESEARCH_ELIGIBLE). */
    val GOOD: List<String> = listOf(
        // V53.6 short baseline + RSI9 SHORT transfer
        "GBPUSD",
        "AUDUSD",
        "USDCHF",
        "NZDUSD",   // V53.6 only (no RSI9 rulebook; still research-eligible)
        "EURCHF",
        "EURGBP",
        "GBPJPY",
        "GBPNZD",
        "NZDCHF",
        "NZDJPY",
        "USDCAD",
        // RSI9 SHORT transfer (were V2-OPT-only before Stage 2 registry merge)
        "EURUSD",
        "EURJPY",
        // Native discovery LONG (Stage 2)
        "USDJPY",
        // RSI9 crypto transfer
        "BTCUSD",
        "ETHUSD",
        // Native discovery indices / commodities (research)
        "GER40",
        "UK100",
        "US100",
        "UKOIL",
        "XAGUSD",
    )

    /**
     * No qualified research rulebook for demo/live autonomous path.
     * Still listed so operators can see status; not treated as Good.
     */
    val NOT_GOOD: List<String> = listOf(
        "GBPAUD",
        "XAUUSD",
        "US500",
        "USOIL",
    )

    /** Display labels for spinner (Good first, then blocked). */
    val ALL_LABELS: List<String> = GOOD.map { "$it  · Good" } +
        NOT_GOOD.map { "$it  · Not Good" }

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

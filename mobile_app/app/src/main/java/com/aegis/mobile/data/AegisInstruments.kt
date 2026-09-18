package com.aegis.mobile.data

/**
 * AEGIS tradeable / research instrument catalog for Settings dropdown.
 * Includes forex from V40/V53.6/V2-OPT registries plus non-forex discovery set.
 * Selection is stored as MT5 chart symbol; server router maps instrument → rulebook.
 */
object AegisInstruments {
    /** Display order: majors, crosses, metals, indices, energy, crypto, synthetics */
    val ALL: List<String> = listOf(
        // Majors
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "USDCHF",
        "USDCAD",
        "AUDUSD",
        "NZDUSD",
        // Crosses
        "EURGBP",
        "EURJPY",
        "EURCHF",
        "GBPJPY",
        "GBPAUD",
        "GBPNZD",
        "AUDJPY",
        "NZDJPY",
        "NZDCHF",
        // Metals
        "XAUUSD",
        "XAGUSD",
        // Indices
        "NAS100",
        "US500",
        "INDEX_MID2K",
        // Energy
        "BRENT",
        // Crypto / synthetic (research)
        "BTCUSD",
        "VOL100",
    )

    fun indexOfSymbol(symbol: String?): Int {
        if (symbol.isNullOrBlank()) return 0
        val u = symbol.trim().uppercase()
        val i = ALL.indexOfFirst { it.equals(u, ignoreCase = true) }
        return if (i >= 0) i else 0
    }
}

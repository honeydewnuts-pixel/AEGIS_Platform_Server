package com.aegis.mobile.models

/**
 * Response from POST /aegis/analyze.
 * Unknown JSON fields are ignored by Gson. Defaults keep parsing resilient.
 */
data class AnalysisResponse(
    val signal: String = "HOLD",
    val confidence: Double = 0.0,
    val details: String = "",
    val timestamp: Long = 0L,
    val rule_name: String? = null,
    val reason: String? = null,
    val pair: String? = null,
    val instrument: String? = null,
    val timeframe: String? = null,
    val frames_in_history: Int? = null,
    val contraction: Int? = null,
    val expansion: Int? = null,
    val neural_confidence: Double? = null,
    val neural_mode: String? = null,
    val neural_signal: String? = null,
    val latency_ms: Double? = null,
    val executed: Boolean? = null,
    val execution_status: String? = null,
    val engine_tier: String? = null,
) {
    /** UI-friendly confidence 0..1 or 0..100 normalized to 0..1 */
    fun confidence01(): Float {
        val c = confidence
        return when {
            c > 1.0 -> (c / 100.0).toFloat().coerceIn(0f, 1f)
            else -> c.toFloat().coerceIn(0f, 1f)
        }
    }
}

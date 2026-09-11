package com.aegis.mobile.models

/**
 * Response from POST /aegis/analyze.
 * Optional fields are filled when the V46 brain returns them.
 */
data class AnalysisResponse(
    val signal: String = "HOLD",
    val confidence: Float = 0f,
    val details: String = "",
    val timestamp: Long = 0L,
    val rule_name: String? = null,
    val reason: String? = null,
    val pair: String? = null,
    val instrument: String? = null,
    val timeframe: String? = null,
    val contraction: Int? = null,
    val expansion: Int? = null,
    val neural_confidence: Float? = null,
    val neural_mode: String? = null,
    val executed: Boolean? = null,
    val execution_status: String? = null,
)

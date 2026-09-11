package com.aegis.mobile.models

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
    val frames_in_history: Int? = null,
    val contraction: Int? = null,
    val expansion: Int? = null,
    val neural_confidence: Float? = null,
    val neural_mode: String? = null,
    val neural_signal: String? = null,
    val executed: Boolean? = null,
    val execution_status: String? = null,
)

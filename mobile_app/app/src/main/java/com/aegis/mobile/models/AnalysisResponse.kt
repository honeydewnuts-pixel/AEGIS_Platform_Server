package com.aegis.mobile.models

data class AnalysisResponse(
    val signal: String,      // "BUY", "SELL", "HOLD"
    val confidence: Float,   // 0.0 to 1.0
    val details: String,     // "RSI=30, MACD Bullish"
    val timestamp: Long      // when brain analyzed it
)

package com.aegis.mobile.data

import androidx.lifecycle.MutableLiveData

/**
 * Lightweight, observable health state for the capture loop. Updated by
 * ScreenCaptureService on every cycle; read by MainActivity (to show
 * live status) and by the heartbeat sender (to report to the backend).
 */
object HealthStatus {
    val lastCaptureTimeMs = MutableLiveData<Long>(0L)
    val lastCaptureSucceeded = MutableLiveData<Boolean>(true)
    val consecutiveFailures = MutableLiveData<Int>(0)
    val captureCount = MutableLiveData<Long>(0L)
    val mediaProjectionActive = MutableLiveData<Boolean>(false)
    val pendingCacheCount = MutableLiveData<Int>(0)

    fun recordCaptureSuccess() {
        lastCaptureTimeMs.postValue(System.currentTimeMillis())
        lastCaptureSucceeded.postValue(true)
        consecutiveFailures.postValue(0)
        captureCount.postValue((captureCount.value ?: 0L) + 1)
    }

    fun recordCaptureFailure() {
        lastCaptureSucceeded.postValue(false)
        consecutiveFailures.postValue((consecutiveFailures.value ?: 0) + 1)
    }
}

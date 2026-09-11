package com.aegis.mobile.network

/**
 * Pure upload policy used by the capture service.
 *
 * A screenshot is a first-class AEGIS input and must not depend on MT5 being
 * connected. The optional symbol is only attached when the MT5 worker is
 * confirmed healthy. HTTP 4xx errors are treated as permanent request/config
 * errors; transient transport/server failures may be retried and queued.
 */
object UploadPolicy {
    fun shouldSendSymbol(configuredSymbol: String, accountId: String, workerConnected: Boolean): Boolean =
        configuredSymbol.isNotBlank() && accountId.isNotBlank() && workerConnected

    fun isRetryableHttp(code: Int): Boolean =
        code == 408 || code == 425 || code == 429 || code in 500..599
}

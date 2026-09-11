package com.aegis.mobile.network

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UploadPolicyTest {
    @Test fun symbol_requires_worker() {
        assertTrue(UploadPolicy.shouldSendSymbol("GBPUSD", "ACC-1", true))
        assertFalse(UploadPolicy.shouldSendSymbol("GBPUSD", "ACC-1", false))
        assertFalse(UploadPolicy.shouldSendSymbol("", "ACC-1", true))
        assertFalse(UploadPolicy.shouldSendSymbol("GBPUSD", "", true))
    }

    @Test fun only_transient_http_failures_are_retryable() {
        assertTrue(UploadPolicy.isRetryableHttp(408))
        assertTrue(UploadPolicy.isRetryableHttp(429))
        assertTrue(UploadPolicy.isRetryableHttp(500))
        assertTrue(UploadPolicy.isRetryableHttp(503))
        assertFalse(UploadPolicy.isRetryableHttp(400))
        assertFalse(UploadPolicy.isRetryableHttp(401))
        assertFalse(UploadPolicy.isRetryableHttp(403))
        assertFalse(UploadPolicy.isRetryableHttp(413))
        assertFalse(UploadPolicy.isRetryableHttp(422))
    }
}

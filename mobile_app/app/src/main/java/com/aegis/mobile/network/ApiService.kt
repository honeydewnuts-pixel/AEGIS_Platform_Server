package com.aegis.mobile.network

import com.aegis.mobile.models.AnalysisResponse
import com.aegis.mobile.models.CaptureRoi
import com.aegis.mobile.models.HeartbeatRequest
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part

interface ApiService {

    @Multipart
    @POST("/aegis/analyze")
    suspend fun analyzeScreenshot(
        @Part image: MultipartBody.Part,
        // Backend now keeps a per-account rolling history to evaluate multi-frame
        // rules (crossings, divergence). Without this field, the backend can't
        // tell which account's history this screenshot belongs to.
        @Part("account_id") accountId: RequestBody,
        // Original capture time, not upload time - lets cached/replayed
        // screenshots (see ScreenshotCacheManager) sort correctly into the
        // backend's history even if sent late after a network outage.
        @Part("captured_at_ms") capturedAtMs: RequestBody
    ): Response<AnalysisResponse>

    @POST("/api/devices/heartbeat")
    suspend fun sendHeartbeat(@Body heartbeat: HeartbeatRequest): Response<Unit>

    @GET("/api/config/capture-roi")
    suspend fun getCaptureRoi(): Response<CaptureRoi>
}

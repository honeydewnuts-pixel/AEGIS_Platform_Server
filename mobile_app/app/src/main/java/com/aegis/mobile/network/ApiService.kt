package com.aegis.mobile.network

import com.aegis.mobile.models.AnalysisResponse
import com.aegis.mobile.models.CaptureRoi
import com.aegis.mobile.models.HeartbeatRequest
import com.aegis.mobile.models.Mt5ConnectRequest
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {

    @Multipart
    @POST("/aegis/analyze")
    suspend fun analyzeScreenshot(
        @Part image: MultipartBody.Part,
        @Part("account_id") accountId: RequestBody,
        @Part("captured_at_ms") capturedAtMs: RequestBody,
        @Part("symbol") symbol: RequestBody?,
        @Part("timeframe") timeframe: RequestBody? = null,
        @Part("candle_ts_ms") candleTsMs: RequestBody? = null,
        @Part("device_ts_ms") deviceTsMs: RequestBody? = null,
        @Part("sequence") sequence: RequestBody? = null
    ): Response<AnalysisResponse>

    @POST("/api/devices/heartbeat")
    suspend fun sendHeartbeat(@Body heartbeat: HeartbeatRequest): Response<Unit>

    @GET("/api/config/capture-roi")
    suspend fun getCaptureRoi(): Response<CaptureRoi>

    @POST("/api/trading/connect")
    suspend fun connectMt5(@Body body: Mt5ConnectRequest): Response<Map<String, Any>>

    @POST("/api/trading/disconnect/{accountId}")
    suspend fun disconnectMt5(@Path("accountId") accountId: String): Response<Map<String, Any>>

    @GET("/api/trading/health")
    suspend fun tradingHealth(@Query("account_id") accountId: String): Response<Map<String, Any>>

    @GET("/")
    suspend fun pingRoot(): Response<Map<String, Any>>

    @GET("/health")
    suspend fun pingHealth(): Response<Map<String, Any>>

    @POST("/api/devices/register")
    suspend fun registerDevice(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<Map<String, Any>>

    @GET("/api/devices/me")
    suspend fun deviceMe(): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/templates/active")
    suspend fun getActiveTemplates(): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/registry/active")
    suspend fun getRegistryActive(): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/registry/pairs")
    suspend fun getRegistryPairs(
        @Query("tradeable_only") tradeableOnly: Boolean = false
    ): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/support/report")
    suspend fun reportIssue(@Body body: Map<String, @JvmSuppressWildcards Any?>): Response<Map<String, Any>>

    @GET("/api/copier/catalog")
    suspend fun copierCatalog(): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/copier/status/{accountId}")
    suspend fun copierStatus(@Path("accountId") accountId: String): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/copier/activate")
    suspend fun copierActivate(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/copier/slaves")
    suspend fun copierAddSlave(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/copier/slaves/toggle")
    suspend fun copierToggleSlave(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<Map<String, @JvmSuppressWildcards Any>>

    @retrofit2.http.DELETE("/api/copier/slaves/{slaveId}")
    suspend fun copierRemoveSlave(
        @Path("slaveId") slaveId: Int,
        @Query("account_id") accountId: String
    ): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/account/risk_preset")
    suspend fun setRiskPreset(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/notifications")
    suspend fun listNotifications(
        @Query("account_id") accountId: String,
        @Query("limit") limit: Int = 50,
        @Query("unread_only") unreadOnly: Boolean = false
    ): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/notifications/read-all")
    suspend fun markAllNotificationsRead(
        @Query("account_id") accountId: String
    ): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/notifications/{id}/read")
    suspend fun markNotificationRead(
        @Path("id") id: Int,
        @Query("account_id") accountId: String
    ): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/notifications/unread-count")
    suspend fun notificationUnreadCount(
        @Query("account_id") accountId: String
    ): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/executor/executions/recent")
    suspend fun recentExecutions(
        @Query("account_id") accountId: String,
        @Query("limit") limit: Int = 20
    ): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/portfolio/equity")
    suspend fun setPortfolioEquity(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/portfolio/risk-tolerance")
    suspend fun setRiskTolerance(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/portfolio/trading-mode")
    suspend fun setTradingMode(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/portfolio/status")
    suspend fun getPortfolioStatus(@Query("account_id") accountId: String): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/account/status")
    suspend fun getAccountStatus(@Query("account_id") accountId: String): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/community/rooms")
    suspend fun communityRooms(): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/community/rooms/{roomId}/messages")
    suspend fun communityMessages(
        @Path("roomId") roomId: String,
        @Query("limit") limit: Int = 50,
        @Query("after_id") afterId: Int? = null
    ): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/community/rooms/{roomId}/messages")
    suspend fun communityPost(
        @Path("roomId") roomId: String,
        @Body body: Map<String, @JvmSuppressWildcards Any>
    ): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/ai/history")
    suspend fun aiHistory(
        @Query("account_id") accountId: String,
        @Query("limit") limit: Int = 40
    ): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/ai/chat")
    suspend fun aiChat(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/community/profile")
    suspend fun communityProfile(@Query("account_id") accountId: String): Response<Map<String, @JvmSuppressWildcards Any>>

    @PUT("/api/community/profile")
    suspend fun communitySetProfile(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/community/presence")
    suspend fun communityPresence(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/community/online")
    suspend fun communityOnline(): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/community/dm/open")
    suspend fun communityDmOpen(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/community/dm/threads")
    suspend fun communityDmThreads(@Query("account_id") accountId: String): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("/api/community/dm/{threadId}/messages")
    suspend fun communityDmMessages(
        @Path("threadId") threadId: String,
        @Query("account_id") accountId: String,
        @Query("limit") limit: Int = 50,
        @Query("after_id") afterId: Int? = null
    ): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/community/dm/{threadId}/messages")
    suspend fun communityDmPost(
        @Path("threadId") threadId: String,
        @Body body: Map<String, @JvmSuppressWildcards Any>
    ): Response<Map<String, @JvmSuppressWildcards Any>>

    @POST("/api/community/report")
    suspend fun communityReport(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<Map<String, @JvmSuppressWildcards Any>>

    @Multipart
    @POST("/api/community/media")
    suspend fun communityUploadMedia(
        @Part("account_id") accountId: RequestBody,
        @Part file: MultipartBody.Part
    ): Response<Map<String, @JvmSuppressWildcards Any>>
}


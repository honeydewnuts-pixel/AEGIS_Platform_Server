package com.aegis.mobile.capture

import android.Manifest
import android.annotation.SuppressLint
import android.app.*
import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiManager
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.BatteryManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.aegis.mobile.R
import com.aegis.mobile.data.HealthStatus
import androidx.datastore.preferences.core.edit
import com.aegis.mobile.data.PrefKeys
import com.aegis.mobile.data.SignalRepository
import com.aegis.mobile.data.dataStore
import com.aegis.mobile.models.AnalysisResponse
import org.json.JSONObject
import com.aegis.mobile.models.HeartbeatRequest
import com.aegis.mobile.network.RetrofitClient
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.io.FileOutputStream

class ScreenCaptureService : Service() {

    private lateinit var mediaProjectionManager: MediaProjectionManager
    private var mediaProjection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var imageReader: ImageReader? = null
    private val handler = Handler(Looper.getMainLooper())
    private val scope = CoroutineScope(Dispatchers.IO)
    private lateinit var apiService: com.aegis.mobile.network.ApiService
    private lateinit var powerManager: PowerManager
    private var screenWakeLock: PowerManager.WakeLock? = null
    private var briefCpuWakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null
    private var connectivityManager: ConnectivityManager? = null
    private var networkCallback: ConnectivityManager.NetworkCallback? = null
    @Volatile private var keepNetworkAlive: Boolean = true
    @Volatile private var captureIntervalMs: Long = DEFAULT_CAPTURE_INTERVAL_MS
    private lateinit var cacheManager: ScreenshotCacheManager

    // Defaults to "no crop" (send the full frame) until a real ROI is
    // fetched - safe fallback if the config endpoint is unreachable, since
    // sending too much is a bandwidth cost, sending too little could crop
    // off real chart data the brain needs.
    @Volatile private var captureTopPercent: Float = 0.06f
    @Volatile private var captureBottomPercent: Float = 0.88f

    companion object {
        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"
        const val ACTION_STOP = "com.aegis.mobile.STOP_CAPTURE"
        const val ACTION_START = "com.aegis.mobile.START_CAPTURE"
        private const val NOTIF_ID = 1001
        private const val DEFAULT_CAPTURE_INTERVAL_MS = 5000L
        private const val HEARTBEAT_INTERVAL = 60000L   // 1 minute - independent of the capture loop
        private const val CACHE_DRAIN_INTERVAL = 8000L // how often we try to flush the offline backlog
        private const val MAX_DRAIN_PER_CYCLE = 5        // catch up gradually, not in one burst, after reconnecting
        private const val ROI_REFRESH_INTERVAL = 6 * 60 * 60 * 1000L  // 6 hours - config rarely changes
        private const val WAKELOCK_TIMEOUT_MS = 10000L  // safety cap so a stuck capture can't hold the lock forever
    }

    override fun onCreate() {
        super.onCreate()
        apiService = RetrofitClient.getApiService(this)
        mediaProjectionManager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        cacheManager = ScreenshotCacheManager(this)
        startForeground(NOTIF_ID, buildNotification("Starting..."))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Explicit stop from the UI — do not restart.
        if (intent?.action == ACTION_STOP) {
            Log.i("AEGIS", "Stop capture requested")
            stopCaptureSession()
            stopFloatingHud()
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }

        val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
        val resultData = intent?.getParcelableExtra<Intent>(EXTRA_RESULT_DATA)
        if (resultData == null || resultCode == 0) {
            // System may restart a sticky service without the MediaProjection token.
            // We cannot capture without a fresh user grant — shut down cleanly.
            Log.w("AEGIS", "No MediaProjection token; not restarting capture")
            HealthStatus.mediaProjectionActive.postValue(false)
            stopSelf()
            return START_NOT_STICKY
        }

        // If already running, ignore duplicate start intents.
        if (mediaProjection != null && HealthStatus.mediaProjectionActive.value == true) {
            Log.i("AEGIS", "Capture already active")
            return START_NOT_STICKY
        }

        mediaProjection = mediaProjectionManager.getMediaProjection(resultCode, resultData)
        mediaProjection?.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() {
                Log.w("AEGIS", "MediaProjection stopped by system/user")
                handler.post {
                    stopCaptureSession()
                    stopForeground(STOP_FOREGROUND_REMOVE)
                    stopSelf()
                }
            }
        }, handler)

        HealthStatus.mediaProjectionActive.postValue(true)
        setupVirtualDisplay()
        scope.launch { refreshCaptureRoi() }
        handler.removeCallbacks(captureRunnable)
        handler.removeCallbacks(heartbeatRunnable)
        handler.removeCallbacks(cacheDrainRunnable)
        handler.removeCallbacks(roiRefreshRunnable)
        scope.launch { loadCaptureInterval() }
        handler.post(captureRunnable) // first frame immediately, then interval
        handler.postDelayed(heartbeatRunnable, HEARTBEAT_INTERVAL)
        handler.postDelayed(cacheDrainRunnable, CACHE_DRAIN_INTERVAL)
        handler.postDelayed(roiRefreshRunnable, ROI_REFRESH_INTERVAL)
        updateNotification("Capturing MT5 chart region")
        acquireServiceWakeLock()
        scope.launch { prepareNetworkKeepAlive() }
        // NOT sticky: prevents auto-restart without a valid projection token (which
        // made Stop appear to "restart" capture and left the UI inconsistent).
        return START_NOT_STICKY
    }

    private fun acquireServiceWakeLock() {
        try {
            // Held for the whole capture session — do NOT release per frame
            if (screenWakeLock == null) {
                @Suppress("DEPRECATION")
                screenWakeLock = powerManager.newWakeLock(
                    PowerManager.SCREEN_BRIGHT_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP,
                    "AEGIS::ScreenOnCapture"
                )
                screenWakeLock?.setReferenceCounted(false)
            }
            if (screenWakeLock?.isHeld != true) {
                @Suppress("DEPRECATION")
                screenWakeLock?.acquire()
            }
        } catch (_: Exception) {
        }
    }

    private fun stopCaptureSession() {
        handler.removeCallbacks(captureRunnable)
        handler.removeCallbacks(heartbeatRunnable)
        handler.removeCallbacks(cacheDrainRunnable)
        handler.removeCallbacks(roiRefreshRunnable)
        try { virtualDisplay?.release() } catch (_: Exception) {}
        virtualDisplay = null
        try { mediaProjection?.stop() } catch (_: Exception) {}
        mediaProjection = null
        try { imageReader?.close() } catch (_: Exception) {}
        imageReader = null
        if (screenWakeLock?.isHeld == true) {
            try { screenWakeLock?.release() } catch (_: Exception) {}
        }
        screenWakeLock = null
        releaseNetworkKeepAlive()
        if (briefCpuWakeLock?.isHeld == true) {
            try { briefCpuWakeLock?.release() } catch (_: Exception) {}
        }
        briefCpuWakeLock = null
        HealthStatus.mediaProjectionActive.postValue(false)
        Log.i("AEGIS", "Capture session cleaned up")
    }

    private fun setupVirtualDisplay() {
        val metrics = resources.displayMetrics
        imageReader = ImageReader.newInstance(metrics.widthPixels, metrics.heightPixels, PixelFormat.RGBA_8888, 2)

        virtualDisplay = mediaProjection?.createVirtualDisplay(
            "AEGIS_ScreenCapture",
            metrics.widthPixels, metrics.heightPixels, metrics.densityDpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            imageReader?.surface, null, null
        )
    }

    private val captureRunnable = object : Runnable {
        override fun run() {
            captureAndSend()
            handler.postDelayed(this, captureIntervalMs)
        }
    }

    private val heartbeatRunnable = object : Runnable {
        override fun run() {
            scope.launch { sendHeartbeat() }
            handler.postDelayed(this, HEARTBEAT_INTERVAL)
        }
    }

    private val cacheDrainRunnable = object : Runnable {
        override fun run() {
            scope.launch { drainCache() }
            handler.postDelayed(this, CACHE_DRAIN_INTERVAL)
        }
    }

    private val roiRefreshRunnable = object : Runnable {
        override fun run() {
            scope.launch { refreshCaptureRoi() }
            handler.postDelayed(this, ROI_REFRESH_INTERVAL)
        }
    }

    /**
     * Fetches the capture crop bounds from the backend (single source of
     * truth: colors_config.json's roi section) rather than hardcoding a
     * copy in the app - so tightening the crop later is a config change,
     * not an app update. Failure here just keeps whatever bounds were
     * already in memory (defaults to "no crop" on first-ever failure) -
     * capture must never block or fail because this fetch failed.
     */
    private suspend fun refreshCaptureRoi() {
        try {
            val response = apiService.getCaptureRoi()
            if (response.isSuccessful) {
                response.body()?.let {
                    captureTopPercent = it.captureTopPercent
                    captureBottomPercent = it.captureBottomPercent
                    Log.d("AEGIS", "Capture ROI updated: $captureTopPercent - $captureBottomPercent")
                }
            }
        } catch (e: Exception) {
            Log.w("AEGIS", "Could not refresh capture ROI, keeping previous bounds: ${e.message}")
        }
    }

    /**
     * Sends cached (previously failed) screenshots oldest-first, stopping
     * as soon as one fails (still offline - try again next cycle) rather
     * than burning through retries against a backend that's still down.
     * Drains a bounded batch per cycle so a large backlog catches up
     * gradually instead of hammering the network the instant it returns.
     */
    private suspend fun drainCache() {
        val pending = cacheManager.listPendingOldestFirst()
        if (pending.isEmpty()) return

        for (file in pending.take(MAX_DRAIN_PER_CYCLE)) {
            val parsed = cacheManager.parse(file)
            if (parsed == null) {
                cacheManager.remove(file)  // malformed filename - can't recover this one, drop it
                continue
            }
            val (capturedAtMs, accountId, cachedSymbol) = parsed
            val symbol = cachedSymbol.ifBlank { applicationContext.dataStore.data.first()[PrefKeys.MT5_SYMBOL]?.trim().orEmpty() }
            val sent = trySend(file, accountId, capturedAtMs, symbol)
            if (sent) {
                cacheManager.remove(file)
                HealthStatus.pendingCacheCount.postValue(cacheManager.pendingCount())
            } else {
                break  // still offline - stop draining, try again next cycle
            }
        }
    }

    /**
     * Held only for the duration of one capture-and-encode cycle, then released
     * immediately - not a continuous lock. This just protects against the CPU
     * suspending mid-capture on aggressive power-saving devices; it deliberately
     * does not try to keep the whole app "awake" between cycles, since that would
     * defeat the point of a wakelock and drain the battery for no benefit.
     */
    private fun withBriefWakeLock(block: () -> Unit) {
        // Separate from screenWakeLock so per-frame release cannot turn the screen off
        if (briefCpuWakeLock == null) {
            briefCpuWakeLock = powerManager.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK,
                "AEGIS::CaptureCpu"
            )
            briefCpuWakeLock?.setReferenceCounted(false)
        }
        try {
            if (briefCpuWakeLock?.isHeld != true) {
                briefCpuWakeLock?.acquire(WAKELOCK_TIMEOUT_MS)
            }
            // Re-assert screen lock each cycle in case OEM dropped it
            acquireServiceWakeLock()
            block()
        } finally {
            try {
                if (briefCpuWakeLock?.isHeld == true) briefCpuWakeLock?.release()
            } catch (_: Exception) {
            }
        }
    }

    private fun captureAndSend() {
        val mt5Fg = com.aegis.mobile.automation.Mt5AccessibilityService.isMt5Foreground
        HealthStatus.mt5Foreground.postValue(mt5Fg)
        val frames = HealthStatus.localFrameCount.value ?: 0L
        val ups = HealthStatus.captureCount.value ?: 0L
        updateNotification(
            if (mt5Fg) "Capturing MT5 · frames $frames · uploads $ups"
            else "Capturing · frames $frames · uploads $ups — keep MT5 visible"
        )

        // Hide operator overlay so it is not painted into the frame sent to the brain.
        try {
            startService(Intent(this, com.aegis.mobile.ui.FloatingHudService::class.java).apply {
                action = com.aegis.mobile.ui.FloatingHudService.ACTION_CAPTURE_HIDE
            })
            Thread.sleep(40)
        } catch (_: Exception) {
        }

        withBriefWakeLock {
            val image = imageReader?.acquireLatestImage()
            if (image == null) {
                HealthStatus.recordCaptureFailure(networkError = false)
                return@withBriefWakeLock
            }
            val capturedAtMs = System.currentTimeMillis()
            val planes = image.planes
            val buffer = planes[0].buffer
            val pixelStride = planes[0].pixelStride
            val rowStride = planes[0].rowStride
            val rowPadding = rowStride - pixelStride * image.width

            val bitmap = Bitmap.createBitmap(
                image.width + rowPadding / pixelStride,
                image.height,
                Bitmap.Config.ARGB_8888
            )
            bitmap.copyPixelsFromBuffer(buffer)
            image.close()

            val croppedBitmap = applyRoiCrop(bitmap)
            HealthStatus.publishPreview(croppedBitmap)

            scope.launch {
                val accountId = resolveAccountId()
                val tempFile = File(cacheDir, "live_capture_tmp.jpg")
                FileOutputStream(tempFile).use { out ->
                    croppedBitmap.compress(Bitmap.CompressFormat.JPEG, 80, out)
                }

                val symbol = applicationContext.dataStore.data.first()[PrefKeys.MT5_SYMBOL]?.trim().orEmpty()
                val sent = trySend(tempFile, accountId, capturedAtMs, symbol)
                if (!sent) {
                    // Backend unreachable - queue it instead of losing it. The
                    // drain loop will retry this (in correct chronological
                    // order relative to other cached frames) once connectivity
                    // returns.
                    cacheManager.cache(croppedBitmap, capturedAtMs, accountId, symbol)
                    HealthStatus.pendingCacheCount.postValue(cacheManager.pendingCount())
                    updateNotification("Offline - ${cacheManager.pendingCount()} screenshots queued")
                }
                tempFile.delete()
            }
        }
        try {
            startService(Intent(this, com.aegis.mobile.ui.FloatingHudService::class.java).apply {
                action = com.aegis.mobile.ui.FloatingHudService.ACTION_CAPTURE_SHOW
            })
        } catch (_: Exception) {
        }
    }

    /**
     * Crops out anything above captureTopPercent or below captureBottomPercent
     * (status bar, MT5 toolbar chrome, nav bar - whatever isn't part of the
     * price/indicator panels). Currently a no-op with the default 0.0/1.0
     * bounds until colors_config.json's roi values are tightened based on a
     * real device measurement - see refreshCaptureRoi() and
     * app/api/config_router.py on the backend for where these come from.
     */
    private fun applyRoiCrop(bitmap: Bitmap): Bitmap {
        if (captureTopPercent <= 0.0f && captureBottomPercent >= 1.0f) {
            return bitmap  // no-op fast path - avoids an unnecessary copy when there's nothing to crop
        }
        val top = (bitmap.height * captureTopPercent).toInt().coerceIn(0, bitmap.height - 1)
        val bottom = (bitmap.height * captureBottomPercent).toInt().coerceIn(top + 1, bitmap.height)
        return Bitmap.createBitmap(bitmap, 0, top, bitmap.width, bottom - top)
    }

    /**
     * Shared send path for both live captures and replayed cached ones.
     * One quick retry on transient failures (Render cold start, brief
     * network blip). Persistent errors fall through to the offline cache.
     */
    private suspend fun trySend(file: File, accountId: String, capturedAtMs: Long, symbol: String): Boolean {
        repeat(2) { attempt ->
            val ok = trySendOnce(file, accountId, capturedAtMs, symbol)
            if (ok) return true
            if (attempt == 0) {
                delay(2_500)
            }
        }
        return false
    }

    private suspend fun trySendOnce(file: File, accountId: String, capturedAtMs: Long, symbol: String): Boolean {
        val t0 = System.currentTimeMillis()
        return try {
            // Fresh client picks up Settings; same simple stack as working builds
            apiService = RetrofitClient.getApiService(applicationContext)
            val requestFile = file.asRequestBody("image/jpeg".toMediaTypeOrNull())
            val body = MultipartBody.Part.createFormData("image", "capture.jpg", requestFile)
            val accountIdBody: RequestBody = accountId.toRequestBody("text/plain".toMediaTypeOrNull())
            val capturedAtBody: RequestBody = capturedAtMs.toString().toRequestBody("text/plain".toMediaTypeOrNull())
            val symbolBody: RequestBody = symbol.toRequestBody("text/plain".toMediaTypeOrNull())

            val response = apiService.analyzeScreenshot(body, accountIdBody, capturedAtBody, symbolBody)
            val code = response.code()
            if (response.isSuccessful) {
                // Parse JSON manually so extra neural fields never fail the upload
                val raw = try { response.body()?.string().orEmpty() } catch (_: Exception) { "" }
                val result = parseAnalysisJson(raw)
                Log.d("AEGIS", "Brain Response HTTP $code: ${result.signal} conf=${result.confidence} rule=${result.rule_name}")
                SignalRepository.latestResult.postValue(result)
                SignalRepository.latestSignal.postValue(result.signal)
                HealthStatus.recordCaptureSuccess(httpCode = code, latencyMs = System.currentTimeMillis() - t0)
                val pending = cacheManager.pendingCount()
                val suffix = if (pending > 0) " ($pending queued)" else ""
                updateNotification("Last signal: ${result.signal} @ ${timeNow()}$suffix")
                true
            } else {
                val errBody = try {
                    response.errorBody()?.string()?.take(500)
                } catch (_: Exception) {
                    null
                }
                Log.e("AEGIS", "Brain Error: $code body=${errBody ?: "(empty)"}")
                HealthStatus.recordCaptureFailure(httpCode = code, networkError = false, latencyMs = System.currentTimeMillis() - t0)
                false
            }
        } catch (e: Exception) {
            Log.e("AEGIS", "Send failed: ${e.javaClass.simpleName}: ${e.message}")
            HealthStatus.recordCaptureFailure(httpCode = null, networkError = true, latencyMs = System.currentTimeMillis() - t0)
            false
        }
    }

    /** Lenient parse — never throws; HTTP 200 always counts as upload success. */
    private fun parseAnalysisJson(raw: String): AnalysisResponse {
        if (raw.isBlank()) {
            return AnalysisResponse(signal = "HOLD", details = "empty body")
        }
        return try {
            val o = JSONObject(raw)
            fun str(key: String): String? =
                if (o.has(key) && !o.isNull(key)) o.optString(key).takeIf { it.isNotBlank() } else null
            AnalysisResponse(
                signal = o.optString("signal", "HOLD").ifBlank { "HOLD" },
                confidence = o.optDouble("confidence", 0.0).toFloat(),
                details = o.optString("details", o.optString("reason", "")),
                timestamp = o.optLong("timestamp", 0L),
                rule_name = str("rule_name"),
                reason = str("reason"),
                pair = str("pair"),
                instrument = str("instrument"),
                timeframe = str("timeframe"),
                frames_in_history = if (o.has("frames_in_history")) o.optInt("frames_in_history") else null,
                neural_mode = str("neural_mode"),
                neural_signal = str("neural_signal"),
                neural_confidence = if (o.has("neural_score")) o.optDouble("neural_score").toFloat() else null,
                executed = if (o.has("executed")) o.optBoolean("executed") else null,
                execution_status = str("execution_status"),
            )
        } catch (e: Exception) {
            Log.w("AEGIS", "parseAnalysisJson soft-fail: ${e.message}")
            AnalysisResponse(signal = "HOLD", details = raw.take(200))
        }
    }

    private suspend fun prepareNetworkKeepAlive() {
        try {
            keepNetworkAlive = applicationContext.dataStore.data.first()[PrefKeys.KEEP_NETWORK_ALIVE] ?: true
        } catch (_: Exception) {
            keepNetworkAlive = true
        }
        if (!keepNetworkAlive) return
        try {
            val wifi = applicationContext.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            @Suppress("DEPRECATION")
            if (wifiLock == null) {
                wifiLock = wifi.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "AEGIS::WifiKeepAlive")
                wifiLock?.setReferenceCounted(false)
            }
            if (wifiLock?.isHeld != true) {
                wifiLock?.acquire()
                Log.i("AEGIS", "Wi‑Fi high-perf lock acquired")
            }
        } catch (e: Exception) {
            Log.w("AEGIS", "Wi‑Fi lock unavailable: ${e.message}")
        }
        try {
            connectivityManager = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val request = NetworkRequest.Builder()
                .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                .build()
            val cb = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    Log.i("AEGIS", "Network available — drain offline queue")
                    HealthStatus.backendReachable.postValue(true)
                    // Kick drain sooner than the normal interval
                    handler.removeCallbacks(cacheDrainRunnable)
                    handler.post(cacheDrainRunnable)
                }
                override fun onLost(network: Network) {
                    Log.w("AEGIS", "Network lost — will queue captures offline")
                    HealthStatus.backendReachable.postValue(false)
                }
            }
            networkCallback = cb
            connectivityManager?.registerNetworkCallback(request, cb)
        } catch (e: Exception) {
            Log.w("AEGIS", "Network callback failed: ${e.message}")
        }
    }

    private fun releaseNetworkKeepAlive() {
        try {
            networkCallback?.let { cb ->
                connectivityManager?.unregisterNetworkCallback(cb)
            }
        } catch (_: Exception) {
        }
        networkCallback = null
        try {
            if (wifiLock?.isHeld == true) wifiLock?.release()
        } catch (_: Exception) {
        }
        wifiLock = null
    }

    private suspend fun loadCaptureInterval() {
        try {
            val sec = applicationContext.dataStore.data.first()[PrefKeys.CAPTURE_INTERVAL_SEC]
                ?: com.aegis.mobile.data.DEFAULT_CAPTURE_INTERVAL_SEC
            captureIntervalMs = (sec.coerceIn(2, 120) * 1000L)
            Log.i("AEGIS", "Capture interval = ${captureIntervalMs}ms")
        } catch (e: Exception) {
            captureIntervalMs = DEFAULT_CAPTURE_INTERVAL_MS
        }
    }

    private suspend fun resolveAccountId(): String {
        var stored = applicationContext.dataStore.data.first()[PrefKeys.ACCOUNT_ID]?.takeIf { it.isNotBlank() }
        if (!stored.isNullOrBlank()) return stored
        // Ask the API which account this key belongs to
        try {
            val api = RetrofitClient.getApiService(applicationContext)
            val me = api.deviceMe()
            if (me.isSuccessful) {
                val id = me.body()?.get("account_id")?.toString()?.trim().orEmpty()
                if (id.isNotEmpty()) {
                    applicationContext.dataStore.edit { it[PrefKeys.ACCOUNT_ID] = id }
                    return id
                }
            }
        } catch (_: Exception) {
        }
        return ""
    }

    private suspend fun sendHeartbeat() {
        try {
            val batteryManager = getSystemService(Context.BATTERY_SERVICE) as BatteryManager
            val batteryPercent = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
            val isCharging = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_STATUS) ==
                BatteryManager.BATTERY_STATUS_CHARGING

            val exempt = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                powerManager.isIgnoringBatteryOptimizations(packageName)
            } else true

            val heartbeat = HeartbeatRequest(
                accountId = resolveAccountId(),
                batteryPercent = batteryPercent,
                isCharging = isCharging,
                lastCaptureTimeMs = HealthStatus.lastCaptureTimeMs.value ?: 0L,
                lastCaptureSucceeded = HealthStatus.lastCaptureSucceeded.value ?: true,
                consecutiveFailures = HealthStatus.consecutiveFailures.value ?: 0,
                captureCount = HealthStatus.captureCount.value ?: 0L,
                mediaProjectionActive = HealthStatus.mediaProjectionActive.value ?: false,
                batteryOptimizationExempt = exempt,
                cachedScreenshotCount = cacheManager.pendingCount(),
                appVersion = "3.0.0"
            )
            apiService.sendHeartbeat(heartbeat)
        } catch (e: Exception) {
            Log.e("AEGIS", "Heartbeat failed: ${e.message}")
        }
    }

    private fun timeNow(): String {
        val sdf = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault())
        return sdf.format(java.util.Date())
    }

    private fun buildNotification(status: String): Notification {
        val channel = NotificationChannel("aegis_service", "AEGIS Service", NotificationManager.IMPORTANCE_LOW)
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        return NotificationCompat.Builder(this, "aegis_service")
            .setContentTitle("AEGIS Active")
            .setContentText(status)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setOngoing(true)
            .build()
    }

    /**
     * On Android 13+ (TIRAMISU), posting a notification requires the runtime
     * POST_NOTIFICATIONS permission. This only guards the *ongoing status update*
     * notify() calls used to refresh the existing foreground notification's text
     * (e.g. "Last signal: BUY @ 10:02:31") - it does not affect startForeground()
     * in onCreate(), which the OS allows regardless so the foreground service
     * itself can still run even if the user never grants notification access.
     * If the permission isn't granted, we simply skip the update rather than
     * crash or spam SecurityExceptions - the service keeps working either way,
     * the user just won't see live status text in the notification shade.
     */
    @SuppressLint("NotificationPermission")
    private fun updateNotification(status: String) {
        val hasPermission = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
                PackageManager.PERMISSION_GRANTED

        if (hasPermission) {
            val manager = getSystemService(NotificationManager::class.java)
            manager.notify(NOTIF_ID, buildNotification(status))
        }
    }

    private fun stopFloatingHud() {
        try {
            val hide = Intent(this, com.aegis.mobile.ui.FloatingHudService::class.java).apply {
                action = com.aegis.mobile.ui.FloatingHudService.ACTION_HIDE
            }
            startService(hide)
            stopService(Intent(this, com.aegis.mobile.ui.FloatingHudService::class.java))
        } catch (_: Exception) {
        }
    }

    override fun onDestroy() {
        stopCaptureSession()
        stopFloatingHud()
        scope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}

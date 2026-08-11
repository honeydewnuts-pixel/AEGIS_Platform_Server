package com.aegis.mobile.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore

// Single shared DataStore instance for the whole app.
// Must be public (not private) so it can be used from SettingsActivity, RetrofitClient, etc.
val Context.dataStore by preferencesDataStore(name = "aegis_settings")

object PrefKeys {

    // Renamed from the old "server_ip" (which only ever stored a bare
    // LAN IP and forced RetrofitClient to hardcode "http://ip:5000/").
    // Render serves HTTPS on 443 with a real hostname, not an IP:port,
    // so this now stores a full base URL instead. SERVER_IP is kept as
    // a fallback read for anyone upgrading from a build that only had
    // a LAN IP saved - see RetrofitClient.resolveBaseUrl().
    val SERVER_URL = stringPreferencesKey("server_url")

    val SERVER_IP = stringPreferencesKey("server_ip")

    val ACCOUNT_ID = stringPreferencesKey("account_id")

    val API_KEY = stringPreferencesKey("api_key")

    // Safety controls (see MainActivity / Mt5AccessibilityService)
    val AUTO_EXECUTE =
        booleanPreferencesKey("auto_execute")

    // default OFF - require manual confirm
    val MIN_CONFIDENCE =
        stringPreferencesKey("min_confidence")
}

// Replace with your actual Render URL,
// e.g. "https://aegis-backend.onrender.com/"
const val DEFAULT_SERVER_URL =
    "https://your-app-name.onrender.com/"

const val DEFAULT_MIN_CONFIDENCE = 0.70f

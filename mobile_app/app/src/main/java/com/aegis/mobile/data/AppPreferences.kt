package com.aegis.mobile.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore

// Single shared DataStore instance for the whole app.
// Must be public (not private) so it can be used from SettingsActivity, RetrofitClient, etc.
val Context.dataStore by preferencesDataStore(name = "aegis_settings")

object PrefKeys {
    val SERVER_IP = stringPreferencesKey("server_ip")
    val ACCOUNT_ID = stringPreferencesKey("account_id")
    val API_KEY = stringPreferencesKey("api_key")

    // Safety controls (see MainActivity / Mt5AccessibilityService)
    val AUTO_EXECUTE = booleanPreferencesKey("auto_execute")       // default OFF - require manual confirm
    val MIN_CONFIDENCE = stringPreferencesKey("min_confidence")     // stored as string, parsed to Float
}

const val DEFAULT_SERVER_IP = "192.168.1.100"
const val DEFAULT_MIN_CONFIDENCE = 0.70f

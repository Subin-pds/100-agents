package com.jarvis.tracker

import android.content.Context
import android.content.SharedPreferences
import java.time.LocalDate

/**
 * Per-day tracking state — direct port of static/index.html's `tripState`
 * shape, so the native tracker behaves identically to the web version it
 * replaces (same fields, same gap/noise-floor rules, applied in
 * LocationTrackingService).
 */
data class TripState(
    val date: String,
    val km: Double,
    val lastLat: Double?,
    val lastLon: Double?,
    val lastFixTime: Long?,
    val lastSentKm: Double,
)

// Local calendar date, not UTC/the server's date — matches
// static/index.html's todayLocal(), so a trip near midnight lands on the
// day the user actually experienced it regardless of where the backend
// happens to be hosted.
fun todayLocal(): String = LocalDate.now().toString() // yyyy-MM-dd

fun freshTripState(): TripState =
    TripState(date = todayLocal(), km = 0.0, lastLat = null, lastLon = null, lastFixTime = null, lastSentKm = 0.0)

private const val PREFS_NAME = "jarvis_tracker"

private const val KEY_DATE = "trip_date"
private const val KEY_KM = "trip_km"
private const val KEY_LAST_LAT = "trip_last_lat"
private const val KEY_LAST_LON = "trip_last_lon"
private const val KEY_LAST_FIX_TIME = "trip_last_fix_time"
private const val KEY_LAST_SENT_KM = "trip_last_sent_km"

private const val KEY_BACKEND_URL = "backend_url"
private const val KEY_PIN = "pin"

private fun prefs(context: Context): SharedPreferences =
    context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

// SharedPreferences has no native double type; storing lat/lon/km as Float
// would lose enough precision to matter for GPS coordinates, so round-trip
// them as the exact bit pattern instead.
private fun SharedPreferences.Editor.putDouble(key: String, value: Double): SharedPreferences.Editor =
    putLong(key, java.lang.Double.doubleToRawLongBits(value))

private fun SharedPreferences.getDoubleOrNull(key: String): Double? =
    if (contains(key)) java.lang.Double.longBitsToDouble(getLong(key, 0L)) else null

fun loadTripState(context: Context): TripState {
    val p = prefs(context)
    val date = p.getString(KEY_DATE, null) ?: return freshTripState()
    if (date != todayLocal()) return freshTripState() // day rolled over
    return TripState(
        date = date,
        km = p.getDoubleOrNull(KEY_KM) ?: 0.0,
        lastLat = p.getDoubleOrNull(KEY_LAST_LAT),
        lastLon = p.getDoubleOrNull(KEY_LAST_LON),
        lastFixTime = if (p.contains(KEY_LAST_FIX_TIME)) p.getLong(KEY_LAST_FIX_TIME, 0L) else null,
        lastSentKm = p.getDoubleOrNull(KEY_LAST_SENT_KM) ?: 0.0,
    )
}

fun saveTripState(context: Context, state: TripState) {
    prefs(context).edit().apply {
        putString(KEY_DATE, state.date)
        putDouble(KEY_KM, state.km)
        if (state.lastLat != null) putDouble(KEY_LAST_LAT, state.lastLat) else remove(KEY_LAST_LAT)
        if (state.lastLon != null) putDouble(KEY_LAST_LON, state.lastLon) else remove(KEY_LAST_LON)
        if (state.lastFixTime != null) putLong(KEY_LAST_FIX_TIME, state.lastFixTime) else remove(KEY_LAST_FIX_TIME)
        putDouble(KEY_LAST_SENT_KM, state.lastSentKm)
        apply()
    }
}

fun loadSettings(context: Context): Pair<String, String> {
    val p = prefs(context)
    return Pair(p.getString(KEY_BACKEND_URL, "") ?: "", p.getString(KEY_PIN, "") ?: "")
}

fun saveSettings(context: Context, backendUrl: String, pin: String) {
    prefs(context).edit().putString(KEY_BACKEND_URL, backendUrl).putString(KEY_PIN, pin).apply()
}

package com.jarvis.tracker

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.location.Location
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

// A fix arriving long after the previous one means tracking was effectively
// paused — the straight line between those two fixes isn't the road
// actually driven, so the gap is skipped rather than added as a guessed
// distance. Same rule static/index.html's (now-removed) tracker used; this
// service exists specifically because that browser-tab version couldn't
// survive screen-lock or backgrounding long enough to avoid triggering this
// constantly.
private const val GAP_THRESHOLD_MS = 3 * 60 * 1000L

// GPS noise produces small phantom jumps even standing still.
private const val MIN_FIX_DISTANCE_KM = 0.02

// Debounce: don't POST on every single fix, wait until real movement has
// accumulated, then send once after a short delay.
private const val SEND_THRESHOLD_KM = 0.1
private const val SEND_DELAY_MS = 60_000L

private const val CHANNEL_ID = "jarvis_tracking"
private const val NOTIFICATION_ID = 1

class LocationTrackingService : Service() {

    private lateinit var fusedClient: FusedLocationProviderClient
    private val sendHandler = Handler(Looper.getMainLooper())
    private var sendScheduled = false

    private val locationCallback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            result.lastLocation?.let(::handleLocation)
        }
    }

    override fun onCreate() {
        super.onCreate()
        isRunning = true
        fusedClient = LocationServices.getFusedLocationProviderClient(this)
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIFICATION_ID, buildNotification(getString(R.string.notif_status_starting)))
        startLocationUpdates()
        return START_STICKY
    }

    override fun onDestroy() {
        isRunning = false
        fusedClient.removeLocationUpdates(locationCallback)
        sendHandler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun startLocationUpdates() {
        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 20_000L)
            .setMinUpdateIntervalMillis(10_000L)
            .setMinUpdateDistanceMeters(10f)
            .build()
        try {
            fusedClient.requestLocationUpdates(request, locationCallback, Looper.getMainLooper())
        } catch (_: SecurityException) {
            // Permission was revoked after Start was tapped (e.g. the user
            // turned it off in Settings) — stop cleanly rather than crash.
            stopSelf()
        }
    }

    private fun handleLocation(location: Location) {
        val now = System.currentTimeMillis()
        var state = loadTripState(this)
        if (state.date != todayLocal()) state = freshTripState()

        val withinGap = state.lastFixTime != null && (now - state.lastFixTime) <= GAP_THRESHOLD_MS
        var km = state.km
        if (state.lastLat != null && state.lastLon != null && withinGap) {
            val delta = haversineKm(state.lastLat, state.lastLon, location.latitude, location.longitude)
            if (delta >= MIN_FIX_DISTANCE_KM) km += delta
        }

        state = state.copy(km = km, lastLat = location.latitude, lastLon = location.longitude, lastFixTime = now)
        saveTripState(this, state)
        updateNotification(state)

        if (!sendScheduled && state.km - state.lastSentKm >= SEND_THRESHOLD_KM) {
            sendScheduled = true
            sendHandler.postDelayed({ sendScheduled = false; sendDistance() }, SEND_DELAY_MS)
        }
    }

    private fun sendDistance() {
        val state = loadTripState(this)
        val (backendUrl, pin) = loadSettings(this)
        if (backendUrl.isBlank()) return
        Thread {
            val success = TripApiClient.postDistance(backendUrl, pin, state.date, state.km)
            if (success) saveTripState(this, state.copy(lastSentKm = state.km))
        }.start()
    }

    private fun haversineKm(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val r = 6371.0
        val dLat = Math.toRadians(lat2 - lat1)
        val dLon = Math.toRadians(lon2 - lon1)
        val sinDLat = sin(dLat / 2)
        val sinDLon = sin(dLon / 2)
        val a = sinDLat * sinDLat + cos(Math.toRadians(lat1)) * cos(Math.toRadians(lat2)) * sinDLon * sinDLon
        return r * 2 * atan2(sqrt(a), sqrt(1 - a))
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID, getString(R.string.notif_channel_name), NotificationManager.IMPORTANCE_LOW,
            )
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun buildNotification(text: String): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setOngoing(true)
            .build()

    private fun updateNotification(state: TripState) {
        getSystemService(NotificationManager::class.java)
            .notify(NOTIFICATION_ID, buildNotification(getString(R.string.notif_status_tracking, state.km)))
    }

    companion object {
        @Volatile var isRunning: Boolean = false
            private set
    }
}

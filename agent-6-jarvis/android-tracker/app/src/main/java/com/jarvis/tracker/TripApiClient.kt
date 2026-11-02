package com.jarvis.tracker

import android.util.Log
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

/**
 * Mirrors the exact contract static/index.html's trip tracker already POSTs
 * to — see agent-6-jarvis/api.py's /trip/distance endpoint. km_travelled is
 * always the day's full cumulative total, never a delta; the server
 * overwrites its stored value with whatever is sent here.
 */
object TripApiClient {
    private const val TAG = "TripApiClient"

    fun postDistance(backendUrl: String, pin: String, date: String, kmTravelled: Double): Boolean {
        return try {
            val url = URL(backendUrl.trimEnd('/') + "/trip/distance")
            val body = JSONObject().apply {
                put("date", date)
                put("km_travelled", kmTravelled)
                put("pin", pin)
            }
            val connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                doOutput = true
                setRequestProperty("Content-Type", "application/json")
                connectTimeout = 10_000
                readTimeout = 10_000
            }
            connection.outputStream.use { stream ->
                OutputStreamWriter(stream, Charsets.UTF_8).use { it.write(body.toString()) }
            }
            val ok = connection.responseCode in 200..299
            connection.disconnect()
            ok
        } catch (e: Exception) {
            Log.w(TAG, "trip distance POST failed: ${e.message}")
            false
        }
    }
}

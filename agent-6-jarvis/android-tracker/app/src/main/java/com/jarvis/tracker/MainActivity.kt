package com.jarvis.tracker

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var backendUrlInput: EditText
    private lateinit var pinInput: EditText
    private lateinit var statusText: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        backendUrlInput = findViewById(R.id.backendUrlInput)
        pinInput = findViewById(R.id.pinInput)
        statusText = findViewById(R.id.statusText)

        val (savedUrl, savedPin) = loadSettings(this)
        backendUrlInput.setText(savedUrl)
        pinInput.setText(savedPin)

        findViewById<Button>(R.id.saveButton).setOnClickListener {
            saveSettings(this, backendUrlInput.text.toString().trim(), pinInput.text.toString().trim())
            Toast.makeText(this, R.string.saved, Toast.LENGTH_SHORT).show()
        }

        findViewById<Button>(R.id.grantPermissionsButton).setOnClickListener { requestForegroundLocation() }
        findViewById<Button>(R.id.backgroundLocationButton).setOnClickListener { requestBackgroundLocation() }
        findViewById<Button>(R.id.batteryOptimizationButton).setOnClickListener { requestBatteryExemption() }
        findViewById<Button>(R.id.startButton).setOnClickListener { startTracking() }
        findViewById<Button>(R.id.stopButton).setOnClickListener { stopTracking() }
    }

    override fun onResume() {
        super.onResume()
        updateStatus()
    }

    // --- Permissions -----------------------------------------------------
    // Android forbids requesting fine + background location in the same
    // dialog from API 30+ — foreground location must already be granted
    // before background can be requested as its own follow-up step.

    private fun requestForegroundLocation() {
        val permissions = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION,
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        ActivityCompat.requestPermissions(this, permissions.toTypedArray(), REQUEST_FOREGROUND)
    }

    private fun requestBackgroundLocation() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            updateStatus()
            return // background location wasn't a separate permission before Android 10
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
            != PackageManager.PERMISSION_GRANTED
        ) {
            Toast.makeText(this, R.string.grant_foreground_first, Toast.LENGTH_LONG).show()
            return
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_BACKGROUND_LOCATION)
            == PackageManager.PERMISSION_GRANTED
        ) {
            updateStatus()
            return
        }
        // On many Android 11+ builds the system dialog only offers "While
        // using the app" here. onRequestPermissionsResult below falls
        // through to app settings if this doesn't end up fully granted.
        ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.ACCESS_BACKGROUND_LOCATION), REQUEST_BACKGROUND)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_BACKGROUND && grantResults.any { it != PackageManager.PERMISSION_GRANTED }) {
            startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", packageName, null)))
        }
        updateStatus()
    }

    private fun requestBatteryExemption() {
        val powerManager = getSystemService(PowerManager::class.java)
        if (powerManager.isIgnoringBatteryOptimizations(packageName)) return
        startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName")))
    }

    private fun hasRequiredPermissions(): Boolean {
        val fine = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED
        val background = Build.VERSION.SDK_INT < Build.VERSION_CODES.Q ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_BACKGROUND_LOCATION) ==
            PackageManager.PERMISSION_GRANTED
        val notifications = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
        return fine && background && notifications
    }

    // --- Start/stop --------------------------------------------------------

    private fun startTracking() {
        val (backendUrl, _) = loadSettings(this)
        if (backendUrl.isBlank()) {
            Toast.makeText(this, R.string.set_backend_url_first, Toast.LENGTH_LONG).show()
            return
        }
        if (!hasRequiredPermissions()) {
            Toast.makeText(this, R.string.grant_permissions_first, Toast.LENGTH_LONG).show()
            return
        }
        ContextCompat.startForegroundService(this, Intent(this, LocationTrackingService::class.java))
        updateStatus()
    }

    private fun stopTracking() {
        stopService(Intent(this, LocationTrackingService::class.java))
        updateStatus()
    }

    private fun updateStatus() {
        val state = loadTripState(this)
        val runningLabel = if (LocationTrackingService.isRunning) "running" else "stopped"
        statusText.text = getString(R.string.status_km_today, state.km, runningLabel)
    }

    companion object {
        private const val REQUEST_FOREGROUND = 100
        private const val REQUEST_BACKGROUND = 101
    }
}

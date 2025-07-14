// GeminiMcpService.kt

package com.example.mcpapp

import android.app.*
import android.content.Intent
import android.os.Binder
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.PowerManager.WakeLock
import android.util.Log
import androidx.core.app.NotificationCompat
import com.google.ai.client.generativeai.GenerativeModel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.BufferedReader
import java.io.IOException
import java.io.InputStreamReader
import java.util.concurrent.TimeUnit
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class GeminiMcpService : Service() {

    companion object {
        const val NOTIFICATION_ID = 1001
        const val CHANNEL_ID = "gemini_mcp_service_channel"
        const val ACTION_STOP_SERVICE = "com.example.mcpapp.STOP_SERVICE"
    }

    private val client = OkHttpClient.Builder()
        .connectTimeout(45, TimeUnit.SECONDS)
        .readTimeout(45, TimeUnit.SECONDS)
        .writeTimeout(45, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .pingInterval(20, TimeUnit.SECONDS)
        .addNetworkInterceptor { chain ->
            val request = chain.request().newBuilder()
                .addHeader("Connection", "keep-alive")
                .addHeader("Cache-Control", "no-cache")
                .addHeader("Keep-Alive", "timeout=300, max=1000")
                .build()
            chain.proceed(request)
        }
        .build()

    private val executor = Executors.newSingleThreadExecutor()
    private val mcpUrl = "http://192.168.43.228:8000/mcp/"

    private val binder = GeminiMcpBinder()
    private lateinit var generativeModel: GenerativeModel
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // Enhanced wake lock management
    private lateinit var wakeLock: WakeLock
    private lateinit var wifiLock: WifiManager.WifiLock

    private var requestId = 1
    private var pendingRequestId: Int? = null
    private var responseChannel: Channel<String>? = null
    private val isListening = AtomicBoolean(false)
    private val shouldReconnect = AtomicBoolean(true)
    private val isServiceRunning = AtomicBoolean(false)

    private var currentUserQuery = ""
    private var maxIterations = 20 // Increased for complex operations
    private var currentIteration = 0
    private val maxRetries = 5 // Increased retries
    private var connectionRetryCount = 0
    private val maxConnectionRetries = 10

    interface GeminiMcpCallback {
        fun onStatusUpdate(status: String)
        fun onResponse(response: String)
        fun onError(error: String)
        fun onCompleted()
    }

    private var callback: GeminiMcpCallback? = null

    inner class GeminiMcpBinder : Binder() {
        fun getService(): GeminiMcpService = this@GeminiMcpService
    }

    override fun onCreate() {
        super.onCreate()

        generativeModel = GenerativeModel(
            modelName = "gemini-2.5-flash",
            apiKey = "AIzaSyDp_sEGHS_JBdjp5M_vbB81HdCcwzPgIOE"
        )

        createNotificationChannel()
        acquireLocks()
        isServiceRunning.set(true)
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Gemini MCP Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Background automation service"
                setSound(null, null)
                enableVibration(false)
                setShowBadge(false)
            }

            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(status: String = "Running automation..."): Notification {
        val stopIntent = Intent(this, GeminiMcpService::class.java).apply {
            action = ACTION_STOP_SERVICE
        }
        val stopPendingIntent = PendingIntent.getService(
            this, 0, stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val mainIntent = Intent(this, MainActivity::class.java)
        val mainPendingIntent = PendingIntent.getActivity(
            this, 0, mainIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("MCP Automation Active")
            .setContentText(status)
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setOngoing(true)
            .setSilent(true)
            .setContentIntent(mainPendingIntent)
            .addAction(
                android.R.drawable.ic_media_pause,
                "Stop",
                stopPendingIntent
            )
            .build()
    }

    private fun acquireLocks() {
        // Enhanced wake lock
        val powerManager = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "GeminiMcpService:WakeLock"
        )
        wakeLock.acquire(30*60*1000L) // 30 minutes

        // WiFi lock to maintain network connectivity
        val wifiManager = applicationContext.getSystemService(WIFI_SERVICE) as WifiManager
        wifiLock = wifiManager.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "GeminiMcpService:WifiLock")
        wifiLock.acquire()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP_SERVICE -> {
                stopSelf()
                return START_NOT_STICKY
            }
        }

        startForeground(NOTIFICATION_ID, createNotification())
        return START_STICKY
    }

    override fun onBind(intent: Intent): IBinder {
        return binder
    }

    fun setCallback(callback: GeminiMcpCallback) {
        this.callback = callback
    }

    fun removeCallback() {
        this.callback = null
    }

    private fun updateNotification(status: String) {
        val notificationManager = getSystemService(NotificationManager::class.java)
        notificationManager.notify(NOTIFICATION_ID, createNotification(status))
    }

    fun processUserQuery(query: String) {
        if (query.isBlank()) {
            callback?.onError("Query cannot be empty")
            return
        }

        currentUserQuery = query
        currentIteration = 0
        connectionRetryCount = 0
        shouldReconnect.set(true)

        serviceScope.launch {
            try {
                updateNotification("Initializing automation...")
                callback?.onStatusUpdate("Initializing automation...")

                // Ensure service is in foreground
                startForeground(NOTIFICATION_ID, createNotification("Initializing..."))

                // Start SSE listener with enhanced retry logic
                startSSEListener()

                // Longer delay to ensure stable connection
                delay(3000)

                updateNotification("Connecting to device...")
                callback?.onStatusUpdate("Selecting device...")
                selectDevice()
                Log.d("selectDevice", "device selected")

                getToolsList()
                Log.d("getToolsList", "got tools $toolsList")

                updateNotification("Processing automation...")
                startGeminiMcpLoop()
            } catch (e: Exception) {
                updateNotification("Error occurred")
                callback?.onError("Error processing query: ${e.message}")
                Log.e("GeminiMcpService", "Error in processUserQuery", e)
            }
        }
    }

    private suspend fun selectDevice() {
        val currentRequestId = requestId++
        pendingRequestId = currentRequestId

        val deviceSelection = JSONObject().apply {
            put("jsonrpc", "2.0")
            put("id", currentRequestId)
            put("method", "tools/call")
            put("params", JSONObject().apply {
                put("name", "mobile_use_device")
                put("arguments", JSONObject().apply {
                    put("device", "R3CW90HS7BP")
                    put("deviceType", "android")
                })
            })
        }

        sendJsonRpcRequestWithRetry(deviceSelection)
        waitForResponse()
        pendingRequestId = null
    }

    private var prevResponse = ""
    private var toolsList = ""

    private suspend fun getToolsList() {
        val currentRequestId = requestId++
        pendingRequestId = currentRequestId

        val toolsListRequest = JSONObject().apply {
            put("jsonrpc", "2.0")
            put("id", currentRequestId)
            put("method", "tools/list")
            put("params", JSONObject())
        }

        sendJsonRpcRequestWithRetry(toolsListRequest)
        val response = waitForResponse()
        toolsList = response
        pendingRequestId = null
    }

    private suspend fun waitForResponse(): String {
        return withContext(Dispatchers.IO) {
            responseChannel = Channel(Channel.UNLIMITED)

            var attempts = 0
            while (attempts < maxRetries) {
                try {
                    val response = responseChannel!!.receive()
                    return@withContext response
                } catch (e: Exception) {
                    attempts++
                    Log.e("GeminiMcpService", "Error waiting for response, attempt $attempts", e)
                    if (attempts < maxRetries) {
                        delay(3000) // Longer delay between retries
                        if (!isListening.get()) {
                            restartSSEListener()
                        }
                    }
                }
            }
            throw Exception("Failed to receive response after $maxRetries attempts")
        }
    }

    private fun startSSEListener() {
        if (isListening.get()) {
            Log.d("MCPService", "SSE listener already running")
            return
        }

        isListening.set(true)
        connectionRetryCount = 0

        executor.execute {
            while (shouldReconnect.get() && !executor.isShutdown && isServiceRunning.get()) {
                try {
                    Log.d("MCPService", "Attempting SSE connection...")
                    
                    val getRequest = Request.Builder()
                        .url(mcpUrl)
                        .get()
                        .header("Cache-Control", "no-cache")
                        .header("Accept", "text/event-stream")
                        .header("Connection", "keep-alive")
                        .header("Keep-Alive", "timeout=300")
                        .build()

                    client.newCall(getRequest).execute().use { response ->
                        if (!response.isSuccessful) {
                            Log.e("MCPService", "❌ Failed SSE connection: ${response.code}")
                            connectionRetryCount++
                            if (connectionRetryCount < maxConnectionRetries) {
                                Thread.sleep(5000)
                                continue
                            } else {
                                callback?.onError("Failed to establish stable connection after $maxConnectionRetries attempts")
                                return@execute
                            }
                        }

                        Log.d("MCPService", "✅ SSE connection established")
                        connectionRetryCount = 0 // Reset on successful connection

                        val reader = BufferedReader(InputStreamReader(response.body?.byteStream()))
                        var event: String? = null
                        val dataBuilder = StringBuilder()
                        var line: String?
                        var lastDataTime = System.currentTimeMillis()

                        while (reader.readLine().also { line = it } != null && 
                               shouldReconnect.get() && isServiceRunning.get()) {
                            
                            line = line?.trim()
                            lastDataTime = System.currentTimeMillis()
                            
                            when {
                                line!!.startsWith("event:") -> {
                                    event = line.removePrefix("event:").trim()
                                }

                                line.startsWith("data:") -> {
                                    dataBuilder.append(line.removePrefix("data:").trim())
                                }

                                line.isEmpty() -> {
                                    val fullData = dataBuilder.toString()
                                    if (event != null && fullData.isNotEmpty()) {
                                        Log.d("SSE_RAW", "event=$event, data=$fullData")

                                        when (event) {
                                            "endpoint" -> {
                                                Log.d("MCPService", "Session endpoint: $fullData")
                                            }

                                            "message" -> {
                                                try {
                                                    val responseJson = JSONObject(fullData)
                                                    val responseId = responseJson.optInt("id", -1)

                                                    if (pendingRequestId != null && responseId == pendingRequestId) {
                                                        Log.d("MCPService", "✅ Received response for request $responseId")
                                                        responseChannel?.trySend(fullData)
                                                    } else {
                                                        Log.d("MCPService", "Response ID $responseId doesn't match pending $pendingRequestId")
                                                    }
                                                } catch (e: Exception) {
                                                    Log.e("MCPService", "Error parsing message response: ${e.message}")
                                                    if (pendingRequestId != null) {
                                                        responseChannel?.trySend(fullData)
                                                    }
                                                }
                                            }

                                            "error" -> {
                                                Log.e("MCPService", "Server error: $fullData")
                                                responseChannel?.trySend(fullData)
                                            }

                                            else -> {
                                                Log.d("MCPService", "Unknown event type '$event': $fullData")
                                            }
                                        }

                                        prevResponse = fullData
                                    }
                                    event = null
                                    dataBuilder.setLength(0)
                                }
                            }

                            // Check for connection timeout
                            if (System.currentTimeMillis() - lastDataTime > 60000) { // 60 seconds timeout
                                Log.w("MCPService", "SSE connection timeout, reconnecting...")
                                break
                            }
                        }
                    }
                } catch (e: Exception) {
                    Log.e("MCPService", "❌ SSE error: ${e.message}")
                    connectionRetryCount++
                    if (shouldReconnect.get() && isServiceRunning.get() && connectionRetryCount < maxConnectionRetries) {
                        Log.d("MCPService", "Retrying connection in 5 seconds... (attempt $connectionRetryCount/$maxConnectionRetries)")
                        Thread.sleep(5000)
                    } else if (connectionRetryCount >= maxConnectionRetries) {
                        callback?.onError("Connection failed after $maxConnectionRetries attempts")
                        break
                    }
                }
            }
            isListening.set(false)
            Log.d("MCPService", "SSE listener stopped")
        }
    }

    private fun restartSSEListener() {
        Log.d("MCPService", "Restarting SSE listener...")
        isListening.set(false)
        Thread.sleep(2000) // Longer pause before restart
        if (shouldReconnect.get() && isServiceRunning.get()) {
            startSSEListener()
        }
    }

    private var fullMcpResponses = ""

    private suspend fun startGeminiMcpLoop() {
        if (currentIteration >= maxIterations) {
            updateNotification("Maximum iterations reached")
            callback?.onError("Maximum iterations reached. Task may be too complex.")
            return
        }

        currentIteration++
        val status = "Processing step $currentIteration of $maxIterations..."
        updateNotification(status)
        callback?.onStatusUpdate(status)

        val geminiPrompt = createGeminiPrompt()
        Log.d("Gemini", "Prompt: $geminiPrompt")

        try {
            val response = generativeModel.generateContent(geminiPrompt)
            val responseText = response.text ?: ""

            Log.d("GeminiMcpService", "Gemini response: $responseText")

            if (responseText.contains("TASK_COMPLETED") ||
                responseText.contains("\"status\": \"completed\"") ||
                responseText.contains("task is complete")) {
                
                updateNotification("Task completed")
                callback?.onResponse("Task completed successfully!")
                callback?.onCompleted()
                return
            }

            val jsonResponse = extractJsonFromResponse(responseText)
            if (jsonResponse != null) {
                val currentRequestId = requestId++
                pendingRequestId = currentRequestId
                jsonResponse.put("id", currentRequestId)

                // Ensure connection is still alive before sending
                if (!isListening.get()) {
                    Log.w("GeminiMcpService", "SSE connection lost, attempting to reconnect...")
                    restartSSEListener()
                    delay(3000) // Wait for reconnection
                }

                sendJsonRpcRequestWithRetry(jsonResponse)
                val mcpResponse = waitForResponse()
                fullMcpResponses += "\n" + mcpResponse
                pendingRequestId = null

                Log.i("requestId: $requestId", "full response: $fullMcpResponses")

                // Longer delay between iterations for stability
                delay(2000)

                // Continue the loop
                startGeminiMcpLoop()
            } else {
                callback?.onError("Failed to parse Gemini response as JSON: $responseText")
            }

        } catch (e: Exception) {
            Log.e("GeminiMcpService", "Error in Gemini loop", e)
            callback?.onError("Error communicating with Gemini: ${e.message}")
        }
    }

    private suspend fun sendJsonRpcRequestWithRetry(params: JSONObject) {
        var attempts = 0
        while (attempts < maxRetries) {
            try {
                sendJsonRpcRequest(params)
                return
            } catch (e: Exception) {
                attempts++
                Log.e("MCPService", "Send request failed, attempt $attempts", e)
                if (attempts < maxRetries) {
                    delay(3000) // Longer delay between send retries
                    
                    // Check if we need to restart SSE connection
                    if (!isListening.get()) {
                        restartSSEListener()
                        delay(2000)
                    }
                }
            }
        }
        throw Exception("Failed to send request after $maxRetries attempts")
    }

    private fun sendJsonRpcRequest(params: JSONObject) {
        val requestBody = params.toString()
            .toRequestBody("application/json".toMediaTypeOrNull())

        val postRequest = Request.Builder()
            .url(mcpUrl)
            .post(requestBody)
            .header("Connection", "keep-alive")
            .build()

        client.newCall(postRequest).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e("MCPService", "❌ JSON-RPC POST failed: ${e.message}")
            }

            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (it.isSuccessful) {
                        Log.d("MCPService", "✅ Sent request successfully")
                    } else {
                        Log.e("MCPService", "❌ JSON-RPC error: ${it.code}")
                    }
                }
            }
        })
    }

    private fun createGeminiPrompt(): String {
        return """
            You are an AI assistant that controls mobile devices through an MCP server.
            Your task is to help execute user queries by calling the appropriate mobile device tools.
            The service is running in the background and can interact with any app on the device.
            
            AVAILABLE TOOLS:
            $toolsList
            
            USER QUERY: $currentUserQuery
            
            PREVIOUS MCP RESPONSES:
            $fullMcpResponses
            
            CRITICAL INSTRUCTIONS:
            1. Respond with ONLY valid JSON - no markdown formatting, no code blocks, no extra text
            2. If task is complete, respond with: {"status": "completed", "message": "Task completed successfully"}
            3. Otherwise, respond with the exact MCP JSON format shown below
            4. Be patient with app transitions and UI loading times
            5. If an app needs time to load, consider using appropriate waiting tools
            
            RESPONSE FORMAT (choose one):
            
            For MCP tool call:
            {"jsonrpc": "2.0", "id": ${requestId}, "method": "tools/call", "params": {"name": "tool_name", "arguments": {"param": "value"}}}
            
            For completion:
            {"status": "completed", "message": "Task completed successfully"}
            
            IMPORTANT: 
            - NO markdown formatting (no ```
            - NO additional text or explanations
            - ONLY JSON response
            - Use exact tool names from the tools list
            - Consider app switching delays and UI loading times
            - Think about what action is needed next based on user query and previous responses
        """.trimIndent()
    }

    private fun extractJsonFromResponse(response: String): JSONObject? {
        return try {
            val trimmed = response.trim()
            val startIndex = trimmed.indexOf('{')
            val endIndex = trimmed.lastIndexOf('}')

            if (startIndex != -1 && endIndex != -1 && endIndex > startIndex) {
                val jsonString = trimmed.substring(startIndex, endIndex + 1)
                JSONObject(jsonString)
            } else {
                null
            }
        } catch (e: Exception) {
            Log.e("GeminiMcpService", "Failed to parse JSON: ${e.message}")
            null
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        
        isServiceRunning.set(false)
        callback = null
        shouldReconnect.set(false)
        isListening.set(false)
        responseChannel?.close()
        executor.shutdown()

        // Release all locks
        if (::wakeLock.isInitialized && wakeLock.isHeld) {
            wakeLock.release()
        }
        if (::wifiLock.isInitialized && wifiLock.isHeld) {
            wifiLock.release()
        }

        // Stop foreground service
        stopForeground(true)
        
        Log.d("GeminiMcpService", "Service destroyed")
    }
}




// MainActivity.kt

package com.example.mcpapp

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.provider.Settings
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var editTextPrompt: EditText
    private lateinit var buttonSend: Button
    private lateinit var buttonStop: Button
    private lateinit var textViewStatus: TextView
    private lateinit var textViewResponse: TextView
    private lateinit var textViewServiceStatus: TextView

    private var geminiMcpService: GeminiMcpService? = null
    private var bound = false
    private var serviceStarted = false

    companion object {
        private const val PERMISSION_REQUEST_CODE = 1001
        private const val OVERLAY_PERMISSION_REQUEST_CODE = 1002
    }

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val allGranted = permissions.all { it.value }
        if (allGranted) {
            checkOverlayPermission()
        } else {
            showPermissionDeniedDialog()
        }
    }

    private val overlayPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && Settings.canDrawOverlays(this)) {
            initializeService()
        } else {
            showOverlayPermissionDeniedDialog()
        }
    }

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(className: ComponentName, service: IBinder) {
            val binder = service as GeminiMcpService.GeminiMcpBinder
            geminiMcpService = binder.getService()
            bound = true
            updateServiceStatus("Connected")

            // Set callback for service responses
            geminiMcpService?.setCallback(object : GeminiMcpService.GeminiMcpCallback {
                override fun onStatusUpdate(status: String) {
                    runOnUiThread {
                        textViewStatus.text = status
                        updateServiceStatus("Running: $status")
                    }
                }

                override fun onResponse(response: String) {
                    runOnUiThread {
                        textViewResponse.text = response
                        buttonSend.isEnabled = true
                        buttonStop.isEnabled = false
                        updateServiceStatus("Task completed")
                    }
                }

                override fun onError(error: String) {
                    runOnUiThread {
                        textViewResponse.text = "Error: $error"
                        textViewStatus.text = "Error occurred"
                        buttonSend.isEnabled = true
                        buttonStop.isEnabled = false
                        updateServiceStatus("Error: $error")
                    }
                }

                override fun onCompleted() {
                    runOnUiThread {
                        textViewStatus.text = "Task completed successfully"
                        buttonSend.isEnabled = true
                        buttonStop.isEnabled = false
                        updateServiceStatus("Task completed successfully")
                    }
                }
            })
        }

        override fun onServiceDisconnected(arg0: ComponentName) {
            bound = false
            geminiMcpService = null
            updateServiceStatus("Disconnected")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        initializeViews()
        setupClickListeners()
        checkPermissions()
    }

    private fun initializeViews() {
        editTextPrompt = findViewById(R.id.editTextPrompt)
        buttonSend = findViewById(R.id.buttonSend)
        buttonStop = findViewById(R.id.buttonStop)
        textViewStatus = findViewById(R.id.textViewStatus)
        textViewResponse = findViewById(R.id.textViewResponse)
        textViewServiceStatus = findViewById(R.id.textViewServiceStatus)

        // Set initial states
        buttonSend.isEnabled = false
        buttonStop.isEnabled = false
        updateServiceStatus("Checking permissions...")
    }

    private fun setupClickListeners() {
        buttonSend.setOnClickListener {
            val prompt = editTextPrompt.text.toString().trim()
            if (prompt.isNotEmpty()) {
                startAutomation(prompt)
            } else {
                Toast.makeText(this, "Please enter a command", Toast.LENGTH_SHORT).show()
            }
        }

        buttonStop.setOnClickListener {
            stopAutomation()
        }
    }

    private fun startAutomation(prompt: String) {
        if (!bound || geminiMcpService == null) {
            Toast.makeText(this, "Service not connected. Please wait...", Toast.LENGTH_SHORT).show()
            return
        }

        buttonSend.isEnabled = false
        buttonStop.isEnabled = true
        textViewResponse.text = ""
        textViewStatus.text = "Starting automation..."
        
        geminiMcpService?.processUserQuery(prompt)
    }

    private fun stopAutomation() {
        // Stop the service
        if (serviceStarted) {
            val stopIntent = Intent(this, GeminiMcpService::class.java).apply {
                action = GeminiMcpService.ACTION_STOP_SERVICE
            }
            startService(stopIntent)
        }
        
        buttonSend.isEnabled = true
        buttonStop.isEnabled = false
        textViewStatus.text = "Automation stopped"
        updateServiceStatus("Stopped")
    }

    private fun updateServiceStatus(status: String) {
        textViewServiceStatus.text = "Service: $status"
    }

    private fun checkPermissions() {
        val permissions = mutableListOf<String>()

        // Check basic permissions
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.INTERNET) != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.INTERNET)
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.WAKE_LOCK) != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.WAKE_LOCK)
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_WIFI_STATE) != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.ACCESS_WIFI_STATE)
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CHANGE_WIFI_STATE) != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.CHANGE_WIFI_STATE)
        }

        // Check notification permission for Android 13+
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                permissions.add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        // Check foreground service permission for Android 14+
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.FOREGROUND_SERVICE) != PackageManager.PERMISSION_GRANTED) {
                permissions.add(Manifest.permission.FOREGROUND_SERVICE)
            }
        }

        if (permissions.isNotEmpty()) {
            permissionLauncher.launch(permissions.toTypedArray())
        } else {
            checkOverlayPermission()
        }
    }

    private fun checkOverlayPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
            showOverlayPermissionDialog()
        } else {
            initializeService()
        }
    }

    private fun showOverlayPermissionDialog() {
        AlertDialog.Builder(this)
            .setTitle("Overlay Permission Required")
            .setMessage("This app needs overlay permission to work in the background and interact with other apps. Please grant the permission in the next screen.")
            .setPositiveButton("Grant Permission") { _, _ ->
                requestOverlayPermission()
            }
            .setNegativeButton("Cancel") { _, _ ->
                updateServiceStatus("Overlay permission denied")
                Toast.makeText(this, "Overlay permission is required for automation", Toast.LENGTH_LONG).show()
            }
            .setCancelable(false)
            .show()
    }

    private fun requestOverlayPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION).apply {
                data = Uri.parse("package:$packageName")
            }
            overlayPermissionLauncher.launch(intent)
        }
    }

    private fun showPermissionDeniedDialog() {
        AlertDialog.Builder(this)
            .setTitle("Permissions Required")
            .setMessage("This app requires several permissions to function properly. Please grant all permissions in the app settings.")
            .setPositiveButton("Settings") { _, _ ->
                openAppSettings()
            }
            .setNegativeButton("Cancel") { _, _ ->
                updateServiceStatus("Permissions denied")
                finish()
            }
            .setCancelable(false)
            .show()
    }

    private fun showOverlayPermissionDeniedDialog() {
        AlertDialog.Builder(this)
            .setTitle("Overlay Permission Denied")
            .setMessage("Overlay permission is required for the app to work in the background. Please enable it in settings.")
            .setPositiveButton("Settings") { _, _ ->
                requestOverlayPermission()
            }
            .setNegativeButton("Continue Anyway") { _, _ ->
                initializeService()
            }
            .show()
    }

    private fun openAppSettings() {
        val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
            data = Uri.fromParts("package", packageName, null)
        }
        startActivity(intent)
    }

    private fun initializeService() {
        updateServiceStatus("Initializing...")
        startAndBindService()
    }

    private fun startAndBindService() {
        try {
            // Start the service as a foreground service
            val serviceIntent = Intent(this, GeminiMcpService::class.java)
            
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(serviceIntent)
            } else {
                startService(serviceIntent)
            }
            
            serviceStarted = true
            
            // Bind to the service
            bindService(serviceIntent, connection, Context.BIND_AUTO_CREATE)
            
            updateServiceStatus("Starting...")
            buttonSend.isEnabled = true
            
        } catch (e: Exception) {
            updateServiceStatus("Failed to start service: ${e.message}")
            Toast.makeText(this, "Failed to start service: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    override fun onStart() {
        super.onStart()
        // Service binding is handled in initializeService() after permissions are granted
    }

    override fun onStop() {
        super.onStop()
        // Don't unbind when activity stops to maintain background operation
        // Service will continue running in background
    }

    override fun onDestroy() {
        super.onDestroy()
        if (bound) {
            geminiMcpService?.removeCallback()
            unbindService(connection)
            bound = false
        }
    }

    override fun onResume() {
        super.onResume()
        // Reconnect to service if it's running but we're not bound
        if (serviceStarted && !bound) {
            val serviceIntent = Intent(this, GeminiMcpService::class.java)
            bindService(serviceIntent, connection, Context.BIND_AUTO_CREATE)
        }
    }
}

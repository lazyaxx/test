// GeminiMcpService.kt

package com.example.mcpapp

import android.app.*
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
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
        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "GeminiMcpService"
        private const val CHANNEL_NAME = "Gemini MCP Background Service"
    }

    private val client = OkHttpClient.Builder()
        .connectTimeout(60, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.SECONDS) // No read timeout for SSE
        .writeTimeout(30, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .pingInterval(45, TimeUnit.SECONDS)
        .addNetworkInterceptor { chain ->
            val request = chain.request().newBuilder()
                .addHeader("Connection", "keep-alive")
                .addHeader("Cache-Control", "no-cache")
                .addHeader("Accept", "text/event-stream")
                .build()
            chain.proceed(request)
        }
        .build()

    private val executor = Executors.newSingleThreadExecutor()
    private val mcpUrl = "http://192.168.43.228:8000/mcp/"

    private val binder = GeminiMcpBinder()
    private lateinit var generativeModel: GenerativeModel
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // Wake lock to prevent system from sleeping
    private lateinit var wakeLock: WakeLock
    
    // Network callback for handling network changes
    private lateinit var connectivityManager: ConnectivityManager
    private lateinit var networkCallback: ConnectivityManager.NetworkCallback

    private var requestId = 1
    private var pendingRequestId: Int? = null
    private var responseChannel: Channel<String>? = null
    private val isListening = AtomicBoolean(false)
    private val shouldReconnect = AtomicBoolean(true)
    private val isTaskRunning = AtomicBoolean(false)

    private var currentUserQuery = ""
    private var maxIterations = 20
    private var currentIteration = 0
    private val maxRetries = 5
    private val connectionRetryDelay = 3000L

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
        
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, createNotification("Service starting..."))

        generativeModel = GenerativeModel(
            modelName = "gemini-2.5-flash",
            apiKey = "API_KEY"
        )

        // Acquire a more persistent wake lock
        val powerManager = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK, 
            "GeminiMcpService:PersistentWakeLock"
        )
        wakeLock.acquire(60*60*1000L) // 1 hour wake lock

        setupNetworkMonitoring()
        
        Log.d("GeminiMcpService", "Service created and started as foreground service")
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Keeps Gemini MCP automation running in background"
                setShowBadge(false)
            }
            
            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(message: String): Notification {
        val intent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent, 
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Gemini MCP Automation")
            .setContentText(message)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }

    private fun updateNotification(message: String) {
        val notification = createNotification(message)
        val notificationManager = getSystemService(NotificationManager::class.java)
        notificationManager.notify(NOTIFICATION_ID, notification)
    }

    private fun setupNetworkMonitoring() {
        connectivityManager = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        
        networkCallback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                Log.d("GeminiMcpService", "Network available, reconnecting if needed")
                if (isTaskRunning.get() && !isListening.get()) {
                    serviceScope.launch {
                        delay(2000) // Wait a bit for network to stabilize
                        restartSSEListener()
                    }
                }
            }

            override fun onLost(network: Network) {
                Log.d("GeminiMcpService", "Network lost")
            }
        }

        val networkRequest = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()
            
        connectivityManager.registerNetworkCallback(networkRequest, networkCallback)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.d("GeminiMcpService", "onStartCommand called")
        return START_STICKY // Restart service if killed
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

    fun processUserQuery(query: String) {
        if (query.isBlank()) {
            callback?.onError("Query cannot be empty")
            return
        }

        if (isTaskRunning.get()) {
            callback?.onError("Another task is already running")
            return
        }

        currentUserQuery = query
        currentIteration = 0
        shouldReconnect.set(true)
        isTaskRunning.set(true)

        updateNotification("Processing: $query")

        serviceScope.launch {
            try {
                callback?.onStatusUpdate("Initializing automation...")

                // Start SSE listener first
                startSSEListener()

                // Wait longer for connection establishment
                delay(3000)

                callback?.onStatusUpdate("Selecting device...")
                selectDevice()
                Log.d("selectDevice", "device selected")

                getToolsList()
                Log.d("getToolsList", "got tools $toolsList")

                startGeminiMcpLoop()
            } catch (e: Exception) {
                callback?.onError("Error processing query: ${e.message}")
                Log.e("GeminiMcpService", "Error in processUserQuery", e)
                isTaskRunning.set(false)
                updateNotification("Error: ${e.message}")
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

            // Wait for response with longer timeout and more retries
            var attempts = 0
            while (attempts < maxRetries) {
                try {
                    val response = responseChannel!!.receive()
                    return@withContext response
                } catch (e: Exception) {
                    attempts++
                    Log.e("GeminiMcpService", "Error waiting for response, attempt $attempts", e)
                    if (attempts < maxRetries) {
                        delay(connectionRetryDelay)
                        if (!isListening.get()) {
                            restartSSEListener()
                            delay(2000) // Wait for connection to establish
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
        Log.d("MCPService", "Starting SSE listener...")

        executor.execute {
            var consecutiveErrors = 0
            val maxConsecutiveErrors = 5
            
            while (shouldReconnect.get() && !executor.isShutdown && consecutiveErrors < maxConsecutiveErrors) {
                try {
                    Log.d("MCPService", "Attempting SSE connection...")
                    
                    val getRequest = Request.Builder()
                        .url(mcpUrl)
                        .get()
                        .header("Cache-Control", "no-cache")
                        .header("Accept", "text/event-stream")
                        .header("Connection", "keep-alive")
                        .header("User-Agent", "GeminiMcpService/1.0")
                        .build()

                    client.newCall(getRequest).execute().use { response ->
                        if (!response.isSuccessful) {
                            Log.e("MCPService", "❌ Failed SSE connection: ${response.code}")
                            consecutiveErrors++
                            Thread.sleep(connectionRetryDelay)
                            return@use
                        }

                        Log.d("MCPService", "✅ SSE connection established")
                        consecutiveErrors = 0 // Reset error counter on successful connection

                        val reader = BufferedReader(InputStreamReader(response.body?.byteStream()))
                        var event: String? = null
                        val dataBuilder = StringBuilder()
                        var line: String?
                        var lastActivity = System.currentTimeMillis()

                        while (reader.readLine().also { line = it } != null && shouldReconnect.get()) {
                            lastActivity = System.currentTimeMillis()
                            line = line?.trim()
                            
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
                            if (System.currentTimeMillis() - lastActivity > 120000) { // 2 minutes
                                Log.w("MCPService", "No activity for 2 minutes, reconnecting...")
                                break
                            }
                        }
                    }
                } catch (e: Exception) {
                    consecutiveErrors++
                    Log.e("MCPService", "❌ SSE error (attempt $consecutiveErrors): ${e.message}")
                    if (shouldReconnect.get() && consecutiveErrors < maxConsecutiveErrors) {
                        Thread.sleep(connectionRetryDelay * consecutiveErrors) // Exponential backoff
                    }
                }
            }
            
            if (consecutiveErrors >= maxConsecutiveErrors) {
                Log.e("MCPService", "Too many consecutive errors, stopping SSE listener")
                callback?.onError("Connection failed after multiple attempts")
            }
            
            isListening.set(false)
        }
    }

    private fun restartSSEListener() {
        Log.d("MCPService", "Restarting SSE listener...")
        isListening.set(false)
        Thread.sleep(2000) // Longer pause for cleanup
        startSSEListener()
    }

    private var fullMcpResponses = ""

    private suspend fun startGeminiMcpLoop() {
        if (currentIteration >= maxIterations) {
            callback?.onError("Maximum iterations reached. Task may be too complex.")
            isTaskRunning.set(false)
            updateNotification("Task incomplete - max iterations reached")
            return
        }

        currentIteration++
        val statusMsg = "Processing step $currentIteration of $maxIterations..."
        callback?.onStatusUpdate(statusMsg)
        updateNotification(statusMsg)

        val geminiPrompt = createGeminiPrompt()
        Log.d("Gemini", "Prompt: $geminiPrompt")

        try {
            val response = generativeModel.generateContent(geminiPrompt)
            val responseText = response.text ?: ""

            Log.d("GeminiMcpService", "Gemini response: $responseText")

            if (responseText.contains("TASK_COMPLETED") ||
                responseText.contains("\"status\": \"completed\"") ||
                responseText.contains("task is complete")) {
                callback?.onResponse("Task completed successfully!")
                callback?.onCompleted()
                isTaskRunning.set(false)
                updateNotification("Task completed successfully")
                return
            }

            val jsonResponse = extractJsonFromResponse(responseText)
            if (jsonResponse != null) {
                val currentRequestId = requestId++
                pendingRequestId = currentRequestId
                jsonResponse.put("id", currentRequestId)

                sendJsonRpcRequestWithRetry(jsonResponse)
                val mcpResponse = waitForResponse()
                fullMcpResponses += "\n" + mcpResponse
                pendingRequestId = null

                Log.i("requestId: $requestId", "full response: $fullMcpResponses")

                // Add delay between iterations
                delay(2000)

                // Continue the loop
                startGeminiMcpLoop()
            } else {
                callback?.onError("Failed to parse Gemini response as JSON: $responseText")
                isTaskRunning.set(false)
                updateNotification("Error parsing Gemini response")
            }

        } catch (e: Exception) {
            Log.e("GeminiMcpService", "Error in Gemini loop", e)
            callback?.onError("Error communicating with Gemini: ${e.message}")
            isTaskRunning.set(false)
            updateNotification("Error: ${e.message}")
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
                    delay(connectionRetryDelay)
                    // Check if SSE connection is still alive
                    if (!isListening.get()) {
                        restartSSEListener()
                        delay(3000) // Wait for reconnection
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
            .header("Content-Type", "application/json")
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
            Remember that the device is already selected and start with the user query.
            
            AVAILABLE TOOLS:
            $toolsList
            
            USER QUERY: $currentUserQuery
            
            PREVIOUS MCP RESPONSES:
            $fullMcpResponses
            
            CRITICAL INSTRUCTIONS:
            1. Respond with ONLY valid JSON - no markdown formatting, no code blocks, no extra text
            2. If task is complete, respond with: {"status": "completed", "message": "Task completed successfully"}
            3. Otherwise, respond with the exact MCP JSON format shown below
            
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
            - Think about what action is needed next based on user query and previous responses
            - Be patient with UI interactions - some actions may take time to complete
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
        Log.d("GeminiMcpService", "Service being destroyed")
        
        callback = null
        shouldReconnect.set(false)
        isListening.set(false)
        isTaskRunning.set(false)
        responseChannel?.close()
        executor.shutdown()

        try {
            connectivityManager.unregisterNetworkCallback(networkCallback)
        } catch (e: Exception) {
            Log.e("GeminiMcpService", "Error unregistering network callback", e)
        }

        if (wakeLock.isHeld) {
            wakeLock.release()
        }
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
import android.os.PowerManager
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
    private lateinit var textViewPermissions: TextView

    private var geminiMcpService: GeminiMcpService? = null
    private var bound = false
    private var serviceStarted = false

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val allGranted = permissions.values.all { it }
        if (allGranted) {
            updatePermissionStatus()
            checkBatteryOptimization()
        } else {
            showPermissionDialog()
        }
    }

    private val batteryOptimizationLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        updatePermissionStatus()
    }

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(className: ComponentName, service: IBinder) {
            val binder = service as GeminiMcpService.GeminiMcpBinder
            geminiMcpService = binder.getService()
            bound = true

            // Set callback for service responses
            geminiMcpService?.setCallback(object : GeminiMcpService.GeminiMcpCallback {
                override fun onStatusUpdate(status: String) {
                    runOnUiThread {
                        textViewStatus.text = status
                    }
                }

                override fun onResponse(response: String) {
                    runOnUiThread {
                        textViewResponse.text = response
                        enableControls(true)
                    }
                }

                override fun onError(error: String) {
                    runOnUiThread {
                        textViewResponse.text = "Error: $error"
                        textViewStatus.text = "Ready"
                        enableControls(true)
                        
                        // Show error dialog for critical errors
                        if (error.contains("connection") || error.contains("network")) {
                            showErrorDialog("Connection Error", error)
                        }
                    }
                }

                override fun onCompleted() {
                    runOnUiThread {
                        textViewStatus.text = "Task completed successfully"
                        enableControls(true)
                        
                        // Show completion notification
                        Toast.makeText(this@MainActivity, "Automation completed!", Toast.LENGTH_SHORT).show()
                    }
                }
            })

            updateServiceStatus()
        }

        override fun onServiceDisconnected(arg0: ComponentName) {
            bound = false
            geminiMcpService = null
            updateServiceStatus()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        initializeViews()
        setupClickListeners()
        
        // Check and request permissions
        checkAndRequestPermissions()
        updatePermissionStatus()
    }

    private fun initializeViews() {
        editTextPrompt = findViewById(R.id.editTextPrompt)
        buttonSend = findViewById(R.id.buttonSend)
        buttonStop = findViewById(R.id.buttonStop)
        textViewStatus = findViewById(R.id.textViewStatus)
        textViewResponse = findViewById(R.id.textViewResponse)
        textViewPermissions = findViewById(R.id.textViewPermissions)
        
        // Set initial states
        buttonStop.isEnabled = false
        textViewStatus.text = "Ready"
    }

    private fun setupClickListeners() {
        buttonSend.setOnClickListener {
            val prompt = editTextPrompt.text.toString().trim()
            if (prompt.isNotEmpty()) {
                if (checkAllPermissions()) {
                    startAutomationTask(prompt)
                } else {
                    checkAndRequestPermissions()
                }
            } else {
                Toast.makeText(this, "Please enter a query", Toast.LENGTH_SHORT).show()
            }
        }

        buttonStop.setOnClickListener {
            stopAutomationTask()
        }

        textViewPermissions.setOnClickListener {
            checkAndRequestPermissions()
        }
    }

    private fun startAutomationTask(prompt: String) {
        enableControls(false)
        textViewResponse.text = ""
        textViewStatus.text = "Starting automation..."
        
        // Start the service first
        startForegroundService()
        
        // Process the query
        geminiMcpService?.processUserQuery(prompt)
    }

    private fun stopAutomationTask() {
        // Stop the service
        stopForegroundService()
        
        enableControls(true)
        textViewStatus.text = "Task stopped by user"
        textViewResponse.text = "Automation stopped"
    }

    private fun enableControls(enabled: Boolean) {
        buttonSend.isEnabled = enabled
        buttonStop.isEnabled = !enabled
        editTextPrompt.isEnabled = enabled
    }

    private fun startForegroundService() {
        if (!serviceStarted) {
            val serviceIntent = Intent(this, GeminiMcpService::class.java)
            
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(serviceIntent)
            } else {
                startService(serviceIntent)
            }
            
            serviceStarted = true
            updateServiceStatus()
        }
        
        // Bind to the service
        val bindIntent = Intent(this, GeminiMcpService::class.java)
        bindService(bindIntent, connection, Context.BIND_AUTO_CREATE)
    }

    private fun stopForegroundService() {
        if (bound) {
            geminiMcpService?.removeCallback()
            unbindService(connection)
            bound = false
        }
        
        if (serviceStarted) {
            val serviceIntent = Intent(this, GeminiMcpService::class.java)
            stopService(serviceIntent)
            serviceStarted = false
        }
        
        updateServiceStatus()
    }

    private fun updateServiceStatus() {
        runOnUiThread {
            val statusText = when {
                bound && serviceStarted -> "Service: Connected & Running"
                serviceStarted -> "Service: Running (Not Connected)"
                bound -> "Service: Connected (Not Running)"
                else -> "Service: Stopped"
            }
            // You can add a service status TextView if needed
        }
    }

    private fun checkAndRequestPermissions() {
        val requiredPermissions = mutableListOf<String>()
        
        // Check basic permissions
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.INTERNET) != PackageManager.PERMISSION_GRANTED) {
            requiredPermissions.add(Manifest.permission.INTERNET)
        }
        
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_NETWORK_STATE) != PackageManager.PERMISSION_GRANTED) {
            requiredPermissions.add(Manifest.permission.ACCESS_NETWORK_STATE)
        }
        
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.WAKE_LOCK) != PackageManager.PERMISSION_GRANTED) {
            requiredPermissions.add(Manifest.permission.WAKE_LOCK)
        }
        
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.FOREGROUND_SERVICE) != PackageManager.PERMISSION_GRANTED) {
            requiredPermissions.add(Manifest.permission.FOREGROUND_SERVICE)
        }

        // Check notification permission for Android 13+
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requiredPermissions.add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        if (requiredPermissions.isNotEmpty()) {
            requestPermissionLauncher.launch(requiredPermissions.toTypedArray())
        } else {
            checkBatteryOptimization()
        }
    }

    private fun checkAllPermissions(): Boolean {
        val internetPermission = ContextCompat.checkSelfPermission(this, Manifest.permission.INTERNET) == PackageManager.PERMISSION_GRANTED
        val networkPermission = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_NETWORK_STATE) == PackageManager.PERMISSION_GRANTED
        val wakeLockPermission = ContextCompat.checkSelfPermission(this, Manifest.permission.WAKE_LOCK) == PackageManager.PERMISSION_GRANTED
        val foregroundPermission = ContextCompat.checkSelfPermission(this, Manifest.permission.FOREGROUND_SERVICE) == PackageManager.PERMISSION_GRANTED
        
        var notificationPermission = true
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            notificationPermission = ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        }
        
        val batteryOptimized = isBatteryOptimizationDisabled()
        
        return internetPermission && networkPermission && wakeLockPermission && foregroundPermission && notificationPermission && batteryOptimized
    }

    private fun checkBatteryOptimization() {
        if (!isBatteryOptimizationDisabled()) {
            showBatteryOptimizationDialog()
        }
        updatePermissionStatus()
    }

    private fun isBatteryOptimizationDisabled(): Boolean {
        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        return powerManager.isIgnoringBatteryOptimizations(packageName)
    }

    private fun showBatteryOptimizationDialog() {
        AlertDialog.Builder(this)
            .setTitle("Battery Optimization")
            .setMessage("To ensure the automation works reliably in the background, please disable battery optimization for this app.")
            .setPositiveButton("Open Settings") { _, _ ->
                openBatteryOptimizationSettings()
            }
            .setNegativeButton("Skip") { _, _ ->
                updatePermissionStatus()
            }
            .show()
    }

    private fun openBatteryOptimizationSettings() {
        try {
            val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
            intent.data = Uri.parse("package:$packageName")
            batteryOptimizationLauncher.launch(intent)
        } catch (e: Exception) {
            // Fallback to general battery optimization settings
            try {
                val intent = Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)
                batteryOptimizationLauncher.launch(intent)
            } catch (ex: Exception) {
                Toast.makeText(this, "Please manually disable battery optimization for this app", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun showPermissionDialog() {
        AlertDialog.Builder(this)
            .setTitle("Permissions Required")
            .setMessage("This app needs various permissions to work properly in the background. Please grant all permissions.")
            .setPositiveButton("Grant") { _, _ ->
                checkAndRequestPermissions()
            }
            .setNegativeButton("Cancel") { _, _ ->
                updatePermissionStatus()
            }
            .show()
    }

    private fun showErrorDialog(title: String, message: String) {
        AlertDialog.Builder(this)
            .setTitle(title)
            .setMessage(message)
            .setPositiveButton("OK") { _, _ -> }
            .show()
    }

    private fun updatePermissionStatus() {
        val allPermissionsGranted = checkAllPermissions()
        
        val statusText = if (allPermissionsGranted) {
            "✅ All permissions granted"
        } else {
            "⚠️ Permissions needed - Tap to grant"
        }
        
        textViewPermissions.text = statusText
        textViewPermissions.setTextColor(
            if (allPermissionsGranted) {
                ContextCompat.getColor(this, android.R.color.holo_green_dark)
            } else {
                ContextCompat.getColor(this, android.R.color.holo_orange_dark)
            }
        )
    }

    override fun onStart() {
        super.onStart()
        updatePermissionStatus()
    }

    override fun onResume() {
        super.onResume()
        updatePermissionStatus()
        
        // Reconnect to service if it's running
        if (serviceStarted && !bound) {
            val bindIntent = Intent(this, GeminiMcpService::class.java)
            bindService(bindIntent, connection, Context.BIND_AUTO_CREATE)
        }
    }

    override fun onPause() {
        super.onPause()
        // Don't unbind here to keep service connected when app goes to background
    }

    override fun onStop() {
        super.onStop()
        // Keep service running in background, just remove callback
        if (bound) {
            geminiMcpService?.removeCallback()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        // Clean up service connection
        if (bound) {
            geminiMcpService?.removeCallback()
            unbindService(connection)
            bound = false
        }
    }

    override fun onBackPressed() {
        // Ask user if they want to continue automation in background
        if (bound && !buttonSend.isEnabled) { // Task is running
            AlertDialog.Builder(this)
                .setTitle("Continue in Background?")
                .setMessage("The automation is still running. Do you want to continue in the background or stop it?")
                .setPositiveButton("Continue in Background") { _, _ ->
                    // Move to background but keep service running
                    moveTaskToBack(true)
                }
                .setNegativeButton("Stop Automation") { _, _ ->
                    stopAutomationTask()
                    super.onBackPressed()
                }
                .setNeutralButton("Cancel") { _, _ ->
                    // Do nothing, stay in app
                }
                .show()
        } else {
            super.onBackPressed()
        }
    }
}



<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">
    
    <!-- Network and Internet Permissions -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
    <uses-permission android:name="android.permission.CHANGE_NETWORK_STATE" />
    
    <!-- Service and Background Operation Permissions -->
    <uses-permission android:name="android.permission.WAKE_LOCK" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
    
    <!-- Battery and Power Management -->
    <uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" />
    <uses-permission android:name="android.permission.DEVICE_POWER" 
        tools:ignore="ProtectedPermissions" />
    
    <!-- Notification Permissions -->
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    
    <!-- Boot and App Restart Permissions -->
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
    <uses-permission android:name="android.permission.QUICKBOOT_POWERON" 
        tools:ignore="ProtectedPermissions" />
    
    <!-- System and Service Management -->
    <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW" />
    <uses-permission android:name="android.permission.WRITE_SETTINGS" 
        tools:ignore="ProtectedPermissions" />

    <application
        android:allowBackup="true"
        android:dataExtractionRules="@xml/data_extraction_rules"
        android:fullBackupContent="@xml/backup_rules"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/AppTheme"
        android:networkSecurityConfig="@xml/network_security_config"
        android:usesCleartextTraffic="true"
        android:requestLegacyExternalStorage="true">
        
        <!-- Main Activity -->
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:theme="@style/AppTheme"
            android:screenOrientation="portrait"
            android:launchMode="singleTop">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        
        <!-- Foreground Service -->
        <service
            android:name=".GeminiMcpService"
            android:enabled="true"
            android:exported="false"
            android:foregroundServiceType="dataSync"
            android:stopWithTask="false" />
        
        <!-- Boot Receiver for Auto-Start -->
        <receiver
            android:name=".BootReceiver"
            android:enabled="true"
            android:exported="true"
            android:permission="android.permission.RECEIVE_BOOT_COMPLETED">
            <intent-filter android:priority="1000">
                <action android:name="android.intent.action.BOOT_COMPLETED" />
                <action android:name="android.intent.action.QUICKBOOT_POWERON" />
                <category android:name="android.intent.category.DEFAULT" />
            </intent-filter>
        </receiver>
        
        <!-- App Restart Receiver -->
        <receiver
            android:name=".RestartReceiver"
            android:enabled="true"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MY_PACKAGE_REPLACED" />
                <action android:name="android.intent.action.PACKAGE_REPLACED" />
                <data android:scheme="package" />
            </intent-filter>
        </receiver>
        
        <!-- Service Watchdog Job (Android 8.0+) -->
        <service
            android:name=".ServiceWatchdogJob"
            android:permission="android.permission.BIND_JOB_SERVICE"
            android:exported="false" />
            
    </application>
</manifest>




<?xml version="1.0" encoding="utf-8"?>
<ScrollView xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:fillViewport="true"
    tools:context=".MainActivity">

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="vertical"
        android:padding="16dp">

        <!-- App Title -->
        <TextView
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:text="Gemini MCP Automation"
            android:textSize="24sp"
            android:textStyle="bold"
            android:gravity="center"
            android:layout_marginBottom="16dp"
            android:textColor="@android:color/black" />

        <!-- Permissions Status -->
        <TextView
            android:id="@+id/textViewPermissions"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:text="Checking permissions..."
            android:textSize="14sp"
            android:padding="12dp"
            android:background="@android:drawable/editbox_background"
            android:layout_marginBottom="16dp"
            android:clickable="true"
            android:focusable="true"
            android:textColor="@android:color/holo_orange_dark" />

        <!-- Query Input -->
        <TextView
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:text="Enter your automation command:"
            android:textSize="16sp"
            android:textStyle="bold"
            android:layout_marginBottom="8dp"
            android:textColor="@android:color/black" />

        <EditText
            android:id="@+id/editTextPrompt"
            android:layout_width="match_parent"
            android:layout_height="120dp"
            android:hint="e.g., 'Open YouTube and search for Android tutorials'"
            android:minLines="4"
            android:maxLines="6"
            android:gravity="top|start"
            android:background="@android:drawable/edit_text"
            android:padding="12dp"
            android:layout_marginBottom="16dp"
            android:textSize="14sp"
            android:inputType="textMultiLine|textCapSentences" />

        <!-- Control Buttons -->
        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:orientation="horizontal"
            android:layout_marginBottom="16dp">

            <Button
                android:id="@+id/buttonSend"
                android:layout_width="0dp"
                android:layout_height="wrap_content"
                android:layout_weight="1"
                android:text="Start Automation"
                android:textSize="16sp"
                android:layout_marginEnd="8dp"
                android:backgroundTint="@android:color/holo_green_dark"
                android:textColor="@android:color/white" />

            <Button
                android:id="@+id/buttonStop"
                android:layout_width="0dp"
                android:layout_height="wrap_content"
                android:layout_weight="1"
                android:text="Stop"
                android:textSize="16sp"
                android:layout_marginStart="8dp"
                android:backgroundTint="@android:color/holo_red_dark"
                android:textColor="@android:color/white"
                android:enabled="false" />

        </LinearLayout>

        <!-- Status Section -->
        <TextView
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:text="Status:"
            android:textSize="16sp"
            android:textStyle="bold"
            android:layout_marginBottom="8dp"
            android:textColor="@android:color/black" />

        <TextView
            android:id="@+id/textViewStatus"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:text="Ready"
            android:textSize="14sp"
            android:textStyle="italic"
            android:layout_marginBottom="16dp"
            android:padding="8dp"
            android:background="@android:color/white"
            android:textColor="@android:color/holo_blue_dark"
            android:drawableStart="@android:drawable/ic_dialog_info"
            android:drawablePadding="8dp" />

        <!-- Response Section -->
        <TextView
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:text="Response:"
            android:textSize="16sp"
            android:textStyle="bold"
            android:layout_marginBottom="8dp"
            android:textColor="@android:color/black" />

        <ScrollView
            android:layout_width="match_parent"
            android:layout_height="200dp"
            android:layout_marginBottom="16dp">

            <TextView
                android:id="@+id/textViewResponse"
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:text=""
                android:textSize="12sp"
                android:background="#f5f5f5"
                android:padding="12dp"
                android:fontFamily="monospace"
                android:textColor="@android:color/black"
                android:scrollbars="vertical" />

        </ScrollView>

        <!-- Instructions -->
        <TextView
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:text="Instructions:\n• Grant all permissions for background operation\n• Disable battery optimization when prompted\n• The automation will continue even if you switch apps\n• Use the notification to return to this app"
            android:textSize="12sp"
            android:textColor="@android:color/darker_gray"
            android:background="@android:color/white"
            android:padding="12dp"
            android:layout_marginTop="8dp" />

    </LinearLayout>
</ScrollView>

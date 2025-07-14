// GeminiMcpService.kt

package com.example.mcpapp

import android.app.*
import android.content.Intent
import android.os.Binder
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
        private const val NOTIFICATION_ID = 1
        private const val CHANNEL_ID = "GeminiMcpServiceChannel"
        private const val CHANNEL_NAME = "Gemini MCP Service"
    }

    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .pingInterval(30, TimeUnit.SECONDS)
        .addNetworkInterceptor { chain ->
            val request = chain.request().newBuilder()
                .addHeader("Connection", "keep-alive")
                .addHeader("Cache-Control", "no-cache")
                .build()
            chain.proceed(request)
        }
        .build()

    private val executor = Executors.newSingleThreadExecutor()
    private val mcpUrl = "http://10.0.2.2:8000/mcp/"

    private val binder = GeminiMcpBinder()
    private lateinit var generativeModel: GenerativeModel
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // Wake lock to prevent system from sleeping
    private lateinit var wakeLock: WakeLock

    private var requestId = 1
    private var pendingRequestId: Int? = null
    private var responseChannel: Channel<String>? = null
    private val isListening = AtomicBoolean(false)
    private val shouldReconnect = AtomicBoolean(true)

    private var currentUserQuery = ""
    private var maxIterations = 15
    private var currentIteration = 0
    private val maxRetries = 3

    private var isProcessing = false

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
            apiKey = "API_KEY"
        )

        // Create notification channel
        createNotificationChannel()

        // Acquire wake lock to prevent system sleep
        val powerManager = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "GeminiMcpService:WakeLock"
        )
        wakeLock.acquire(60*60*1000L /*1 hour*/)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Start as foreground service
        startForeground(NOTIFICATION_ID, createNotification("MCP Service Running"))

        return START_STICKY // Restart service if killed
    }

    override fun onBind(intent: Intent): IBinder {
        return binder
    }

    private fun createNotificationChannel() {
        val serviceChannel = NotificationChannel(
            CHANNEL_ID,
            CHANNEL_NAME,
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Channel for Gemini MCP Service"
            setShowBadge(false)
        }

        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(serviceChannel)
    }

    private fun createNotification(content: String): Notification {
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent, PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("MCP Automation Service")
            .setContentText(content)
            .setSmallIcon(android.R.drawable.ic_menu_info_details)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }

    private fun updateNotification(content: String) {
        val notification = createNotification(content)
        val notificationManager = getSystemService(NotificationManager::class.java)
        notificationManager.notify(NOTIFICATION_ID, notification)
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

        if (isProcessing) {
            callback?.onError("Another query is already being processed")
            return
        }

        isProcessing = true
        currentUserQuery = query
        currentIteration = 0
        shouldReconnect.set(true)

        serviceScope.launch {
            try {
                updateNotification("Processing: $query")
                callback?.onStatusUpdate("Initializing automation...")

                // Start SSE listener first
                startSSEListener()

                // Small delay to ensure connection is established
                delay(2000)

                callback?.onStatusUpdate("Selecting device...")
                selectDevice()
                Log.d("selectDevice", "device selected")

                getToolsList()
                Log.d("getToolsList", "got tools $toolsList")

                startGeminiMcpLoop()
            } catch (e: Exception) {
                isProcessing = false
                updateNotification("Error: ${e.message}")
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
                    put("device", "emulator-5554")
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

            // Wait for response with timeout
            var attempts = 0
            while (attempts < maxRetries) {
                try {
                    val response = responseChannel!!.receive()
                    return@withContext response
                } catch (e: Exception) {
                    attempts++
                    Log.e("GeminiMcpService", "Error waiting for response, attempt $attempts", e)
                    if (attempts < maxRetries) {
                        delay(3000) // Wait before retry
                        restartSSEListener()
                    }
                }
            }
            throw Exception("Failed to receive response after $maxRetries attempts")
        }
    }

    private fun startSSEListener() {
        if (isListening.get()) return

        isListening.set(true)

        executor.execute {
            while (shouldReconnect.get() && !executor.isShutdown) {
                try {
                    val getRequest = Request.Builder()
                        .url(mcpUrl)
                        .get()
                        .header("Cache-Control", "no-cache")
                        .header("Accept", "text/event-stream")
                        .header("Connection", "keep-alive")
                        .build()

                    client.newCall(getRequest).execute().use { response ->
                        if (!response.isSuccessful) {
                            Log.e("MCPService", "❌ Failed SSE connection: ${response.code}")
                            Thread.sleep(5000)
                            return@use
                        }

                        Log.d("MCPService", "✅ SSE connection established")

                        val reader = BufferedReader(InputStreamReader(response.body?.byteStream()))
                        var event: String? = null
                        val dataBuilder = StringBuilder()
                        var line: String?

                        while (reader.readLine().also { line = it } != null && shouldReconnect.get()) {
                            line = line?.trim()
                            when {
                                line!!.startsWith("event:") -> {
                                    event = line!!.removePrefix("event:").trim()
                                }

                                line!!.startsWith("data:") -> {
                                    dataBuilder.append(line!!.removePrefix("data:").trim())
                                }

                                line!!.isEmpty() -> {
                                    val fullData = dataBuilder.toString()
                                    if (event != null && fullData.isNotEmpty()) {
                                        Log.d("SSE_RAW", "event=$event, data=$fullData")

                                        // Handle different event types properly
                                        when (event) {
                                            "endpoint" -> {
                                                // This is session metadata, just log it
                                                Log.d("MCPService", "Session endpoint: $fullData")
                                            }

                                            "message" -> {
                                                // This is the actual JSON response we need
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
                                                    // For malformed JSON in message events, still try to send
                                                    if (pendingRequestId != null) {
                                                        responseChannel?.trySend(fullData)
                                                    }
                                                }
                                            }

                                            "error" -> {
                                                // Handle error events
                                                Log.e("MCPService", "Server error: $fullData")
                                                responseChannel?.trySend(fullData)
                                            }

                                            else -> {
                                                // Unknown event type, log but don't process
                                                Log.d("MCPService", "Unknown event type '$event': $fullData")
                                            }
                                        }

                                        prevResponse = fullData
                                    }
                                    event = null
                                    dataBuilder.setLength(0)
                                }
                            }
                        }
                    }
                } catch (e: Exception) {
                    Log.e("MCPService", "❌ SSE error: ${e.message}")
                    if (shouldReconnect.get()) {
                        Thread.sleep(5000)
                    }
                }
            }
            isListening.set(false)
        }
    }

    private fun restartSSEListener() {
        Log.d("MCPService", "Restarting SSE listener...")
        isListening.set(false)
        Thread.sleep(2000) // Brief pause
        startSSEListener()
    }

    private var fullMcpResponses = ""

    private suspend fun startGeminiMcpLoop() {
        if (currentIteration >= maxIterations) {
            isProcessing = false
            updateNotification("Max iterations reached")
            callback?.onError("Maximum iterations reached. Task may be too complex.")
            return
        }

        currentIteration++
        val statusText = "Processing step $currentIteration of $maxIterations..."
        updateNotification(statusText)
        callback?.onStatusUpdate(statusText)

        val geminiPrompt = createGeminiPrompt()
        Log.d("Gemini", "Prompt: $geminiPrompt")

        try {
            val response = generativeModel.generateContent(geminiPrompt)
            val responseText = response.text ?: ""

            Log.d("GeminiMcpService", "Gemini response: $responseText")

            if (responseText.contains("TASK_COMPLETED") ||
                responseText.contains("\"status\": \"completed\"") ||
                responseText.contains("task is complete")) {
                isProcessing = false
                updateNotification("Task completed successfully")
                callback?.onResponse("Task completed successfully!")
                callback?.onCompleted()
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

                // Add delay between iterations to prevent overwhelming the system
                delay(2000)

                // Continue the loop
                startGeminiMcpLoop()
            } else {
                isProcessing = false
                updateNotification("Error parsing response")
                callback?.onError("Failed to parse Gemini response as JSON: $responseText")
            }

        } catch (e: Exception) {
            isProcessing = false
            updateNotification("Error: ${e.message}")
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
                    delay(3000)
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
        isProcessing = false
        callback = null
        shouldReconnect.set(false)
        isListening.set(false)
        responseChannel?.close()
        executor.shutdown()

        if (::wakeLock.isInitialized && wakeLock.isHeld) {
            wakeLock.release()
        }
    }
}



// MainActivity.kt

package com.example.mcpapp

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.Bundle
import android.os.IBinder
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    private lateinit var editTextPrompt: EditText
    private lateinit var buttonSend: Button
    private lateinit var textViewStatus: TextView
    private lateinit var textViewResponse: TextView

    private var geminiMcpService: GeminiMcpService? = null
    private var bound = false

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
                        buttonSend.isEnabled = true
                    }
                }

                override fun onError(error: String) {
                    runOnUiThread {
                        textViewResponse.text = "Error: $error"
                        textViewStatus.text = "Ready"
                        buttonSend.isEnabled = true
                    }
                }

                override fun onCompleted() {
                    runOnUiThread {
                        textViewStatus.text = "Task completed successfully"
                        buttonSend.isEnabled = true
                    }
                }
            })
        }

        override fun onServiceDisconnected(arg0: ComponentName) {
            bound = false
            geminiMcpService = null
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        editTextPrompt = findViewById(R.id.editTextPrompt)
        buttonSend = findViewById(R.id.buttonSend)
        textViewStatus = findViewById(R.id.textViewStatus)
        textViewResponse = findViewById(R.id.textViewResponse)

        buttonSend.setOnClickListener {
            val prompt = editTextPrompt.text.toString().trim()
            if (prompt.isNotEmpty()) {
                buttonSend.isEnabled = false
                textViewResponse.text = ""
                geminiMcpService?.processUserQuery(prompt)
            }
        }

        // Start the service as a foreground service
        startGeminiMcpService()
    }

    private fun startGeminiMcpService() {
        val serviceIntent = Intent(this, GeminiMcpService::class.java)

        // Start as foreground service
        startForegroundService(serviceIntent)

        // Also bind to it for communication
        bindService(serviceIntent, connection, Context.BIND_AUTO_CREATE)
    }

    override fun onStart() {
        super.onStart()
        if (!bound) {
            val serviceIntent = Intent(this, GeminiMcpService::class.java)
            bindService(serviceIntent, connection, Context.BIND_AUTO_CREATE)
        }
    }

    override fun onStop() {
        super.onStop()
        if (bound) {
            geminiMcpService?.removeCallback()
            unbindService(connection)
            bound = false
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        if (bound) {
            geminiMcpService?.removeCallback()
            unbindService(connection)
            bound = false
        }
    }
}




<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" />
    <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW" />
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />

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
        android:usesCleartextTraffic="true">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:theme="@style/AppTheme">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <service
            android:name=".GeminiMcpService"
            android:enabled="true"
            android:exported="false"
            android:foregroundServiceType="dataSync"
            android:stopWithTask="false" />

    </application>
</manifest>

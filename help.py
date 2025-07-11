package com.example.mcpapp

import android.app.Service
import android.content.Intent
import android.os.Binder
import android.os.IBinder
import android.util.Log
import com.google.ai.client.generativeai.GenerativeModel
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit
import java.util.concurrent.ConcurrentHashMap

class GeminiMcpService : Service() {

    private val binder = GeminiMcpBinder()
    private lateinit var generativeModel: GenerativeModel
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var currentJob: Job? = null

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS) // Increased for longer operations
        .writeTimeout(30, TimeUnit.SECONDS)
        .callTimeout(120, TimeUnit.SECONDS) // Overall call timeout
        .retryOnConnectionFailure(true)
        .build()

    private val mcpBaseUrl = "http://10.0.2.2:8000/mcp"
    private var requestId = 1
    private var toolsList: String = ""
    private val previousMcpResponses = mutableListOf<String>()
    private var currentUserQuery = ""
    private var maxIterations = 10
    private var currentIteration = 0

    // Track pending requests to match responses
    private val pendingRequests = ConcurrentHashMap<Int, (String) -> Unit>()

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

        // Cancel any existing operation
        currentJob?.cancel()

        currentUserQuery = query
        currentIteration = 0
        previousMcpResponses.clear()
        pendingRequests.clear()

        currentJob = serviceScope.launch {
            try {
                callback?.onStatusUpdate("Selecting device...")
                selectDevice()
            } catch (e: CancellationException) {
                Log.d("GeminiMcpService", "Operation cancelled")
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    callback?.onError("Error processing query: ${e.message}")
                }
            }
        }
    }

    fun cancelCurrentOperation() {
        currentJob?.cancel()
        pendingRequests.clear()
        callback?.onStatusUpdate("Operation cancelled")
    }

    private suspend fun selectDevice() {
        val currentRequestId = requestId++
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

        callMCPServer(deviceSelection, currentRequestId) { result ->
            serviceScope.launch {
                if (result.contains("error")) {
                    withContext(Dispatchers.Main) {
                        callback?.onError("Failed to select device: $result")
                    }
                } else {
                    Log.d("GeminiMcpService", "Device selected: $result")
                    withContext(Dispatchers.Main) {
                        callback?.onStatusUpdate("Getting tools list...")
                    }
                    getToolsList()
                }
            }
        }
    }

    private suspend fun getToolsList() {
        val currentRequestId = requestId++
        val toolsListRequest = JSONObject().apply {
            put("jsonrpc", "2.0")
            put("id", currentRequestId)
            put("method", "tools/list")
            put("params", JSONObject())
        }

        callMCPServer(toolsListRequest, currentRequestId) { result ->
            serviceScope.launch {
                if (result.contains("error")) {
                    withContext(Dispatchers.Main) {
                        callback?.onError("Failed to get tools list: $result")
                    }
                } else {
                    toolsList = result
                    Log.d("GeminiMcpService", "Fresh tools list received: $toolsList")
                    withContext(Dispatchers.Main) {
                        callback?.onStatusUpdate("Starting task execution...")
                    }
                    startGeminiMcpLoop()
                }
            }
        }
    }

    private suspend fun startGeminiMcpLoop() {
        if (currentIteration >= maxIterations) {
            withContext(Dispatchers.Main) {
                callback?.onError("Maximum iterations reached. Task may be too complex.")
            }
            return
        }

        currentIteration++
        withContext(Dispatchers.Main) {
            callback?.onStatusUpdate("Processing step $currentIteration...")
        }

        val geminiPrompt = createGeminiPrompt()

        try {
            val response = generativeModel.generateContent(geminiPrompt)
            val responseText = response.text ?: ""

            Log.d("GeminiMcpService", "Gemini response: $responseText")

            if (responseText.contains("TASK_COMPLETED") ||
                responseText.contains("\"status\": \"completed\"") ||
                responseText.contains("task is complete")) {
                
                withContext(Dispatchers.Main) {
                    callback?.onResponse("Task completed successfully!")
                    callback?.onCompleted()
                }
                return
            }

            val jsonResponse = extractJsonFromResponse(responseText)
            if (jsonResponse != null) {
                val currentRequestId = requestId++
                jsonResponse.put("id", currentRequestId) // Ensure fresh ID
                
                callMCPServer(jsonResponse, currentRequestId) { mcpResult ->
                    serviceScope.launch {
                        previousMcpResponses.add(mcpResult)
                        Log.d("GeminiMcpService", "Fresh MCP response: $mcpResult")
                        startGeminiMcpLoop()
                    }
                }
            } else {
                withContext(Dispatchers.Main) {
                    callback?.onError("Failed to parse Gemini response as JSON: $responseText")
                }
            }

        } catch (e: Exception) {
            withContext(Dispatchers.Main) {
                callback?.onError("Error communicating with Gemini: ${e.message}")
            }
        }
    }

    private fun createGeminiPrompt(): String {
        return """
            You are an AI assistant that controls mobile devices through an MCP server.
            Your task is to help execute user queries by calling the appropriate mobile device tools.
            
            AVAILABLE TOOLS:
            $toolsList
            
            USER QUERY: $currentUserQuery
            
            PREVIOUS MCP RESPONSES:
            ${previousMcpResponses.joinToString("\n")}
            
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

    // Improved callMCPServer function with proper coroutine handling
    private fun callMCPServer(params: JSONObject, requestId: Int, callback: (String) -> Unit) {
        // Store the callback for this specific request
        pendingRequests[requestId] = callback
        
        Log.d("GeminiMcpService", "Sending request ID: $requestId")
        
        val body = RequestBody.create("application/json".toMediaTypeOrNull(), params.toString())
        val postRequest = Request.Builder()
            .url("$mcpBaseUrl/")
            .post(body)
            .build()

        client.newCall(postRequest).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                pendingRequests.remove(requestId)
                callback("Error: ${e.message}")
            }

            override fun onResponse(call: Call, response: Response) {
                if (!response.isSuccessful) {
                    pendingRequests.remove(requestId)
                    callback("Error: HTTP ${response.code}")
                    return
                }

                Log.d("GeminiMcpService", "POST successful for request ID: $requestId")
                
                // Start fresh SSE connection for this request
                startFreshSSEConnection(requestId)
            }
        })
    }

    private fun startFreshSSEConnection(requestId: Int) {
        val getRequest = Request.Builder()
            .url("$mcpBaseUrl/")
            .get()
            .addHeader("Accept", "text/event-stream")
            .addHeader("Cache-Control", "no-cache")
            .build()

        serviceScope.launch(Dispatchers.IO) {
            try {
                val call = client.newCall(getRequest)
                
                // Add timeout for the SSE connection
                withTimeout(60000) { // 60 second timeout
                    call.execute().use { sseResponse ->
                        if (!sseResponse.isSuccessful) {
                            withContext(Dispatchers.Main) {
                                val callback = pendingRequests.remove(requestId)
                                callback?.invoke("Error: SSE connection failed with code ${sseResponse.code}")
                            }
                            return@withTimeout
                        }

                        val reader = sseResponse.body?.charStream()?.buffered() ?: run {
                            withContext(Dispatchers.Main) {
                                val callback = pendingRequests.remove(requestId)
                                callback?.invoke("Error: SSE response body is null")
                            }
                            return@withTimeout
                        }

                        processSSEStream(reader, requestId)
                    }
                }
            } catch (e: TimeoutCancellationException) {
                withContext(Dispatchers.Main) {
                    Log.w("GeminiMcpService", "SSE connection timeout for request ID: $requestId")
                    val callback = pendingRequests.remove(requestId)
                    callback?.invoke("Error: SSE connection timeout")
                }
            } catch (e: CancellationException) {
                Log.d("GeminiMcpService", "SSE connection cancelled for request ID: $requestId")
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Log.e("GeminiMcpService", "SSE connection error for request ID $requestId: ${e.message}")
                    val callback = pendingRequests.remove(requestId)
                    callback?.invoke("Error: SSE connection failed: ${e.message}")
                }
            }
        }
    }

    private suspend fun processSSEStream(reader: java.io.BufferedReader, requestId: Int) {
        var event: String? = null
        val dataBuilder = StringBuilder()
        var messageCount = 0
        val maxMessages = 10
        var lastActivity = System.currentTimeMillis()
        val activityTimeout = 30000 // 30 seconds

        while (messageCount < maxMessages && isActive) { // Check if coroutine is still active
            val line = withTimeoutOrNull(5000) { // 5 second timeout per line
                reader.readLine()
            }
            
            if (line == null) {
                if (System.currentTimeMillis() - lastActivity > activityTimeout) {
                    Log.w("GeminiMcpService", "SSE stream inactive for too long")
                    break
                }
                continue
            }
            
            lastActivity = System.currentTimeMillis()
            
            when {
                line.startsWith("event:") -> {
                    event = line.removePrefix("event:").trim()
                }
                line.startsWith("") -> {
                    if (dataBuilder.isNotEmpty()) {
                        dataBuilder.append("\n")
                    }
                    dataBuilder.append(line.removePrefix("").trim())
                }
                line.isEmpty() -> {
                    val fullData = dataBuilder.toString()
                    if (event != null && fullData.isNotEmpty()) {
                        messageCount++
                        Log.d("GeminiMcpService", "SSE Message $messageCount: event=$event, data=$fullData")
                        
                        if (handleSSEMessage(fullData, requestId)) {
                            return // Successfully matched and processed
                        }
                    }
                    
                    // Reset for next message
                    event = null
                    dataBuilder.setLength(0)
                }
            }
        }
        
        // If we reach here, no matching response found
        withContext(Dispatchers.Main) {
            Log.w("GeminiMcpService", "No matching response found for request ID: $requestId")
            val callback = pendingRequests.remove(requestId)
            callback?.invoke("Error: No matching response received")
        }
    }

    private suspend fun handleSSEMessage(fullData: String, requestId: Int): Boolean {
        return try {
            val jsonData = JSONObject(fullData)
            val responseId = jsonData.optInt("id", -1)
            
            if (responseId == requestId) {
                Log.d("GeminiMcpService", "✅ Matched response for request ID: $requestId")
                withContext(Dispatchers.Main) {
                    val callback = pendingRequests.remove(requestId)
                    callback?.invoke(fullData)
                }
                true
            } else {
                Log.d("GeminiMcpService", "⚠️ ID mismatch: expected $requestId, got $responseId")
                false
            }
        } catch (e: Exception) {
            Log.w("GeminiMcpService", "Non-JSON SSE  $fullData")
            withContext(Dispatchers.Main) {
                val callback = pendingRequests.remove(requestId)
                callback?.invoke(fullData)
            }
            true
        }
    }

    private fun checkSystemPermissions(): Boolean {
        return try {
            // Check if we have necessary permissions before attempting system calls
            val context = applicationContext
            val pm = context.packageManager
            
            // Add proper permission checks here if needed
            true
        } catch (e: SecurityException) {
            Log.w("GeminiMcpService", "Insufficient permissions: ${e.message}")
            false
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        
        // Cancel all pending operations
        currentJob?.cancel()
        serviceScope.cancel()
        
        // Clean up resources
        pendingRequests.clear()
        callback = null
        
        // Close HTTP client connections
        client.dispatcher.executorService.shutdown()
        client.connectionPool.evictAll()
    }
}

package com.example.mcpapp

import android.app.Service
import android.content.Intent
import android.os.Binder
import android.os.IBinder
import android.util.Log
import com.google.ai.client.generativeai.GenerativeModel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class GeminiMcpService : Service() {

    private val binder = GeminiMcpBinder()
    private lateinit var generativeModel: GenerativeModel
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // Updated client configuration for SSE support
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS) // infinite read for SSE
        .retryOnConnectionFailure(true)
        .build()

    private val mcpBaseUrl = "http://192.168.1.77:9000/mcp"
    private var requestId = 1
    private var toolsList: String = ""
    private val previousMcpResponses = mutableListOf<String>()
    private var currentUserQuery = ""
    private var maxIterations = 10
    private var currentIteration = 0

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

        currentUserQuery = query
        currentIteration = 0
        previousMcpResponses.clear()

        serviceScope.launch {
            try {
                // Step 1: Select device
                callback?.onStatusUpdate("Selecting device...")
                selectDevice()
            } catch (e: Exception) {
                callback?.onError("Error processing query: ${e.message}")
            }
        }
    }

    private suspend fun selectDevice() {
        val deviceSelection = JSONObject().apply {
            put("jsonrpc", "2.0")
            put("id", requestId++)
            put("method", "tools/call")
            put("params", JSONObject().apply {
                put("name", "mobile_use_device")
                put("arguments", JSONObject().apply {
                    put("device", "emulator-5554")
                    put("deviceType", "android")
                })
            })
        }

        callMCPServer(deviceSelection) { result ->
            serviceScope.launch {
                if (result.contains("error")) {
                    callback?.onError("Failed to select device: $result")
                } else {
                    Log.d("GeminiMcpService", "Device selected: $result")
                    callback?.onStatusUpdate("Getting tools list...")
                    getToolsList()
                }
            }
        }
    }

    private suspend fun getToolsList() {
        val toolsListRequest = JSONObject().apply {
            put("jsonrpc", "2.0")
            put("id", requestId++)
            put("method", "tools/list")
            put("params", JSONObject())
        }

        callMCPServer(toolsListRequest) { result ->
            serviceScope.launch {
                if (result.contains("error")) {
                    callback?.onError("Failed to get tools list: $result")
                } else {
                    toolsList = result // Now this will contain the actual tools data instead of "Accepted"
                    Log.d("GeminiMcpService", "Tools list received: $toolsList")
                    callback?.onStatusUpdate("Starting task execution...")
                    startGeminiMcpLoop()
                }
            }
        }
    }

    private suspend fun startGeminiMcpLoop() {
        if (currentIteration >= maxIterations) {
            callback?.onError("Maximum iterations reached. Task may be too complex.")
            return
        }

        currentIteration++
        callback?.onStatusUpdate("Processing step $currentIteration...")

        val geminiPrompt = createGeminiPrompt()

        try {
            val response = generativeModel.generateContent(geminiPrompt)
            val responseText = response.text ?: ""

            Log.d("GeminiMcpService", "Gemini response: $responseText")

            // Check if Gemini indicates completion
            if (responseText.contains("TASK_COMPLETED") ||
                responseText.contains("\"status\": \"completed\"") ||
                responseText.contains("task is complete")) {
                callback?.onResponse("Task completed successfully!")
                callback?.onCompleted()
                return
            }

            // Try to extract JSON from Gemini response
            val jsonResponse = extractJsonFromResponse(responseText)
            if (jsonResponse != null) {
                // Send to MCP server
                callMCPServer(jsonResponse) { mcpResult ->
                    serviceScope.launch {
                        previousMcpResponses.add(mcpResult)
                        Log.d("GeminiMcpService", "MCP response: $mcpResult")

                        // Continue loop
                        startGeminiMcpLoop()
                    }
                }
            } else {
                callback?.onError("Failed to parse Gemini response as JSON: $responseText")
            }

        } catch (e: Exception) {
            callback?.onError("Error communicating with Gemini: ${e.message}")
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
            {"jsonrpc": "2.0", "id": $requestId, "method": "tools/call", "params": {"name": "tool_name", "arguments": {"param": "value"}}}
            
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
            // Try to find JSON in the response
            val trimmed = response.trim()

            // Look for JSON object boundaries
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

    // Updated callMCPServer function to handle SSE properly
    private fun callMCPServer(params: JSONObject, callback: (String) -> Unit) {
        val body = RequestBody.create("application/json".toMediaTypeOrNull(), params.toString())
        val postRequest = Request.Builder()
            .url("$mcpBaseUrl/")
            .post(body)
            .build()

        client.newCall(postRequest).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback("Error: ${e.message}")
            }

            override fun onResponse(call: Call, response: Response) {
                if (!response.isSuccessful) {
                    callback("Error: HTTP ${response.code}")
                    return
                }

                // After POST is successful, start listening to SSE
                val getRequest = Request.Builder()
                    .url("$mcpBaseUrl/")
                    .get()
                    .build()

                // Execute SSE listening in a new thread to avoid blocking
                Thread {
                    try {
                        client.newCall(getRequest).execute().use { sseResponse ->
                            if (!sseResponse.isSuccessful) {
                                callback("Error: SSE connection failed with code ${sseResponse.code}")
                                return@use
                            }

                            val reader = sseResponse.body?.charStream()?.buffered() ?: run {
                                callback("Error: SSE response body is null")
                                return@use
                            }

                            var event: String? = null
                            val dataBuilder = StringBuilder()

                            while (true) {
                                val line = reader.readLine() ?: break
                                when {
                                    line.startsWith("event:") -> {
                                        event = line.removePrefix("event:").trim()
                                    }
                                    line.startsWith("data:") -> {
                                        dataBuilder.append(line.removePrefix("data:").trim())
                                    }
                                    line.isEmpty() -> {
                                        val fullData = dataBuilder.toString()
                                        if (event != null && fullData.isNotEmpty()) {
                                            Log.d("GeminiMcpService", "SSE Data received: $fullData")
                                            callback(fullData)
                                            return@use // Exit after receiving the first complete SSE message
                                        }
                                        event = null
                                        dataBuilder.setLength(0)
                                    }
                                }
                            }
                        }
                    } catch (e: Exception) {
                        Log.e("GeminiMcpService", "SSE listening failed: ${e.message}")
                        callback("Error: SSE listening failed: ${e.message}")
                    }
                }.start()
            }
        })
    }

    override fun onDestroy() {
        super.onDestroy()
        callback = null
    }
}






private fun callMCPServer(params: JSONObject, callback: (String) -> Unit) {
    val body = RequestBody.create("application/json".toMediaTypeOrNull(), params.toString())
    val postRequest = Request.Builder()
        .url("$mcpBaseUrl/")
        .post(body)
        .build()

    client.newCall(postRequest).enqueue(object : Callback {
        override fun onFailure(call: Call, e: IOException) {
            callback("Error: ${e.message}")
        }

        override fun onResponse(call: Call, response: Response) {
            if (!response.isSuccessful) {
                callback("Error: HTTP ${response.code}")
                return
            }

            // After POST is successful, start listening to SSE
            val getRequest = Request.Builder()
                .url("$mcpBaseUrl/")
                .get()
                .build()

            // Execute SSE listening in a new thread to avoid blocking
            Thread {
                try {
                    client.newCall(getRequest).execute().use { sseResponse ->
                        if (!sseResponse.isSuccessful) {
                            callback("Error: SSE connection failed with code ${sseResponse.code}")
                            return@use
                        }

                        val reader = sseResponse.body?.charStream()?.buffered() ?: run {
                            callback("Error: SSE response body is null")
                            return@use
                        }

                        var event: String? = null
                        val dataBuilder = StringBuilder()

                        while (true) {
                            val line = reader.readLine() ?: break
                            when {
                                line.startsWith("event:") -> {
                                    event = line.removePrefix("event:").trim()
                                }
                                line.startsWith("data:") -> {
                                    dataBuilder.append(line.removePrefix("data:").trim())
                                }
                                line.isEmpty() -> {
                                    val fullData = dataBuilder.toString()
                                    if (event != null && fullData.isNotEmpty()) {
                                        callback(fullData)
                                        return@use // Exit after receiving the first complete SSE message
                                    }
                                    event = null
                                    dataBuilder.setLength(0)
                                }
                            }
                        }
                    }
                } catch (e: Exception) {
                    callback("Error: SSE listening failed: ${e.message}")
                }
            }.start()
        }
    })
}


private val client = OkHttpClient.Builder()
    .connectTimeout(10, TimeUnit.SECONDS)
    .readTimeout(0, TimeUnit.MILLISECONDS) // infinite read for SSE
    .retryOnConnectionFailure(true)
    .build()

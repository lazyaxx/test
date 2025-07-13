class MCPService : Service() {

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS) // infinite read for SSE
        .retryOnConnectionFailure(true)
        .build()

    private val executor = Executors.newSingleThreadExecutor()
    private val mcpUrl = "http://10.0.2.2:8000/mcp/"

    // Track multiple outstanding requests
    private val pendingRequests = ConcurrentHashMap<String, String>()

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        sendJsonRpcRequest("tools/list", JSONObject())
        listenToSSE()
        return START_STICKY
    }

    private fun sendJsonRpcRequest(method: String, params: JSONObject) {
        val requestId = UUID.randomUUID().toString()

        val jsonRequest = JSONObject().apply {
            put("jsonrpc", "2.0")
            put("id", 1)
            put("method", "tools/list")
            put("params", JSONObject().apply{})
        }

        val requestBody = RequestBody.create(
            "application/json".toMediaTypeOrNull(),
            jsonRequest.toString()
        )

        val postRequest = Request.Builder()
            .url(mcpUrl)
            .post(requestBody)
            .build()

        pendingRequests[requestId] = method

        client.newCall(postRequest).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e("MCPService", "❌ JSON-RPC POST failed: ${e.message}")
                pendingRequests.remove(requestId)
            }

            override fun onResponse(call: Call, response: Response) {
                if (response.isSuccessful) {
                    Log.d("MCPService", "✅ Sent method '$method' with id=$requestId")
                } else {
                    Log.e("MCPService", "❌ JSON-RPC error: ${response.code}")
                    pendingRequests.remove(requestId)
                }
            }
        })
    }

    private fun listenToSSE() {
        val getRequest = Request.Builder()
            .url(mcpUrl)
            .get()
            .build()

        executor.execute {
            while (!executor.isShutdown) {
                try {
                    client.newCall(getRequest).execute().use { response ->
                        if (!response.isSuccessful) {
                            Log.e("MCPService", "❌ Failed SSE connection: ${response.code}")
                            Thread.sleep(3000)
                            return@use
                        }

                        val reader = BufferedReader(InputStreamReader(response.body?.byteStream()))
                        var event: String? = null
                        val dataBuilder = StringBuilder()
                        var line: String?

                        while (reader.readLine().also { line = it } != null) {
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
//                                        handleIncomingSSE(event!!, fullData)
                                    }
                                    event = null
                                    dataBuilder.setLength(0)
                                }
                            }
                        }
                    }
                } catch (e: Exception) {
                    Log.e("MCPService", "❌ SSE error: ${e.message}")
                    Thread.sleep(3000)
                }
            }
        }
    }

//    private fun handleIncomingSSE(event: String, data: String) {
//        try {
//            val json = JSONObject(data)
//            val incomingId = json.optString("id", "")
//
//            if (pendingRequests.containsKey(incomingId)) {
//                val method = pendingRequests[incomingId]
//                Log.i("MCPService", "✅ Matched SSE for method='$method', id=$incomingId → result: $data")
//                pendingRequests.remove(incomingId)
//
//                // TODO: Dispatch result to Activity or ViewModel if needed
//            } else {
//                Log.w("MCPService", "⚠️ Unmatched SSE id=$incomingId, ignoring or notify user")
//            }
//        } catch (e: Exception) {
//            Log.e("MCPService", "❌ Failed to parse SSE data: $data")
//        }
//    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        executor.shutdownNow()
        pendingRequests.clear()
        super.onDestroy()
    }
}




Complete Line-by-Line Explanation of GeminiMcpService
This is an Android Background Service that combines Google's Gemini AI with mobile device automation through an MCP (Mobile Control Protocol) server. Let me break down every part for you.

Package Declaration and Imports
kotlin
package com.example.mcpapp
Declares the package name where this class belongs

Standard Android app package structure

kotlin
import android.app.Service
import android.content.Intent
import android.os.Binder
import android.os.IBinder
import android.os.PowerManager
import android.os.PowerManager.WakeLock
import android.util.Log
Service: Base class for background services in Android

Intent: Used to start/communicate with services

Binder/IBinder: Allows other app components to bind to this service

PowerManager/WakeLock: Prevents device from sleeping during operations

Log: Android's logging utility for debugging

kotlin
import com.google.ai.client.generativeai.GenerativeModel
Google's Gemini AI client library for generating AI responses

kotlin
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
Coroutines: Kotlin's way of handling asynchronous operations (like network calls)

Dispatchers: Different thread pools for different types of work

SupervisorJob: Prevents one coroutine failure from canceling others

Channel: Communication mechanism between coroutines

delay: Pauses execution for a specified time

kotlin
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody.Companion.toRequestBody
OkHttp: Popular HTTP client library for making network requests

MediaType/RequestBody: For formatting HTTP requests

kotlin
import org.json.JSONObject
import java.io.BufferedReader
import java.io.IOException
import java.io.InputStreamReader
import java.util.concurrent.TimeUnit
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
JSONObject: For working with JSON data

BufferedReader/InputStreamReader: For reading streaming data

Executors: For managing background threads

AtomicBoolean: Thread-safe boolean operations

Class Declaration and Properties
kotlin
class GeminiMcpService : Service() {
Creates a class that extends Android's Service class

Services run in the background without a user interface

kotlin
private val client = OkHttpClient.Builder()
    .connectTimeout(15, TimeUnit.SECONDS)
    .readTimeout(0, TimeUnit.MILLISECONDS)
    .writeTimeout(15, TimeUnit.SECONDS)
    .retryOnConnectionFailure(true)
    .build()
Creates an HTTP client with specific timeout settings

connectTimeout: How long to wait for connection (15 seconds)

readTimeout: How long to wait for data (0 = infinite for streaming)

writeTimeout: How long to wait when sending data (15 seconds)

retryOnConnectionFailure: Automatically retry failed connections

kotlin
private val executor = Executors.newSingleThreadExecutor()
private val mcpUrl = "http://10.0.2.2:8080/mcp/"
executor: Creates a single background thread for network operations

mcpUrl: The server URL (10.0.2.2 is the special IP for Android emulator to access localhost)

kotlin
private val binder = GeminiMcpBinder()
private lateinit var generativeModel: GenerativeModel
private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
binder: Object that allows other components to communicate with this service

generativeModel: Will hold the Gemini AI model (lateinit means "initialize later")

serviceScope: Coroutine scope for background operations

kotlin
private lateinit var wakeLock: WakeLock
wakeLock: Prevents the device from going to sleep during operations

kotlin
private var requestId = 1
private var pendingRequestId: Int? = null
private var responseChannel: Channel<String>? = null
private val isListening = AtomicBoolean(false)
private val shouldReconnect = AtomicBoolean(true)
requestId: Unique identifier for each request (starts at 1)

pendingRequestId: Tracks which request we're waiting for a response to

responseChannel: Communication channel for receiving responses

isListening: Thread-safe flag to track if we're listening for responses

shouldReconnect: Thread-safe flag to control reconnection attempts

kotlin
private var currentUserQuery = ""
private var maxIterations = 15
private var currentIteration = 0
private val maxRetries = 3
currentUserQuery: Stores the user's current question/request

maxIterations: Maximum number of AI-server interactions (prevents infinite loops)

currentIteration: Tracks current iteration number

maxRetries: Maximum retry attempts for failed operations

Interface and Inner Class
kotlin
interface GeminiMcpCallback {
    fun onStatusUpdate(status: String)
    fun onResponse(response: String)
    fun onError(error: String)
    fun onCompleted()
}
Interface: Defines methods that other components must implement

These methods allow the service to communicate back to the UI:

onStatusUpdate: Reports progress

onResponse: Sends results

onError: Reports errors

onCompleted: Signals task completion

kotlin
private var callback: GeminiMcpCallback? = null
Stores reference to the callback object (nullable because it might not be set)

kotlin
inner class GeminiMcpBinder : Binder() {
    fun getService(): GeminiMcpService = this@GeminiMcpService
}
Inner class: Class defined inside another class

Binder: Allows other components to get a reference to this service

this@GeminiMcpService: Refers to the outer class instance

Service Lifecycle Methods
kotlin
override fun onCreate() {
    super.onCreate()
    generativeModel = GenerativeModel(
        modelName = "gemini-2.5-flash",
        apiKey = "API_KEY"
    )
onCreate: Called when service is first created

super.onCreate(): Calls parent class's onCreate method

GenerativeModel: Initializes the Gemini AI model with API key

kotlin
    val powerManager = getSystemService(POWER_SERVICE) as PowerManager
    wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "GeminiMcpService:WakeLock")
    wakeLock.acquire(10*60*1000L /*10 minutes*/)
}
getSystemService: Gets Android system service

PowerManager: Service that manages device power states

newWakeLock: Creates a wake lock to prevent sleep

PARTIAL_WAKE_LOCK: Keeps CPU running but allows screen to turn off

acquire: Activates the wake lock for 10 minutes

kotlin
override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
    return START_STICKY // Restart service if killed
}
onStartCommand: Called when service is started

START_STICKY: Tells Android to restart the service if it's killed

kotlin
override fun onBind(intent: Intent): IBinder {
    return binder
}
onBind: Called when another component binds to this service

Returns the binder object for communication

Public Methods for External Interaction
kotlin
fun setCallback(callback: GeminiMcpCallback) {
    this.callback = callback
}

fun removeCallback() {
    this.callback = null
}
setCallback: Allows external components to register for updates

removeCallback: Clears the callback reference

kotlin
fun processUserQuery(query: String) {
    if (query.isBlank()) {
        callback?.onError("Query cannot be empty")
        return
    }

    currentUserQuery = query
    currentIteration = 0
    shouldReconnect.set(true)
processUserQuery: Main method to start processing a user's request

isBlank(): Checks if string is empty or only whitespace

callback?.onError: Calls onError if callback is not null (safe call operator)

return: Exits the function early if query is empty

Resets iteration counter and enables reconnection

kotlin
    serviceScope.launch {
        try {
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
            callback?.onError("Error processing query: ${e.message}")
            Log.e("GeminiMcpService", "Error in processUserQuery", e)
        }
    }
}
serviceScope.launch: Starts a coroutine in the background

try-catch: Handles any exceptions that might occur

startSSEListener(): Starts listening for server responses

delay(2000): Waits 2 seconds for connection to stabilize

selectDevice(): Selects the target device for automation

getToolsList(): Gets available tools from the server

startGeminiMcpLoop(): Starts the main AI interaction loop

Log.d/Log.e: Debug and error logging

Device Selection and Tools
kotlin
private suspend fun selectDevice() {
    val currentRequestId = requestId++
    pendingRequestId = currentRequestId
suspend: Indicates this function can be paused and resumed (coroutine function)

requestId++: Increments request ID and uses the previous value

pendingRequestId: Stores the ID we're waiting for a response to

kotlin
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
JSONObject().apply: Creates JSON object and applies the code block to it

put(): Adds key-value pairs to the JSON object

Creates a JSON-RPC request to select an Android emulator device

kotlin
    sendJsonRpcRequestWithRetry(deviceSelection)
    waitForResponse()
    pendingRequestId = null
}
sendJsonRpcRequestWithRetry: Sends the request with retry logic

waitForResponse(): Waits for the server's response

pendingRequestId = null: Clears the pending request ID

kotlin
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
prevResponse: Stores the previous server response

toolsList: Stores the list of available tools

getToolsList(): Requests and stores the available tools from the server

Similar structure to selectDevice but requests tools list instead

Response Handling
kotlin
private suspend fun waitForResponse(): String {
    return withContext(Dispatchers.IO) {
        responseChannel = Channel(Channel.UNLIMITED)
withContext: Switches to IO dispatcher for network operations

Channel(Channel.UNLIMITED): Creates channel with unlimited buffer size

kotlin
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
                    delay(2000) // Wait before retry
                    restartSSEListener()
                }
            }
        }
        throw Exception("Failed to receive response after $maxRetries attempts")
    }
}
while loop: Retries up to maxRetries times

responseChannel!!.receive(): Receives response from channel (!! assumes it's not null)

return@withContext: Returns from the withContext block

restartSSEListener(): Restarts the connection if there's an error

throw Exception: Throws an exception if all retries fail

Server-Sent Events (SSE) Listener
kotlin
private fun startSSEListener() {
    if (isListening.get()) return

    isListening.set(true)
isListening.get(): Gets the current value of the atomic boolean

return: Exits if already listening

isListening.set(true): Sets the listening flag to true

kotlin
    executor.execute {
        while (shouldReconnect.get() && !executor.isShutdown) {
            try {
                val getRequest = Request.Builder()
                    .url(mcpUrl)
                    .get()
                    .build()
executor.execute: Runs code in the background thread

while loop: Continues while reconnection is enabled and executor isn't shut down

Request.Builder: Creates an HTTP GET request to the MCP server

kotlin
                client.newCall(getRequest).execute().use { response ->
                    if (!response.isSuccessful) {
                        Log.e("MCPService", "❌ Failed SSE connection: ${response.code}")
                        Thread.sleep(3000)
                        return@use
                    }

                    Log.d("MCPService", "✅ SSE connection established")
newCall().execute(): Makes the HTTP request

use: Automatically closes the response when done

isSuccessful: Checks if HTTP status is 200-299

Thread.sleep(3000): Waits 3 seconds before retrying

return@use: Returns from the use block

kotlin
                    val reader = BufferedReader(InputStreamReader(response.body?.byteStream()))
                    var event: String? = null
                    val dataBuilder = StringBuilder()
                    var line: String?
BufferedReader: Reads text from the response stream

InputStreamReader: Converts byte stream to character stream

StringBuilder: Efficiently builds strings

event: Stores the current SSE event type

line: Stores each line read from the stream

kotlin
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
                                // Process complete SSE message
                                val fullData = dataBuilder.toString()
                                if (event != null && fullData.isNotEmpty()) {
                                    // Handle different event types
                                    when (event) {
                                        "endpoint" -> {
                                            Log.d("MCPService", "Session endpoint: $fullData")
                                        }
                                        "message" -> {
                                            // Process actual responses
                                            try {
                                                val responseJson = JSONObject(fullData)
                                                val responseId = responseJson.optInt("id", -1)

                                                if (pendingRequestId != null && responseId == pendingRequestId) {
                                                    Log.d("MCPService", "✅ Received response for request $responseId")
                                                    responseChannel?.trySend(fullData)
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
                                    }
                                }
                                // Reset for next message
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
This complex section handles Server-Sent Events (SSE) - a way for servers to push real-time data to clients:

readLine(): Reads each line from the server stream

when expression: Kotlin's version of switch/case

startsWith(): Checks if line starts with specific text

removePrefix(): Removes the prefix from the string

StringBuilder.append(): Adds text to the string builder

isEmpty(): Checks if line is empty (indicates end of SSE message)

optInt(): Gets integer value from JSON, returns -1 if not found

trySend(): Attempts to send data through the channel

setLength(0): Clears the StringBuilder

AI Integration Loop
kotlin
private suspend fun startGeminiMcpLoop() {
    if (currentIteration >= maxIterations) {
        callback?.onError("Maximum iterations reached. Task may be too complex.")
        return
    }

    currentIteration++
    callback?.onStatusUpdate("Processing step $currentIteration of $maxIterations...")
startGeminiMcpLoop: Main loop that coordinates AI and server interactions

Checks if maximum iterations reached to prevent infinite loops

Increments iteration counter and updates status

kotlin
    val geminiPrompt = createGeminiPrompt()
    Log.d("Gemini", "Prompt: $geminiPrompt")

    try {
        val response = generativeModel.generateContent(geminiPrompt)
        val responseText = response.text ?: ""

        Log.d("GeminiMcpService", "Gemini response: $responseText")
createGeminiPrompt(): Creates the prompt for the AI

generateContent(): Sends prompt to Gemini AI and gets response

?: "": Elvis operator - uses empty string if response.text is null

kotlin
        if (responseText.contains("TASK_COMPLETED") ||
            responseText.contains("\"status\": \"completed\"") ||
            responseText.contains("task is complete")) {
            callback?.onResponse("Task completed successfully!")
            callback?.onCompleted()
            return
        }
Checks if AI indicates the task is completed

contains(): Checks if string contains specific text

||: Logical OR operator

Calls completion callbacks if task is done

kotlin
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

            delay(1000)
            startGeminiMcpLoop()
        } else {
            callback?.onError("Failed to parse Gemini response as JSON: $responseText")
        }
extractJsonFromResponse(): Extracts JSON from AI response

if (jsonResponse != null): Checks if JSON extraction was successful

+=: Adds new response to accumulated responses

delay(1000): Waits 1 second between iterations

startGeminiMcpLoop(): Recursively calls itself to continue the loop

Network Request Methods
kotlin
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
                delay(2000)
            }
        }
    }
    throw Exception("Failed to send request after $maxRetries attempts")
}
sendJsonRpcRequestWithRetry: Wrapper that adds retry logic

while loop: Retries up to maxRetries times

sendJsonRpcRequest(): Actual method that sends the request

return: Exits successfully if request succeeds

attempts++: Increments attempt counter

throw Exception: Throws exception if all retries fail

kotlin
private fun sendJsonRpcRequest(params: JSONObject) {
    val requestBody = params.toString()
        .toRequestBody("application/json".toMediaTypeOrNull())

    val postRequest = Request.Builder()
        .url(mcpUrl)
        .post(requestBody)
        .build()
params.toString(): Converts JSON object to string

toRequestBody(): Converts string to HTTP request body

toMediaTypeOrNull(): Sets content type to JSON

Request.Builder: Creates HTTP POST request

kotlin
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
enqueue(): Sends request asynchronously

object : Callback: Creates anonymous object implementing Callback interface

onFailure: Called if request fails

onResponse: Called when response is received

response.use: Automatically closes response when done

AI Prompt Creation
kotlin
private fun createGeminiPrompt(): String {
    return """
        You are an AI assistant that controls mobile devices through an MCP server.
        Your task is to help execute user queries by calling the appropriate mobile device tools.
        
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
        - For YouTube search: click on search field, type "Titanic", then select first video result
    """.trimIndent()
}
""": Triple-quoted string for multi-line text

$toolsList: String interpolation - inserts variable value

trimIndent(): Removes common indentation from multi-line strings

Creates detailed instructions for the AI to follow

Utility Methods
text
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
extractJsonFromResponse: Extracts JSON from AI response text

trim(): Removes whitespace from beginning and end

indexOf('{')/lastIndexOf('}'): Finds first { and last } characters

!= -1: Checks if characters were found (-1 means not found)

substring(): Extracts portion of string between specified indices

try-catch: Handles parsing errors gracefully

return null: Returns null if parsing fails

Service Cleanup
text
override fun onDestroy() {
    super.onDestroy()
    callback = null
    shouldReconnect.set(false)
    isListening.set(false)
    responseChannel?.close()
    executor.shutdown()

    if (wakeLock.isHeld) {
        wakeLock.release()
    }
}
onDestroy: Called when service is being destroyed

super.onDestroy(): Calls parent class cleanup

callback = null: Clears callback reference

shouldReconnect.set(false): Stops reconnection attempts

isListening.set(false): Stops listening for responses

responseChannel?.close(): Closes communication channel

executor.shutdown(): Stops the background thread

wakeLock.isHeld: Checks if wake lock is still active

wakeLock.release(): Releases the wake lock to allow device sleep

Summary
This service creates a sophisticated automation system that:

Connects to an MCP server for device control

Uses Google's Gemini AI to understand user requests

Implements real-time communication through Server-Sent Events

Provides retry logic for network failures

Manages device power to prevent sleep during operations

Communicates with UI through callback interface

Handles complex multi-step tasks through iterative AI interactions

The service essentially acts as a bridge between human language (user queries) and mobile device automation, using AI to determine what actions to take and then executing them through the MCP server.

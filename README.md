implementation 'com.squareup.okhttp3:okhttp-sse:4.12.0'



import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources

private fun callMCPServer(params: JSONObject, callback: (String) -> Unit) {
    // First, make the POST request to initiate the operation
    val requestBody = RequestBody.create("application/json".toMediaTypeOrNull(), params.toString())
    val postRequest = Request.Builder()
        .url("$mcpBaseUrl/")
        .post(requestBody)
        .build()

    client.newCall(postRequest).enqueue(object : Callback {
        override fun onFailure(call: Call, e: IOException) {
            callback("Error: ${e.message}")
        }

        override fun onResponse(call: Call, response: Response) {
            val responseBody = response.body?.string() ?: "No response"
            Log.d("GeminiMcpService", "POST response: $responseBody")
            
            // Now listen to the SSE stream for the actual data
            listenToSSEStream(callback)
        }
    })
}

private fun listenToSSEStream(callback: (String) -> Unit) {
    val sseRequest = Request.Builder()
        .url(mcpBaseUrl) // Same URL but for SSE
        .header("Accept", "text/event-stream")
        .header("Cache-Control", "no-cache")
        .build()

    val eventSourceListener = object : EventSourceListener() {
        private var hasReceivedData = false
        
        override fun onOpen(eventSource: EventSource, response: Response) {
            Log.d("GeminiMcpService", "SSE connection opened")
        }

        override fun onEvent(eventSource: EventSource, id: String?, type: String?, data: String) {
            Log.d("GeminiMcpService", "SSE event received - type: $type, data: $data")
            
            if (type == "message" && data.isNotEmpty()) {
                hasReceivedData = true
                callback(data)
                eventSource.cancel() // Close the connection after receiving data
            }
        }

        override fun onFailure(eventSource: EventSource, t: Throwable?, response: Response?) {
            Log.e("GeminiMcpService", "SSE connection failed: ${t?.message}")
            if (!hasReceivedData) {
                callback("Error: ${t?.message}")
            }
        }

        override fun onClosed(eventSource: EventSource) {
            Log.d("GeminiMcpService", "SSE connection closed")
        }
    }

    EventSources.createFactory(client).newEventSource(sseRequest, eventSourceListener)
}

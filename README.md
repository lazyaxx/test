private fun callMCPServerSSE(params: JSONObject, callback: (String) -> Unit) {
    if (activeMcpUrl == null) {
        callback("Error: No active MCP server connection")
        return
    }
    
    val body = RequestBody.create("application/json".toMediaTypeOrNull(), params.toString())
    val request = Request.Builder()
        .url("$activeMcpUrl/")
        .post(body)
        .addHeader("Content-Type", "application/json")
        .addHeader("Accept", "text/event-stream")
        .addHeader("Cache-Control", "no-cache")
        .build()
    
    Log.d("GeminiMcpService", "📤 Sending SSE request: ${params.toString()}")
    
    client.newCall(request).enqueue(object : Callback {
        override fun onFailure(call: Call, e: IOException) {
            Log.e("GeminiMcpService", "❌ SSE Request failed: ${e.message}")
            callback("Error: ${e.message}")
        }
        
        override fun onResponse(call: Call, response: Response) {
            try {
                Log.d("GeminiMcpService", "📥 SSE Response received: ${response.code}")
                
                if (response.isSuccessful) {
                    // Don't read response.body?.string() - it only gets "Accepted"
                    // Instead, read the streaming data
                    readSSEStream(response, callback)
                } else {
                    callback("Error: HTTP ${response.code} - ${response.message}")
                }
            } catch (e: Exception) {
                Log.e("GeminiMcpService", "Error processing SSE response", e)
                callback("Error: SSE processing failed - ${e.message}")
            }
        }
    })
}

private fun readSSEStream(response: Response, callback: (String) -> Unit) {
    try {
        val responseBody = response.body
        if (responseBody == null) {
            callback("Error: No response body")
            return
        }
        
        val source = responseBody.source()
        val buffer = StringBuilder()
        var dataFound = false
        
        Log.d("GeminiMcpService", "📖 Reading SSE stream...")
        
        // Read line by line from the stream
        while (!source.exhausted()) {
            val line = source.readUtf8Line()
            if (line == null) break
            
            Log.d("GeminiMcpService", "📄 Stream line: '$line'")
            
            when {
                line.startsWith(" ") -> {
                    val data = line.substring(6).trim()
                    if (data.isNotEmpty()) {
                        buffer.append(data)
                        dataFound = true
                        Log.d("GeminiMcpService", "📦 Found  $data")
                    }
                }
                line.isEmpty() && dataFound -> {
                    // End of SSE event - process accumulated data
                    val result = buffer.toString()
                    if (result.isNotEmpty() && isValidJSON(result)) {
                        Log.d("GeminiMcpService", "✅ Complete SSE  $result")
                        callback(result)
                        return
                    }
                    buffer.clear()
                    dataFound = false
                }
                line.startsWith("event: ") -> {
                    val eventType = line.substring(7).trim()
                    Log.d("GeminiMcpService", "🎯 Event type: $eventType")
                }
            }
        }
        
        // Handle case where stream ends without empty line
        if (dataFound && buffer.isNotEmpty()) {
            val result = buffer.toString()
            if (isValidJSON(result)) {
                Log.d("GeminiMcpService", "✅ Final SSE  $result")
                callback(result)
            } else {
                callback("Error: Invalid JSON in SSE stream: $result")
            }
        } else {
            callback("Error: No valid data received from SSE stream")
        }
        
    } catch (e: Exception) {
        Log.e("GeminiMcpService", "Error reading SSE stream", e)
        callback("Error: Failed to read SSE stream - ${e.message}")
    } finally {
        response.close()
    }
}

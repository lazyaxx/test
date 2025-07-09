private fun callMCPServer(params: JSONObject, callback: (String) -> Unit) {
    if (activeMcpUrl == null) {
        callback("Error: No active MCP server connection")
        return
    }
    
    val body = RequestBody.create("application/json".toMediaTypeOrNull(), params.toString())
    val request = Request.Builder()
        .url("$activeMcpUrl/")
        .post(body)
        .addHeader("Content-Type", "application/json")
        .addHeader("Accept", "text/event-stream, application/json") // Accept SSE
        .build()
    
    Log.d("GeminiMcpService", "📤 Sending request: ${params.toString()}")
    
    client.newCall(request).enqueue(object : Callback {
        override fun onFailure(call: Call, e: IOException) {
            Log.e("GeminiMcpService", "❌ Request failed: ${e.message}")
            callback("Error: ${e.message}")
        }
        
        override fun onResponse(call: Call, response: Response) {
            try {
                val responseBody = response.body?.string()
                
                Log.d("GeminiMcpService", "📥 Raw response: $responseBody")
                
                if (response.isSuccessful && !responseBody.isNullOrEmpty()) {
                    // Check if it's SSE format
                    if (responseBody.contains("event:") && responseBody.contains("")) {
                        val extractedData = extractDataFromSSE(responseBody)
                        if (extractedData != null) {
                            Log.d("GeminiMcpService", "✅ Extracted SSE  $extractedData")
                            callback(extractedData)
                        } else {
                            callback("Error: Failed to extract data from SSE response")
                        }
                    } else {
                        // Regular JSON response
                        callback(responseBody)
                    }
                } else {
                    callback("Error: HTTP ${response.code} - ${response.message}")
                }
            } catch (e: Exception) {
                Log.e("GeminiMcpService", "Error processing response", e)
                callback("Error: Failed to process response - ${e.message}")
            } finally {
                response.close()
            }
        }
    })
}

private fun extractDataFromSSE(sseResponse: String): String? {
    return try {
        val lines = sseResponse.split("\n")
        val dataLines = mutableListOf<String>()
        
        for (line in lines) {
            if (line.startsWith(" ")) {
                val data = line.substring(6) // Remove " " prefix
                dataLines.add(data)
            }
        }
        
        // Join all data lines (in case data spans multiple lines)
        val combinedData = dataLines.joinToString("")
        
        Log.d("GeminiMcpService", "Extracted  $combinedData")
        
        // Validate it's valid JSON
        if (combinedData.isNotEmpty() && (combinedData.startsWith("{") || combinedData.startsWith("["))) {
            combinedData
        } else {
            null
        }
    } catch (e: Exception) {
        Log.e("GeminiMcpService", "Failed to extract SSE data", e)
        null
    }
}




private fun callMCPServer(params: JSONObject, callback: (String) -> Unit) {
    if (activeMcpUrl == null) {
        callback("Error: No active MCP server connection")
        return
    }
    
    val body = RequestBody.create("application/json".toMediaTypeOrNull(), params.toString())
    val request = Request.Builder()
        .url("$activeMcpUrl/")
        .post(body)
        .addHeader("Content-Type", "application/json")
        .addHeader("Accept", "text/event-stream, application/json")
        .addHeader("Cache-Control", "no-cache")
        .build()
    
    Log.d("GeminiMcpService", "📤 Sending request: ${params.toString()}")
    
    client.newCall(request).enqueue(object : Callback {
        override fun onFailure(call: Call, e: IOException) {
            callback("Error: ${e.message}")
        }
        
        override fun onResponse(call: Call, response: Response) {
            try {
                val responseBody = response.body?.string()
                
                if (response.isSuccessful && !responseBody.isNullOrEmpty()) {
                    val result = parseServerResponse(responseBody)
                    callback(result)
                } else {
                    callback("Error: HTTP ${response.code} - ${response.message}")
                }
            } catch (e: Exception) {
                callback("Error: ${e.message}")
            } finally {
                response.close()
            }
        }
    })
}

private fun parseServerResponse(response: String): String {
    return when {
        // Handle SSE format
        response.contains("event:") && response.contains("") -> {
            parseSSEResponse(response)
        }
        // Handle regular JSON
        response.trim().startsWith("{") || response.trim().startsWith("[") -> {
            response
        }
        // Handle other formats
        else -> {
            Log.w("GeminiMcpService", "Unknown response format: $response")
            response
        }
    }
}

private fun parseSSEResponse(sseData: String): String {
    val events = sseData.split("\n\n") // Split by double newline (event separator)
    
    for (event in events) {
        val lines = event.split("\n")
        var eventType: String? = null
        val dataLines = mutableListOf<String>()
        
        for (line in lines) {
            when {
                line.startsWith("event: ") -> {
                    eventType = line.substring(7).trim()
                }
                line.startsWith(" ") -> {
                    dataLines.add(line.substring(6))
                }
            }
        }
        
        // Process 'message' events (adjust event type as needed)
        if (eventType == "message" || eventType == null) {
            val data = dataLines.joinToString("\n")
            if (data.isNotEmpty()) {
                Log.d("GeminiMcpService", "📋 SSE Event: $eventType, Data: $data")
                return data
            }
        }
    }
    
    return "Error: No valid data found in SSE response"
}




private fun parseSSEResponse(sseData: String): String {
    try {
        Log.d("GeminiMcpService", "🔍 Parsing SSE: $sseData")
        
        // Split by double newline to separate events
        val events = sseData.split(Regex("\n\n|\r\n\r\n"))
        
        for (event in events) {
            if (event.trim().isEmpty()) continue
            
            val lines = event.split(Regex("\n|\r\n"))
            var eventType: String? = null
            val dataLines = mutableListOf<String>()
            
            for (line in lines) {
                val trimmedLine = line.trim()
                when {
                    trimmedLine.startsWith("event:") -> {
                        eventType = trimmedLine.substring(6).trim()
                    }
                    trimmedLine.startsWith("") -> {
                        val data = trimmedLine.substring(5).trim()
                        dataLines.add(data)
                    }
                }
            }
            
            if (dataLines.isNotEmpty()) {
                val combinedData = dataLines.joinToString("")
                
                // Validate it's proper JSON
                if (isValidJSON(combinedData)) {
                    Log.d("GeminiMcpService", "✅ Valid JSON extracted: $combinedData")
                    return combinedData
                } else {
                    Log.w("GeminiMcpService", "⚠️ Invalid JSON: $combinedData")
                }
            }
        }
        
        return "Error: No valid JSON data found in SSE response"
    } catch (e: Exception) {
        Log.e("GeminiMcpService", "Failed to parse SSE response", e)
        return "Error: SSE parsing failed - ${e.message}"
    }
}

private fun isValidJSON( String): Boolean {
    return try {
        if (data.trim().startsWith("{")) {
            JSONObject(data)
            true
        } else if (data.trim().startsWith("[")) {
            org.json.JSONArray(data)
            true
        } else {
            false
        }
    } catch (e: Exception) {
        false
    }
}



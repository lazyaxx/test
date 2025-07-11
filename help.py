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
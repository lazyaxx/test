import android.util.Log
import okhttp3.*
import java.io.BufferedReader
import java.io.InputStreamReader

fun startSSEStream() {
    val client = OkHttpClient.Builder()
        .retryOnConnectionFailure(true)
        .build()

    val request = Request.Builder()
        .url("http://10.0.2.2:8000/mcp/") // Change to your actual SSE URL
        .header("Accept", "text/event-stream")
        .build()

    client.newCall(request).enqueue(object : Callback {
        override fun onFailure(call: Call, e: IOException) {
            Log.e("SSE", "Failed to connect: ${e.message}")
        }

        override fun onResponse(call: Call, response: Response) {
            try {
                val inputStream = response.body?.byteStream()
                val reader = BufferedReader(InputStreamReader(inputStream))

                var line: String?
                val dataBuffer = StringBuilder()

                while (reader.readLine().also { line = it } != null) {
                    Log.d("SSE_RAW", "Line: $line")

                    // Collect data lines (ignoring event: or empty lines)
                    if (line!!.startsWith("data:")) {
                        val json = line.removePrefix("data:").trim()
                        Log.d("SSE_DATA", "Received JSON: $json")

                        // TODO: Parse and use the JSON here
                        // Example: sendToMCP(json)
                    }
                }

            } catch (e: Exception) {
                Log.e("SSE", "Error reading SSE: ${e.message}")
            }
        }
    })
}
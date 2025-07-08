package com.example.mcpapp

import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.util.Log
import com.google.ai.client.generativeai.GenerativeModel
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class GeminiMCPService : Service() {

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .build()

    private lateinit var generativeModel: GenerativeModel
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val mcpBaseUrl = "http://10.0.2.2:8000/mcp"

    override fun onCreate() {
        super.onCreate()
        generativeModel = GenerativeModel(
            modelName = "gemini-pro",
            apiKey = BuildConfig.apiKey
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val userPrompt = intent?.getStringExtra("user_prompt") ?: return START_NOT_STICKY

        serviceScope.launch {
            try {
                // Step 1: Fetch tools list
                val toolsListJson = JSONObject().apply {
                    put("jsonrpc", "2.0")
                    put("id", 1)
                    put("method", "tools/list")
                    put("params", JSONObject())
                }

                val toolsList = callMCP(toolsListJson)
                if (toolsList.contains("error", true)) {
                    stopSelf()
                    return@launch
                }

                // Step 2: Ask Gemini for tasks
                val promptForTasks = """
                    Below is the tools list:
                    $toolsList
                    
                    Based on the following user prompt, generate a list of atomic tasks (one per line) specifying the tool and intent.
                    
                    User prompt: $userPrompt
                """.trimIndent()

                val tasksResponse = generativeModel.generateContent(promptForTasks)
                val tasksText = tasksResponse.text ?: ""
                val tasksList = tasksText.lines().filter { it.isNotBlank() }

                var prevResponse = ""
                for (task in tasksList) {
                    // Step 3: Ask Gemini for JSON to execute the task
                    val promptForJson = """
                        Tools list: $toolsList
                        
                        Now just give the JSON output to execute the following task:
                        "$task"
                        
                        Previous MCP response: $prevResponse
                        
                        The output should ONLY be JSON, no explanation.
                    """.trimIndent()

                    val jsonOutput = generativeModel.generateContent(promptForJson).text ?: ""
                    val jsonRequest = try {
                        JSONObject(jsonOutput)
                    } catch (e: Exception) {
                        stopSelf()
                        return@launch
                    }

                    val response = callMCP(jsonRequest)
                    prevResponse = response

                    if (response.contains("failed", true) || response.contains("error", true)) {
                        Log.e("GeminiMCPService", "Task failed: $task\n$response")
                        stopSelf()
                        return@launch
                    }
                }

                Log.i("GeminiMCPService", "All tasks completed successfully")
            } catch (e: Exception) {
                Log.e("GeminiMCPService", "Exception: ${e.message}")
            } finally {
                stopSelf()
            }
        }

        return START_NOT_STICKY
    }

    private suspend fun callMCP(json: JSONObject): String = withContext(Dispatchers.IO) {
        val body = RequestBody.create("application/json".toMediaTypeOrNull(), json.toString())
        val request = Request.Builder()
            .url("$mcpBaseUrl/")
            .post(body)
            .build()

        return@withContext suspendCancellableCoroutine { cont ->
            client.newCall(request).enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) {
                    cont.resume("Error: ${e.message}", null)
                }

                override fun onResponse(call: Call, response: Response) {
                    cont.resume(response.body?.string() ?: "No response", null)
                }
            })
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
    }
}


package com.example.mcpapp

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    private lateinit var editTextPrompt: EditText
    private lateinit var buttonSend: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        editTextPrompt = findViewById(R.id.editTextPrompt)
        buttonSend = findViewById(R.id.buttonSend)

        buttonSend.setOnClickListener {
            val prompt = editTextPrompt.text.toString()
            if (prompt.isNotBlank()) {
                val intent = Intent(this, GeminiMCPService::class.java).apply {
                    putExtra("user_prompt", prompt)
                }
                startService(intent)
            }
        }
    }
}


<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools"
    android:id="@+id/layout_main"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:padding="24dp"
    android:orientation="vertical"
    android:gravity="center"
    tools:context=".MainActivity">

    <TextView
        android:id="@+id/textViewTitle"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Enter your prompt"
        android:textSize="18sp"
        android:layout_marginBottom="12dp" />

    <EditText
        android:id="@+id/editTextPrompt"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:hint="Type your request..."
        android:minLines="3"
        android:gravity="top"
        android:background="@android:drawable/edit_text"
        android:padding="12dp"
        android:textSize="16sp" />

    <Button
        android:id="@+id/buttonSend"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="Send"
        android:layout_marginTop="16dp"
        android:textAllCaps="false"
        android:padding="12dp" />

    <ProgressBar
        android:id="@+id/progressBar"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_marginTop="24dp"
        android:visibility="gone" />

</LinearLayout>

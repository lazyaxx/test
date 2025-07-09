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
        .addHeader("Accept", "application/json")
        .build()
    
    client.newCall(request).enqueue(object : Callback {
        override fun onFailure(call: Call, e: IOException) {
            callback("Error: ${e.message}")
        }
        
        override fun onResponse(call: Call, response: Response) {
            try {
                val responseBody = response.body?.string()
                
                if (response.isSuccessful) {
                    if (responseBody != null && responseBody.isNotEmpty()) {
                        Log.d("GeminiMcpService", "MCP Response: $responseBody")
                        callback(responseBody)
                    } else {
                        callback("Error: Empty response body")
                    }
                } else {
                    Log.e("GeminiMcpService", "HTTP Error: ${response.code} - ${response.message}")
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




package com.example.testmcpapp

import android.app.Service
import android.content.Intent
import android.os.Binder
import android.os.IBinder
import com.google.ai.client.generativeai.GenerativeModel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class GeminiService : Service() {
    
    private val binder = GeminiBinder()
    private lateinit var generativeModel: GenerativeModel
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    
    // Interface for communication with activity
    interface GeminiCallback {
        fun onResponse(response: String)
        fun onError(error: String)
        fun onStarted()
    }
    
    private var callback: GeminiCallback? = null
    
    inner class GeminiBinder : Binder() {
        fun getService(): GeminiService = this@GeminiService
    }
    
    override fun onCreate() {
        super.onCreate()
        // Initialize Gemini model
        generativeModel = GenerativeModel(
            modelName = "gemini-pro",
            apiKey = BuildConfig.apiKey
        )
    }
    
    override fun onBind(intent: Intent): IBinder {
        return binder
    }
    
    // Method to set callback for communication
    fun setCallback(callback: GeminiCallback) {
        this.callback = callback
    }
    
    // Method to remove callback
    fun removeCallback() {
        this.callback = null
    }
    
    // Method to send prompt to Gemini
    fun sendPrompt(prompt: String) {
        if (prompt.isBlank()) {
            callback?.onError("Prompt cannot be empty")
            return
        }
        
        // Notify that processing started
        callback?.onStarted()
        
        // Make API call in background
        serviceScope.launch {
            try {
                val response = generativeModel.generateContent(prompt)
                val responseText = response.text ?: "No response received"
                callback?.onResponse(responseText)
            } catch (e: Exception) {
                callback?.onError("Error: ${e.message}")
            }
        }
    }
    
    override fun onDestroy() {
        super.onDestroy()
        callback = null
    }
}



package com.example.testmcpapp

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.Bundle
import android.os.IBinder
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity(), GeminiService.GeminiCallback {
    
    private lateinit var editTextPrompt: EditText
    private lateinit var buttonSend: Button
    private lateinit var textViewResponse: TextView
    
    private var geminiService: GeminiService? = null
    private var isBound = false
    
    // Service connection
    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            val binder = service as GeminiService.GeminiBinder
            geminiService = binder.getService()
            geminiService?.setCallback(this@MainActivity)
            isBound = true
            
            // Enable the button once service is connected
            buttonSend.isEnabled = true
            buttonSend.text = "Send to Gemini"
        }
        
        override fun onServiceDisconnected(name: ComponentName?) {
            geminiService?.removeCallback()
            geminiService = null
            isBound = false
            buttonSend.isEnabled = false
        }
    }
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        
        // Initialize views
        editTextPrompt = findViewById(R.id.editTextPrompt)
        buttonSend = findViewById(R.id.buttonSend)
        textViewResponse = findViewById(R.id.textViewResponse)
        
        // Initially disable button until service connects
        buttonSend.isEnabled = false
        buttonSend.text = "Connecting..."
        
        // Set button click listener
        buttonSend.setOnClickListener {
            sendPromptToGemini()
        }
        
        // Start and bind to service
        startAndBindService()
    }
    
    private fun startAndBindService() {
        val intent = Intent(this, GeminiService::class.java)
        startService(intent) // Start the service
        bindService(intent, serviceConnection, Context.BIND_AUTO_CREATE) // Bind to service
    }
    
    private fun sendPromptToGemini() {
        val prompt = editTextPrompt.text.toString().trim()
        
        if (prompt.isEmpty()) {
            Toast.makeText(this, "Please enter a prompt", Toast.LENGTH_SHORT).show()
            return
        }
        
        if (isBound) {
            geminiService?.sendPrompt(prompt)
        } else {
            Toast.makeText(this, "Service not connected", Toast.LENGTH_SHORT).show()
        }
    }
    
    // Callback methods from GeminiService
    override fun onResponse(response: String) {
        runOnUiThread {
            textViewResponse.text = response
            buttonSend.isEnabled = true
            buttonSend.text = "Send to Gemini"
        }
    }
    
    override fun onError(error: String) {
        runOnUiThread {
            textViewResponse.text = error
            buttonSend.isEnabled = true
            buttonSend.text = "Send to Gemini"
            Toast.makeText(this@MainActivity, error, Toast.LENGTH_LONG).show()
        }
    }
    
    override fun onStarted() {
        runOnUiThread {
            buttonSend.isEnabled = false
            buttonSend.text = "Sending..."
            textViewResponse.text = "Processing your request..."
        }
    }
    
    override fun onDestroy() {
        super.onDestroy()
        if (isBound) {
            geminiService?.removeCallback()
            unbindService(serviceConnection)
            isBound = false
        }
    }
}



<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">
    
    <uses-permission android:name="android.permission.INTERNET" />

    <application
        android:allowBackup="true"
        android:dataExtractionRules="@xml/data_extraction_rules"
        android:fullBackupContent="@xml/backup_rules"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.AppCompat.Light.DarkActionBar"
        tools:targetApi="31">
        
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:theme="@style/Theme.AppCompat.Light.DarkActionBar">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        
        <!-- Add the Gemini Service -->
        <service
            android:name=".GeminiService"
            android:enabled="true"
            android:exported="false" />
        
    </application>
</manifest>

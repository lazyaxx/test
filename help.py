<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.example.testmcpapp">

    <uses-permission android:name="android.permission.INTERNET" />

    <application
        android:allowBackup="true"
        android:label="@string/app_name"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.TestMcpApp">
        <activity android:name=".MainActivity">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>



<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:orientation="vertical"
    android:padding="24dp"
    android:layout_width="match_parent"
    android:layout_height="match_parent">

    <EditText
        android:id="@+id/promptInput"
        android:hint="Type your prompt here"
        android:layout_width="match_parent"
        android:layout_height="wrap_content" />

    <Button
        android:id="@+id/sendButton"
        android:text="Send"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_marginTop="16dp" />

    <ProgressBar
        android:id="@+id/progressBar"
        android:visibility="gone"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_gravity="center"
        android:layout_marginTop="16dp" />

    <TextView
        android:id="@+id/responseText"
        android:text=""
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:layout_marginTop="24dp" />
</LinearLayout>


package com.example.testmcpapp

import android.os.Bundle
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import com.google.ai.client.generativeai.GenerativeModel
import kotlinx.coroutines.*
import kotlin.coroutines.CoroutineContext

class MainActivity : AppCompatActivity(), CoroutineScope {
    private lateinit var promptInput: EditText
    private lateinit var sendButton: Button
    private lateinit var responseText: TextView
    private lateinit var progressBar: ProgressBar

    // Replace with your Gemini API key from Google AI Studio
    private val apiKey = "YOUR_GEMINI_API_KEY"

    private val job = Job()
    override val coroutineContext: CoroutineContext
        get() = Dispatchers.Main + job

    override fun onDestroy() {
        super.onDestroy()
        job.cancel()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        promptInput = findViewById(R.id.promptInput)
        sendButton = findViewById(R.id.sendButton)
        responseText = findViewById(R.id.responseText)
        progressBar = findViewById(R.id.progressBar)

        sendButton.setOnClickListener {
            val prompt = promptInput.text.toString().trim()
            if (prompt.isNotEmpty()) {
                sendPromptToGemini(prompt)
            } else {
                Toast.makeText(this, "Please enter a prompt", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun sendPromptToGemini(prompt: String) {
        progressBar.visibility = View.VISIBLE
        responseText.text = ""
        sendButton.isEnabled = false

        launch {
            try {
                val model = GenerativeModel(
                    modelName = "gemini-pro",
                    apiKey = apiKey
                )
                val response = withContext(Dispatchers.IO) {
                    model.generateContent(prompt)
                }
                responseText.text = response.text
            } catch (e: Exception) {
                responseText.text = "Error: ${e.message}"
            } finally {
                progressBar.visibility = View.GONE
                sendButton.isEnabled = true
            }
        }
    }
}




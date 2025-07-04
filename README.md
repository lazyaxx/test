dependencies {
    implementation("com.google.ai.client.generativeai:generativeai:0.9.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    
    // Your existing dependencies will remain here
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
}


sdk.dir=YOUR_SDK_PATH
apiKey=YOUR_GEMINI_API_KEY_HERE


android {
    // ... your existing configuration
    
    buildFeatures {
        buildConfig = true
    }
    
    defaultConfig {
        // ... your existing config
        
        val properties = java.util.Properties()
        properties.load(project.rootProject.file("local.properties").inputStream())
        buildConfigField("String", "API_KEY", "\"${properties.getProperty("apiKey")}\"")
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
        android:theme="@style/Theme.McpAppTest"
        tools:targetApi="31">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>

</manifest>


<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="16dp">

    <TextView
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="Gemini AI Chat"
        android:textSize="24sp"
        android:textStyle="bold"
        android:gravity="center"
        android:layout_marginBottom="20dp" />

    <EditText
        android:id="@+id/editTextPrompt"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:hint="Enter your prompt here..."
        android:minLines="3"
        android:gravity="top"
        android:layout_marginBottom="16dp" />

    <Button
        android:id="@+id/buttonSend"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="Send to Gemini"
        android:layout_marginBottom="16dp" />

    <ProgressBar
        android:id="@+id/progressBar"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_gravity="center"
        android:visibility="gone" />

    <ScrollView
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1">

        <TextView
            android:id="@+id/textViewResponse"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:text="Response will appear here..."
            android:textSize="16sp"
            android:padding="8dp"
            android:background="@android:color/white"
            android:textColor="@android:color/black" />

    </ScrollView>

</LinearLayout>



package com.example.mcpapptest

import androidx.appcompat.app.AppCompatActivity
import android.os.Bundle
import android.view.View
import android.widget.*
import com.google.ai.client.generativeai.GenerativeModel
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {
    
    private lateinit var editTextPrompt: EditText
    private lateinit var buttonSend: Button
    private lateinit var textViewResponse: TextView
    private lateinit var progressBar: ProgressBar
    private lateinit var generativeModel: GenerativeModel
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        
        // Initialize views
        editTextPrompt = findViewById(R.id.editTextPrompt)
        buttonSend = findViewById(R.id.buttonSend)
        textViewResponse = findViewById(R.id.textViewResponse)
        progressBar = findViewById(R.id.progressBar)
        
        // Initialize Gemini model
        generativeModel = GenerativeModel(
            modelName = "gemini-1.5-flash",
            apiKey = BuildConfig.API_KEY
        )
        
        // Set button click listener
        buttonSend.setOnClickListener {
            val prompt = editTextPrompt.text.toString().trim()
            if (prompt.isNotEmpty()) {
                sendPromptToGemini(prompt)
            } else {
                Toast.makeText(this, "Please enter a prompt", Toast.LENGTH_SHORT).show()
            }
        }
    }
    
    private fun sendPromptToGemini(prompt: String) {
        // Show loading state
        progressBar.visibility = View.VISIBLE
        buttonSend.isEnabled = false
        textViewResponse.text = "Generating response..."
        
        // Launch coroutine for API call
        MainScope().launch {
            try {
                // Make API call on background thread
                val response = withContext(Dispatchers.IO) {
                    generativeModel.generateContent(prompt)
                }
                
                // Update UI on main thread
                textViewResponse.text = response.text ?: "No response received"
                
            } catch (e: Exception) {
                // Handle errors
                textViewResponse.text = "Error: ${e.message}"
                Toast.makeText(this@MainActivity, "Failed to get response", Toast.LENGTH_LONG).show()
            } finally {
                // Hide loading state
                progressBar.visibility = View.GONE
                buttonSend.isEnabled = true
            }
        }
    }
}



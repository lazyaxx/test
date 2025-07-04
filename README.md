<resources xmlns:tools="http://schemas.android.com/tools">
    <style name="Theme.TestMcpApp" parent="Theme.MaterialComponents.DayNight.DarkActionBar">
        <!-- Primary brand color -->
        <item name="colorPrimary">@color/purple_500</item>
        <item name="colorPrimaryVariant">@color/purple_700</item>
        <item name="colorOnPrimary">@color/white</item>
        
        <!-- Secondary brand color -->
        <item name="colorSecondary">@color/teal_200</item>
        <item name="colorSecondaryVariant">@color/teal_700</item>
        <item name="colorOnSecondary">@color/black</item>
        
        <!-- Status bar color -->
        <item name="android:statusBarColor" tools:targetApi="l">?attr/colorPrimaryVariant</item>
    </style>
</resources>




<resources xmlns:tools="http://schemas.android.com/tools">
    <!-- Change this line -->
    <style name="Theme.TestMCPApp" parent="Theme.AppCompat.DayNight.DarkActionBar">
        <item name="colorPrimary">@color/purple_500</item>
        <item name="colorPrimaryVariant">@color/purple_700</item>
        <item name="colorOnPrimary">@color/white</item>
        <item name="colorSecondary">@color/teal_200</item>
        <item name="colorSecondaryVariant">@color/teal_700</item>
        <item name="colorOnSecondary">@color/black</item>
    </style>
</resources>


import androidx.appcompat.app.AppCompatActivity
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import com.google.ai.client.generativeai.GenerativeModel
import kotlinx.coroutines.launch


dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.activity:activity-compose:1.8.2")
    implementation("androidx.compose.ui:ui:1.5.4")
    implementation("androidx.compose.ui:ui-tooling-preview:1.5.4")
    implementation("androidx.compose.material3:material3:1.1.2")
    
    // Add this line for Gemini API
    implementation("com.google.ai.client.generativeai:generativeai:0.7.0")
    
    // For network calls
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
}

<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">

    <!-- Add this line -->
    <uses-permission android:name="android.permission.INTERNET" />

    <application
        android:allowBackup="true"
        android:dataExtractionRules="@xml/data_extraction_rules"
        android:fullBackupContent="@xml/backup_rules"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.TestMCPApp"
        tools:targetApi="31">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:theme="@style/Theme.TestMCPApp">
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
        android:layout_marginBottom="24dp" />

    <EditText
        android:id="@+id/editTextPrompt"
        android:layout_width="match_parent"
        android:layout_height="120dp"
        android:hint="Enter your prompt here..."
        android:gravity="top"
        android:inputType="textMultiLine"
        android:background="@drawable/edit_text_background"
        android:padding="12dp"
        android:layout_marginBottom="16dp" />

    <Button
        android:id="@+id/buttonSend"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="Send to Gemini"
        android:textSize="16sp"
        android:layout_marginBottom="16dp" />

    <ProgressBar
        android:id="@+id/progressBar"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_gravity="center"
        android:visibility="gone"
        android:layout_marginBottom="16dp" />

    <ScrollView
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1">

        <TextView
            android:id="@+id/textViewResponse"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:text="Response will appear here..."
            android:textSize="14sp"
            android:padding="12dp"
            android:background="@drawable/response_background" />

    </ScrollView>

</LinearLayout>


<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android">
    <solid android:color="@android:color/white" />
    <stroke android:width="1dp" android:color="#CCCCCC" />
    <corners android:radius="8dp" />
</shape>


<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android">
    <solid android:color="#F5F5F5" />
    <stroke android:width="1dp" android:color="#E0E0E0" />
    <corners android:radius="8dp" />
</shape>


package com.example.testmcpapp

import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.google.ai.client.generativeai.GenerativeModel
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var editTextPrompt: EditText
    private lateinit var buttonSend: Button
    private lateinit var textViewResponse: TextView
    private lateinit var progressBar: ProgressBar
    
    // Replace "YOUR_API_KEY_HERE" with your actual Gemini API key
    private val apiKey = "YOUR_API_KEY_HERE"
    
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
            modelName = "gemini-pro",
            apiKey = apiKey
        )

        // Set button click listener
        buttonSend.setOnClickListener {
            sendPromptToGemini()
        }
    }

    private fun sendPromptToGemini() {
        val prompt = editTextPrompt.text.toString().trim()
        
        if (prompt.isEmpty()) {
            Toast.makeText(this, "Please enter a prompt", Toast.LENGTH_SHORT).show()
            return
        }

        if (apiKey == "YOUR_API_KEY_HERE") {
            Toast.makeText(this, "Please add your Gemini API key in MainActivity.kt", Toast.LENGTH_LONG).show()
            return
        }

        // Show loading state
        progressBar.visibility = View.VISIBLE
        buttonSend.isEnabled = false
        textViewResponse.text = "Generating response..."

        // Make API call using coroutine
        lifecycleScope.launch {
            try {
                val response = generativeModel.generateContent(prompt)
                val responseText = response.text ?: "No response received"
                
                // Update UI on main thread
                runOnUiThread {
                    textViewResponse.text = responseText
                    progressBar.visibility = View.GONE
                    buttonSend.isEnabled = true
                }
                
            } catch (e: Exception) {
                // Handle error
                runOnUiThread {
                    textViewResponse.text = "Error: ${e.message}"
                    progressBar.visibility = View.GONE
                    buttonSend.isEnabled = true
                    Toast.makeText(this@MainActivity, "Error occurred: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }
}


private val apiKey = "YOUR_API_KEY_HERE"


<resources xmlns:tools="http://schemas.android.com/tools">
    <style name="Theme.TestMCPApp" parent="Theme.AppCompat.DayNight.DarkActionBar">
        <item name="colorPrimary">@color/purple_500</item>
        <item name="colorPrimaryVariant">@color/purple_700</item>
        <item name="colorOnPrimary">@color/white</item>
        <item name="colorSecondary">@color/teal_200</item>
        <item name="colorSecondaryVariant">@color/teal_700</item>
        <item name="colorOnSecondary">@color/black</item>
    </style>
</resources>

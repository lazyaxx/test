plugins {
    id 'com.android.application' version '8.4.0' apply false
    id 'org.jetbrains.kotlin.android' version '2.0.0' apply false
}


plugins {
    id 'com.android.application'
    id 'org.jetbrains.kotlin.android'
}

android {
    namespace 'com.example.testmcpapp'
    compileSdk 34

    defaultConfig {
        applicationId "com.example.testmcpapp"
        minSdk 34
        targetSdk 34

        // forward the key from local.properties
        buildConfigField "String", "GEMINI_API_KEY",
                "\"${properties['geminiApiKey']}\""
    }

    buildTypes {
        release {
            minifyEnabled false
            proguardFiles getDefaultProguardFile(
                    'proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }
}

dependencies {
    // Google Generative AI SDK (text-only models)
    implementation "com.google.ai.client:generativeai:0.9.0"   // latest as of July 2025 [17]

    // Kotlin coroutines for easy background work
    implementation "org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1"

    // Material components for UI (already added by template)
    implementation 'com.google.android.material:material:1.12.0'
}



<manifest package="com.example.testmcpapp"
          xmlns:android="http://schemas.android.com/apk/res/android">

    <!-- Internet permission is mandatory for HTTP calls -->
    <uses-permission android:name="android.permission.INTERNET"/>

    <application
        android:allowBackup="true"
        android:label="Gemini Demo"
        android:theme="@style/Theme.Material3.DayNight.NoActionBar">
        <activity android:name=".MainActivity"
                  android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>



<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout
  xmlns:android="http://schemas.android.com/apk/res/android"
  xmlns:app="http://schemas.android.com/apk/res-auto"
  android:layout_width="match_parent"
  android:layout_height="match_parent"
  android:padding="16dp">

    <com.google.android.material.textfield.TextInputLayout
        android:id="@+id/tilPrompt"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent">

        <com.google.android.material.textfield.TextInputEditText
            android:id="@+id/etPrompt"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:hint="Ask Gemini…" />
    </com.google.android.material.textfield.TextInputLayout>

    <Button
        android:id="@+id/btnSend"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Send"
        app:layout_constraintTop_toBottomOf="@id/tilPrompt"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />

    <ProgressBar
        android:id="@+id/progress"
        style="?android:attr/progressBarStyle"
        android:visibility="gone"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        app:layout_constraintTop_toBottomOf="@id/btnSend"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent"/>

    <ScrollView
        android:id="@+id/scroll"
        android:layout_width="0dp"
        android:layout_height="0dp"
        app:layout_constraintTop_toBottomOf="@id/progress"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent">

        <TextView
            android:id="@+id/tvAnswer"
            android:padding="8dp"
            android:textAppearance="?attr/textAppearanceBodyLarge"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"/>
    </ScrollView>

</androidx.constraintlayout.widget.ConstraintLayout>



package com.example.testmcpapp

import android.os.Bundle
import android.view.inputmethod.EditorInfo
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import com.example.testmcpapp.databinding.ActivityMainBinding
import com.google.ai.client.generativeai.GenerativeModel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val uiScope = CoroutineScope(Job() + Dispatchers.Main)

    // Initialise Gemini once. BuildConfig constant was injected from local.properties
    private val gemini = GenerativeModel(
        modelName = "gemini-pro",           // text→text model [17]
        apiKey = BuildConfig.GEMINI_API_KEY // already safe-loaded
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnSend.setOnClickListener { sendPrompt() }

        // optional: hit “done” on soft-keyboard
        binding.etPrompt.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                sendPrompt(); true
            } else false
        }
    }

    private fun sendPrompt() {
        val prompt = binding.etPrompt.text.toString().trim()
        if (prompt.isEmpty()) {
            Toast.makeText(this, "Please type something", Toast.LENGTH_SHORT).show()
            return
        }

        binding.progress.isVisible = true
        binding.tvAnswer.text = ""

        uiScope.launch {
            try {
                // Network call on IO dispatcher
                val response = withContext(Dispatchers.IO) {
                    gemini.generateContent(prompt)
                }
                binding.tvAnswer.text = response.text ?: "No answer 🤷"
            } catch (e: Exception) {
                binding.tvAnswer.text = "Error: ${e.localizedMessage}"
            } finally {
                binding.progress.isVisible = false
            }
        }
    }
}





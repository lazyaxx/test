Based on your project structure, here's exactly where to put each piece of code. Since you're using Kotlin, I'll provide both the file locations and mention that you can mix Java and Kotlin files in the same project.

Project Structure Mapping
1. AndroidManifest.xml
Location: manifests/AndroidManifest.xml

Replace the content with:

xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">

    <!-- Add these permissions -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />

    <application
        android:allowBackup="true"
        android:dataExtractionRules="@xml/data_extraction_rules"
        android:fullBackupContent="@xml/backup_rules"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:networkSecurityConfig="@xml/network_security_config"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.TestMcpApp"
        tools:targetApi="31">
        
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        
        <!-- Add the service -->
        <service
            android:name=".MobileControlService"
            android:enabled="true"
            android:exported="false"
            android:foregroundServiceType="dataSync" />
    </application>
</manifest>
2. Gradle Dependencies
Location: gradle scripts/build.gradle (Module: app)

Add these dependencies in the dependencies block:

text
dependencies {
    implementation 'androidx.core:core-ktx:1.10.1'
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'com.google.android.material:material:1.9.0'
    implementation 'androidx.constraintlayout:constraintlayout:2.1.4'
    
    // For HTTP requests
    implementation 'com.squareup.okhttp3:okhttp:4.11.0'
    implementation 'com.squareup.retrofit2:retrofit:2.9.0'
    implementation 'com.squareup.retrofit2:converter-gson:2.9.0'
    
    // For JSON handling
    implementation 'com.google.code.gson:gson:2.10.1'
    
    // For async operations
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3'
    
    testImplementation 'junit:junit:4.13.2'
    androidTestImplementation 'androidx.test.ext:junit:1.1.5'
    androidTestImplementation 'androidx.test.espresso:espresso-core:3.5.1'
}
3. MainActivity.kt
Location: kotlin+java/com.example.testmcpapp/MainActivity.kt

Replace your existing MainActivity.kt with:

kotlin
package com.example.testmcpapp

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    private lateinit var commandInput: EditText
    private lateinit var executeButton: Button
    private lateinit var statusText: TextView
    private lateinit var logText: TextView
    private val logBuilder = StringBuilder()
    
    private val statusReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            val status = intent?.getStringExtra("status")
            status?.let {
                statusText.text = "Status: $it"
            }
        }
    }
    
    private val logReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            val log = intent?.getStringExtra("log")
            log?.let {
                logBuilder.append(it).append("\n")
                logText.text = logBuilder.toString()
            }
        }
    }
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        
        initializeViews()
        setupClickListeners()
        
        logBuilder.append("App started. Ready to process commands.\n")
        logText.text = logBuilder.toString()
    }
    
    private fun initializeViews() {
        commandInput = findViewById(R.id.commandInput)
        executeButton = findViewById(R.id.executeButton)
        statusText = findViewById(R.id.statusText)
        logText = findViewById(R.id.logText)
    }
    
    private fun setupClickListeners() {
        executeButton.setOnClickListener {
            val command = commandInput.text.toString().trim()
            if (command.isNotEmpty()) {
                executeCommand(command)
                commandInput.setText("")
            }
        }
    }
    
    private fun executeCommand(command: String) {
        val serviceIntent = Intent(this, MobileControlService::class.java)
        serviceIntent.putExtra("command", command)
        startForegroundService(serviceIntent)
        
        statusText.text = "Status: Processing command..."
        logBuilder.append("User command: $command\n")
        logText.text = logBuilder.toString()
    }
    
    override fun onResume() {
        super.onResume()
        registerReceiver(statusReceiver, IntentFilter("com.example.testmcpapp.STATUS_UPDATE"))
        registerReceiver(logReceiver, IntentFilter("com.example.testmcpapp.LOG_UPDATE"))
    }
    
    override fun onPause() {
        super.onPause()
        unregisterReceiver(statusReceiver)
        unregisterReceiver(logReceiver)
    }
}
4. Create New Java Files
Since you're mixing Kotlin and Java, create these Java files in: kotlin+java/com.example.testmcpapp/

Right-click on com.example.testmcpapp → New → Java Class

MobileControlService.java
java
package com.example.testmcpapp;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import android.util.Log;

import androidx.core.app.NotificationCompat;

import com.example.testmcpapp.models.GeminiRequest;
import com.example.testmcpapp.models.JsonRpcRequest;
import com.example.testmcpapp.models.JsonRpcResponse;
import com.example.testmcpapp.network.GeminiApiService;
import com.example.testmcpapp.network.McpApiService;
import com.google.gson.Gson;
import com.google.gson.JsonObject;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public class MobileControlService extends Service {
    private static final String TAG = "MobileControlService";
    private static final String CHANNEL_ID = "MobileControlChannel";
    private static final int NOTIFICATION_ID = 1;
    
    private McpApiService mcpApiService;
    private GeminiApiService geminiApiService;
    private ExecutorService executorService;
    private Gson gson;
    
    // Replace with your actual Gemini API key
    private static final String GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE";
    
    // Replace with your laptop's IP address where MCP server is running
    private static final String MCP_SERVER_URL = "http://192.168.1.100:3000";
    
    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
        
        gson = new Gson();
        executorService = Executors.newSingleThreadExecutor();
        
        // Initialize MCP API service
        Retrofit mcpRetrofit = new Retrofit.Builder()
                .baseUrl(MCP_SERVER_URL)
                .addConverterFactory(GsonConverterFactory.create())
                .build();
        mcpApiService = mcpRetrofit.create(McpApiService.class);
        
        // Initialize Gemini API service
        Retrofit geminiRetrofit = new Retrofit.Builder()
                .baseUrl("https://generativelanguage.googleapis.com/")
                .addConverterFactory(GsonConverterFactory.create())
                .build();
        geminiApiService = geminiRetrofit.create(GeminiApiService.class);
    }
    
    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String command = intent.getStringExtra("command");
        
        Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("Mobile Control Service")
                .setContentText("Processing command: " + command)
                .setSmallIcon(R.drawable.ic_launcher_foreground)
                .build();
        
        startForeground(NOTIFICATION_ID, notification);
        
        if (command != null) {
            processCommand(command);
        }
        
        return START_STICKY;
    }
    
    private void processCommand(String userCommand) {
        Log.d(TAG, "Processing command: " + userCommand);
        getAvailableTools(userCommand);
    }
    
    private void getAvailableTools(String userCommand) {
        JsonRpcRequest request = new JsonRpcRequest(1, "tools/list", new Object());
        
        mcpApiService.sendJsonRpc(request).enqueue(new Callback<JsonRpcResponse>() {
            @Override
            public void onResponse(Call<JsonRpcResponse> call, Response<JsonRpcResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    JsonRpcResponse mcpResponse = response.body();
                    Log.d(TAG, "Available tools: " + gson.toJson(mcpResponse.result));
                    consultGemini(userCommand, mcpResponse.result);
                } else {
                    Log.e(TAG, "Failed to get tools from MCP server");
                    broadcastStatus("Error: Failed to connect to MCP server");
                }
            }
            
            @Override
            public void onFailure(Call<JsonRpcResponse> call, Throwable t) {
                Log.e(TAG, "MCP server connection failed", t);
                broadcastStatus("Error: MCP server connection failed - " + t.getMessage());
            }
        });
    }
    
    private void consultGemini(String userCommand, JsonObject availableTools) {
        String prompt = buildGeminiPrompt(userCommand, availableTools);
        GeminiRequest request = new GeminiRequest(prompt);
        
        geminiApiService.generateContent(request, GEMINI_API_KEY).enqueue(new Callback<JsonObject>() {
            @Override
            public void onResponse(Call<JsonObject> call, Response<JsonObject> response) {
                if (response.isSuccessful() && response.body() != null) {
                    JsonObject geminiResponse = response.body();
                    Log.d(TAG, "Gemini response: " + gson.toJson(geminiResponse));
                    
                    String actionJson = extractActionFromGeminiResponse(geminiResponse);
                    if (actionJson != null) {
                        executeAction(actionJson, userCommand);
                    } else {
                        broadcastStatus("Error: Could not understand the command");
                    }
                } else {
                    Log.e(TAG, "Gemini API call failed");
                    broadcastStatus("Error: Failed to process command with AI");
                }
            }
            
            @Override
            public void onFailure(Call<JsonObject> call, Throwable t) {
                Log.e(TAG, "Gemini API call failed", t);
                broadcastStatus("Error: AI service unavailable - " + t.getMessage());
            }
        });
    }
    
    private String buildGeminiPrompt(String userCommand, JsonObject availableTools) {
        return String.format(
            "You are a mobile device controller. The user wants to: '%s'\n\n" +
            "Available tools: %s\n\n" +
            "Please analyze the user command and respond with a JSON-RPC call to execute the appropriate tool. " +
            "Your response should be in this exact format:\n" +
            "{\n" +
            "  \"jsonrpc\": \"2.0\",\n" +
            "  \"id\": 2,\n" +
            "  \"method\": \"tools/call\",\n" +
            "  \"params\": {\n" +
            "    \"name\": \"tool_name\",\n" +
            "    \"arguments\": {}\n" +
            "  }\n" +
            "}\n\n" +
            "Only respond with the JSON, no other text.",
            userCommand, gson.toJson(availableTools)
        );
    }
    
    private String extractActionFromGeminiResponse(JsonObject geminiResponse) {
        try {
            return geminiResponse
                .getAsJsonArray("candidates")
                .get(0).getAsJsonObject()
                .getAsJsonObject("content")
                .getAsJsonArray("parts")
                .get(0).getAsJsonObject()
                .get("text").getAsString().trim();
        } catch (Exception e) {
            Log.e(TAG, "Failed to extract action from Gemini response", e);
            return null;
        }
    }
    
    private void executeAction(String actionJson, String originalCommand) {
        try {
            JsonRpcRequest actionRequest = gson.fromJson(actionJson, JsonRpcRequest.class);
            
            mcpApiService.sendJsonRpc(actionRequest).enqueue(new Callback<JsonRpcResponse>() {
                @Override
                public void onResponse(Call<JsonRpcResponse> call, Response<JsonRpcResponse> response) {
                    if (response.isSuccessful() && response.body() != null) {
                        JsonRpcResponse mcpResponse = response.body();
                        Log.d(TAG, "Action executed: " + gson.toJson(mcpResponse.result));
                        broadcastStatus("Command executed successfully");
                        broadcastLog("Executed: " + originalCommand);
                        broadcastLog("Result: " + gson.toJson(mcpResponse.result));
                    } else {
                        Log.e(TAG, "Failed to execute action");
                        broadcastStatus("Error: Failed to execute action");
                    }
                }
                
                @Override
                public void onFailure(Call<JsonRpcResponse> call, Throwable t) {
                    Log.e(TAG, "Action execution failed", t);
                    broadcastStatus("Error: Action execution failed - " + t.getMessage());
                }
            });
        } catch (Exception e) {
            Log.e(TAG, "Failed to parse action JSON", e);
            broadcastStatus("Error: Invalid action format");
        }
    }
    
    private void broadcastStatus(String status) {
        Intent intent = new Intent("com.example.testmcpapp.STATUS_UPDATE");
        intent.putExtra("status", status);
        sendBroadcast(intent);
    }
    
    private void broadcastLog(String log) {
        Intent intent = new Intent("com.example.testmcpapp.LOG_UPDATE");
        intent.putExtra("log", log);
        sendBroadcast(intent);
    }
    
    private void createNotificationChannel() {
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "Mobile Control Service",
                NotificationManager.IMPORTANCE_LOW
        );
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(channel);
    }
    
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
5. Create Model Classes
Create a new package: Right-click on com.example.testmcpapp → New → Package → name it "models"

models/JsonRpcRequest.java
java
package com.example.testmcpapp.models;

public class JsonRpcRequest {
    public String jsonrpc = "2.0";
    public int id;
    public String method;
    public Object params;
    
    public JsonRpcRequest(int id, String method, Object params) {
        this.id = id;
        this.method = method;
        this.params = params;
    }
}
models/JsonRpcResponse.java
java
package com.example.testmcpapp.models;

import com.google.gson.JsonObject;

public class JsonRpcResponse {
    public String jsonrpc;
    public int id;
    public JsonObject result;
    public JsonObject error;
}
models/GeminiRequest.java
java
package com.example.testmcpapp.models;

import java.util.List;

public class GeminiRequest {
    public List<Content> contents;
    
    public static class Content {
        public List<Part> parts;
        
        public static class Part {
            public String text;
            
            public Part(String text) {
                this.text = text;
            }
        }
        
        public Content(String text) {
            this.parts = List.of(new Part(text));
        }
    }
    
    public GeminiRequest(String prompt) {
        this.contents = List.of(new Content(prompt));
    }
}
6. Create Network Interfaces
Create a new package: Right-click on com.example.testmcpapp → New → Package → name it "network"

network/McpApiService.java
java
package com.example.testmcpapp.network;

import com.example.testmcpapp.models.JsonRpcRequest;
import com.example.testmcpapp.models.JsonRpcResponse;

import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.POST;

public interface McpApiService {
    @POST("/")
    Call<JsonRpcResponse> sendJsonRpc(@Body JsonRpcRequest request);
}
network/GeminiApiService.java
java
package com.example.testmcpapp.network;

import com.example.testmcpapp.models.GeminiRequest;
import com.google.gson.JsonObject;

import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.POST;
import retrofit2.http.Query;

public interface GeminiApiService {
    @POST("v1beta/models/gemini-pro:generateContent")
    Call<JsonObject> generateContent(@Body GeminiRequest request, @Query("key") String apiKey);
}
7. Layout File
Location: res/layout/activity_main.xml

Replace the content with:

xml
<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    xmlns:tools="http://schemas.android.com/tools"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:padding="16dp"
    tools:context=".MainActivity">

    <TextView
        android:id="@+id/titleText"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Mobile Control App"
        android:textSize="24sp"
        android:textStyle="bold"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintTop_toTopOf="parent"
        android:layout_marginTop="32dp" />

    <com.google.android.material.textfield.TextInputLayout
        android:id="@+id/commandInputLayout"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_marginTop="32dp"
        android:hint="Enter your command"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintTop_toBottomOf="@+id/titleText">

        <com.google.android.material.textfield.TextInputEditText
            android:id="@+id/commandInput"
            android:layout_width="match_parent"
            android:layout_height="120dp"
            android:gravity="top"
            android:inputType="textMultiLine"
            android:maxLines="5" />

    </com.google.android.material.textfield.TextInputLayout>

    <Button
        android:id="@+id/executeButton"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_marginTop="16dp"
        android:text="Execute Command"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintTop_toBottomOf="@+id/commandInputLayout" />

    <TextView
        android:id="@+id/statusText"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_marginTop="16dp"
        android:text="Status: Ready"
        android:textSize="16sp"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintTop_toBottomOf="@+id/executeButton" />

    <ScrollView
        android:id="@+id/logScrollView"
        android:layout_width="0dp"
        android:layout_height="0dp"
        android:layout_marginTop="16dp"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintTop_toBottomOf="@+id/statusText">

        <TextView
            android:id="@+id/logText"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:background="#f0f0f0"
            android:fontFamily="monospace"
            android:padding="8dp"
            android:text="Logs will appear here..."
            android:textSize="12sp" />

    </ScrollView>

</androidx.constraintlayout.widget.ConstraintLayout>
8. Network Security Config
Location: res/xml/network_security_config.xml

Create this file by: Right-click on res/xml → New → XML Resource File → name it "network_security_config"

xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">192.168.1.100</domain>
    </domain-config>
</network-security-config>
Final Steps
Sync your project: Click "Sync Now" when prompted after adding dependencies

Update IP address: Change 192.168.1.100 to your laptop's actual IP address in both MobileControlService.java and network_security_config.xml

Add Gemini API key: Replace YOUR_GEMINI_API_KEY_HERE with your actual API key

Build and run: Click the green play button to build and install the app

The app will now work with your MCP server running on your laptop!

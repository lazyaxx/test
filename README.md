I'll help you build this Android app step by step. This is a complex project that involves multiple components, so I'll break it down into manageable parts and explain where each piece of code goes.

Project Overview
Your app will have these main components:

MainActivity: Contains the form for user input

MobileControlService: Background service that handles MCP server communication

Network classes: For JSON-RPC communication and Gemini AI integration

Data models: For handling JSON responses

Step 1: Set up your Android project
First, install Android Studio and create a new project:

Open Android Studio

Click "New Project"

Select "Empty Activity" template

Name your project "MobileControlApp"

Set minimum SDK to API 24

Click "Finish"

Step 2: Add dependencies
Open your app/build.gradle file (Module: app) and add these dependencies inside the dependencies block:

text
dependencies {
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
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.6.4'
}
Step 3: Add permissions
In your AndroidManifest.xml file (located in app/src/main/), add these permissions before the <application> tag:

xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
Step 4: Create data models
Create a new package called models. Right-click on app/src/main/java/com.example.mobilecontrolapp/ → New → Package → name it "models"

Create JsonRpcRequest.java in the models package:

java
package com.example.mobilecontrolapp.models;

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
Create JsonRpcResponse.java in the models package:

java
package com.example.mobilecontrolapp.models;

import com.google.gson.JsonObject;

public class JsonRpcResponse {
    public String jsonrpc;
    public int id;
    public JsonObject result;
    public JsonObject error;
}
Create GeminiRequest.java in the models package:

java
package com.example.mobilecontrolapp.models;

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
Step 5: Create network interfaces
Create a new package called network.

Create McpApiService.java in the network package:

java
package com.example.mobilecontrolapp.network;

import com.example.mobilecontrolapp.models.JsonRpcRequest;
import com.example.mobilecontrolapp.models.JsonRpcResponse;

import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.POST;

public interface McpApiService {
    @POST("/")
    Call<JsonRpcResponse> sendJsonRpc(@Body JsonRpcRequest request);
}
Create GeminiApiService.java in the network package:

java
package com.example.mobilecontrolapp.network;

import com.example.mobilecontrolapp.models.GeminiRequest;
import com.google.gson.JsonObject;

import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.POST;
import retrofit2.http.Query;

public interface GeminiApiService {
    @POST("v1beta/models/gemini-pro:generateContent")
    Call<JsonObject> generateContent(@Body GeminiRequest request, @Query("key") String apiKey);
}
Step 6: Create the main layout
Replace the content of app/src/main/res/layout/activity_main.xml:

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
Step 7: Create the background service
Create MobileControlService.java in your main package:

java
package com.example.mobilecontrolapp;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import android.util.Log;

import androidx.core.app.NotificationCompat;

import com.example.mobilecontrolapp.models.GeminiRequest;
import com.example.mobilecontrolapp.models.JsonRpcRequest;
import com.example.mobilecontrolapp.models.JsonRpcResponse;
import com.example.mobilecontrolapp.network.GeminiApiService;
import com.example.mobilecontrolapp.network.McpApiService;
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
    private static final String MCP_SERVER_URL = "http://192.168.1.100:3000"; // Example IP
    
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
        
        // Step 1: Get available tools from MCP server
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
                    
                    // Step 2: Send tools and command to Gemini
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
                    
                    // Extract the action from Gemini's response
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
        Intent intent = new Intent("com.example.mobilecontrolapp.STATUS_UPDATE");
        intent.putExtra("status", status);
        sendBroadcast(intent);
    }
    
    private void broadcastLog(String log) {
        Intent intent = new Intent("com.example.mobilecontrolapp.LOG_UPDATE");
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
Step 8: Update MainActivity
Replace the content of MainActivity.java:

java
package com.example.mobilecontrolapp;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {
    private EditText commandInput;
    private Button executeButton;
    private TextView statusText;
    private TextView logText;
    private StringBuilder logBuilder;
    
    private BroadcastReceiver statusReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String status = intent.getStringExtra("status");
            if (status != null) {
                statusText.setText("Status: " + status);
            }
        }
    };
    
    private BroadcastReceiver logReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String log = intent.getStringExtra("log");
            if (log != null) {
                logBuilder.append(log).append("\n");
                logText.setText(logBuilder.toString());
            }
        }
    };
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        
        initializeViews();
        setupClickListeners();
        
        logBuilder = new StringBuilder();
        logBuilder.append("App started. Ready to process commands.\n");
        logText.setText(logBuilder.toString());
    }
    
    private void initializeViews() {
        commandInput = findViewById(R.id.commandInput);
        executeButton = findViewById(R.id.executeButton);
        statusText = findViewById(R.id.statusText);
        logText = findViewById(R.id.logText);
    }
    
    private void setupClickListeners() {
        executeButton.setOnClickListener(v -> {
            String command = commandInput.getText().toString().trim();
            if (!command.isEmpty()) {
                executeCommand(command);
                commandInput.setText("");
            }
        });
    }
    
    private void executeCommand(String command) {
        Intent serviceIntent = new Intent(this, MobileControlService.class);
        serviceIntent.putExtra("command", command);
        startForegroundService(serviceIntent);
        
        statusText.setText("Status: Processing command...");
        logBuilder.append("User command: ").append(command).append("\n");
        logText.setText(logBuilder.toString());
    }
    
    @Override
    protected void onResume() {
        super.onResume();
        registerReceiver(statusReceiver, new IntentFilter("com.example.mobilecontrolapp.STATUS_UPDATE"));
        registerReceiver(logReceiver, new IntentFilter("com.example.mobilecontrolapp.LOG_UPDATE"));
    }
    
    @Override
    protected void onPause() {
        super.onPause();
        unregisterReceiver(statusReceiver);
        unregisterReceiver(logReceiver);
    }
}
Step 9: Register the service in AndroidManifest.xml
Add this service declaration inside the <application> tag in your AndroidManifest.xml:

xml
<service
    android:name=".MobileControlService"
    android:enabled="true"
    android:exported="false"
    android:foregroundServiceType="dataSync" />
Important Configuration Steps
1. Replace placeholder values in MobileControlService.java:

Replace YOUR_GEMINI_API_KEY_HERE with your actual Gemini API key

Replace 192.168.1.100:3000 with your laptop's actual IP address and MCP server port

2. Network Security Configuration
Create res/xml/network_security_config.xml:

xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">192.168.1.100</domain>
    </domain-config>
</network-security-config>
Add this to your AndroidManifest.xml in the <application> tag:

xml
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ... >
Key Considerations
Challenges you'll face:

MCP Server Startup: The app cannot directly start the MCP server on your laptop. You'll need to manually run npx @mobilenext/mobile-mcp@latest on your laptop first.

Network Configuration: Ensure your Android device and laptop are on the same network.

API Keys: You'll need a valid Gemini API key from Google Cloud Console.

Error Handling: The current implementation has basic error handling, but you may need to enhance it based on actual MCP server responses.

Testing Steps:

Start the MCP server on your laptop

Update the IP address in the Android app

Install and run the app

Test with simple commands first

This implementation provides a solid foundation, but you may need to adjust the JSON-RPC communication based on the actual mobile-mcp server specifications. The app uses background services to handle long-running tasks and maintains communication between components through broadcast receivers.

{
  "name": "url_analyzer_agent",
  "description": "Senior Security Analyst specialized in URL threat detection",
  "url": "http://localhost:8001/",
  "version": "1.0.0",
  "capabilities": {
    "streaming": false,
    "pushNotifications": true,
    "stateTransitionHistory": false
  },
  "authentication": {
    "schemes": ["Bearer"]
  },
  "defaultInputModes": ["text", "text/plain"],
  "defaultOutputModes": ["application/json"],
  "skills": [
    {
      "id": "analyze_url_threat",
      "name": "URL Threat Analysis",
      "description": "Analyze URLs for security threats and provide trust level assessment",
      "tags": ["security", "url-analysis", "threat-detection"],
      "examples": ["Analyze this URL: https://example.com for security threats"]
    }
  ]
}

{
  "name": "soc_communication_agent", 
  "description": "SOC Liaison Officer for security operations coordination",
  "url": "http://localhost:8002/",
  "version": "1.0.0",
  "capabilities": {
    "streaming": false,
    "pushNotifications": true,
    "stateTransitionHistory": false
  },
  "authentication": {
    "schemes": ["Bearer"]
  },
  "defaultInputModes": ["application/json"],
  "defaultOutputModes": ["text", "text/plain"],
  "skills": [
    {
      "id": "communicate_with_soc",
      "name": "SOC Communication",
      "description": "Send security analysis results to SOC admin and get severity assessment",
      "tags": ["soc", "communication", "security-assessment"],
      "examples": ["Send analysis data to SOC admin for severity assessment"]
    }
  ]
}


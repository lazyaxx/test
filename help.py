Implementing A2A Protocol for CrewAI Agent Communication
Based on your current CrewAI implementation, I'll show you how to convert it to use Google's Agent2Agent (A2A) protocol for inter-agent communication. The A2A protocol enables standardized communication between AI agents built on different frameworks, allowing them to discover each other's capabilities and collaborate securely.

Overview of A2A Protocol
The Agent2Agent (A2A) protocol is an open standard that enables autonomous AI agents to securely discover, communicate, and collaborate across platforms. It uses JSON-RPC 2.0 over HTTP(S) for standardized communication and supports agent discovery via "Agent Cards" that detail capabilities and connection information.

Step 1: Install Required Dependencies
First, install the official A2A Python SDK and AutoA2A CLI tool:

bash
# Install A2A SDK
pip install a2a-sdk

# Install AutoA2A for CrewAI scaffolding
git clone https://github.com/NapthaAI/autoa2a
cd autoa2a
pip install -e .
Step 2: Create Agent Cards
Agent Cards serve as digital identity cards for your agents, describing their capabilities to other agents. Each agent needs an Agent Card accessible at /.well-known/agent.json.

URL Analyzer Agent Card
Create url_analyzer_agent_card.json:

json
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
    "schemes": ["Basic"]
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
SOC Communication Agent Card
Create soc_communication_agent_card.json:

json
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
    "schemes": ["Basic"]
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
Step 3: Implement A2A Server Wrappers
URL Analyzer A2A Server
Create url_analyzer_a2a_server.py:

python
import asyncio
import json
from typing import Dict, Any
from a2a_sdk import A2AServer, AgentCard, AgentSkill, AgentCapabilities
from crews.security_crew.security_crew import SecurityCrew
from crewai import LLM

class URLAnalyzerA2AServer:
    def __init__(self, host="localhost", port=8001):
        self.host = host
        self.port = port
        self.llm = LLM(
            model="ollama/mistral:7b-instruct-q6_K",
            num_ctx=4096,
        )
        
        # Create agent card
        self.agent_card = AgentCard(
            name="url_analyzer_agent",
            description="Senior Security Analyst specialized in URL threat detection",
            url=f"http://{host}:{port}/",
            version="1.0.0",
            capabilities=AgentCapabilities(pushNotifications=True),
            skills=[
                AgentSkill(
                    id="analyze_url_threat",
                    name="URL Threat Analysis",
                    description="Analyze URLs for security threats and provide trust level assessment",
                    tags=["security", "url-analysis", "threat-detection"],
                    examples=["Analyze this URL: https://example.com for security threats"]
                )
            ]
        )
        
        self.server = A2AServer(
            agent_card=self.agent_card,
            host=host,
            port=port
        )

    async def handle_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle URL analysis task"""
        try:
            url = task_data.get("url", "")
            if not url:
                return {"error": "URL is required"}
            
            # Create a simple crew for URL analysis
            security_crew = SecurityCrew()
            
            # Execute URL analysis
            result = security_crew.crew().kickoff(inputs={"url": url})
            
            # Extract trust level from result
            trust_level = self._extract_trust_level(str(result))
            
            return {
                "url": url,
                "trust_level": trust_level,
                "analysis_result": str(result),
                "status": "completed"
            }
            
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}
    
    def _extract_trust_level(self, result_text: str) -> int:
        """Extract trust level from analysis result"""
        # Simple extraction logic - in production, use more sophisticated parsing
        import re
        match = re.search(r'trust.*?level.*?(\d+)', result_text.lower())
        if match:
            return int(match.group(1))
        return 5  # Default middle trust level

    async def start(self):
        """Start the A2A server"""
        await self.server.start()

# Server runner
async def main():
    server = URLAnalyzerA2AServer()
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
SOC Communication A2A Server
Create soc_communication_a2a_server.py:

python
import asyncio
import json
from typing import Dict, Any
from a2a_sdk import A2AServer, AgentCard, AgentSkill, AgentCapabilities
from tools.custom_tool import SOCCommunicationTool

class SOCCommunicationA2AServer:
    def __init__(self, host="localhost", port=8002):
        self.host = host
        self.port = port
        self.soc_tool = SOCCommunicationTool()
        
        # Create agent card
        self.agent_card = AgentCard(
            name="soc_communication_agent",
            description="SOC Liaison Officer for security operations coordination",
            url=f"http://{host}:{port}/",
            version="1.0.0",
            capabilities=AgentCapabilities(pushNotifications=True),
            skills=[
                AgentSkill(
                    id="communicate_with_soc",
                    name="SOC Communication",
                    description="Send security analysis results to SOC admin and get severity assessment",
                    tags=["soc", "communication", "security-assessment"],
                    examples=["Send analysis data to SOC admin for severity assessment"]
                )
            ]
        )
        
        self.server = A2AServer(
            agent_card=self.agent_card,
            host=host,
            port=port
        )

    async def handle_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle SOC communication task"""
        try:
            analysis_data = task_data.get("analysis_data", {})
            if not analysis_data:
                return {"error": "Analysis data is required"}
            
            # Use the existing SOC communication tool
            soc_response = self.soc_tool._run(analysis_data)
            
            return {
                "soc_response": soc_response,
                "status": "completed"
            }
            
        except Exception as e:
            return {"error": f"SOC communication failed: {str(e)}"}

    async def start(self):
        """Start the A2A server"""
        await self.server.start()

# Server runner
async def main():
    server = SOCCommunicationA2AServer()
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
Step 4: Create A2A Client for Agent Orchestration
Create security_monitoring_a2a_client.py:

python
import asyncio
import json
from typing import List, Dict, Any
from a2a_sdk import A2AClient
from pydantic import BaseModel

class SecurityState(BaseModel):
    processed_urls: List[str] = []
    results: List[Dict] = []

class SecurityMonitoringA2AClient:
    def __init__(self):
        self.state = SecurityState()
        self.url_analyzer_client = A2AClient("http://localhost:8001")
        self.soc_communication_client = A2AClient("http://localhost:8002")

    async def initialize_monitoring(self):
        """Initialize the security monitoring system"""
        print("🚀 Starting A2A Security Monitoring System")
        print("=" * 50)
        
        # Demo URL list
        demo_urls = [
            "https://example.com",
            "https://malware.com/download.exe",
            "https://phishing-site.net/fake-login",
            "https://legitimate-site.org",
            "https://suspicious-download.org/file.exe",
            "http://unsecure-site.com"
        ]
        
        return demo_urls

    async def process_urls(self, urls: List[str]):
        """Process URLs using A2A protocol"""
        print(f"\n🔍 Processing {len(urls)} URLs using A2A protocol...")
        
        for url in urls:
            try:
                # Step 1: Send URL to analyzer agent
                analysis_task = await self.url_analyzer_client.send_task({
                    "skill_id": "analyze_url_threat",
                    "inputs": {"url": url}
                })
                
                # Wait for analysis completion
                analysis_result = await self.url_analyzer_client.get_task_result(analysis_task.id)
                
                print(f"✅ Analysis completed for: {url}")
                print(f"   Trust Level: {analysis_result.get('trust_level', 'Unknown')}")
                
                # Step 2: Send analysis to SOC communication agent
                soc_task = await self.soc_communication_client.send_task({
                    "skill_id": "communicate_with_soc",
                    "inputs": {"analysis_data": analysis_result}
                })
                
                # Wait for SOC response
                soc_result = await self.soc_communication_client.get_task_result(soc_task.id)
                
                # Store combined results
                self.state.processed_urls.append(url)
                self.state.results.append({
                    "url": url,
                    "analysis_result": analysis_result,
                    "soc_response": soc_result.get("soc_response", ""),
                    "status": "completed"
                })
                
                print(f"   SOC Assessment: {soc_result.get('soc_response', 'No response')}")
                print("-" * 50)
                
            except Exception as e:
                print(f"❌ Error processing {url}: {str(e)}")
                self.state.results.append({
                    "url": url,
                    "error": str(e),
                    "status": "failed"
                })

    async def generate_summary_report(self):
        """Generate final summary report"""
        print("\n📊 A2A SECURITY MONITORING SUMMARY")
        print("=" * 60)
        print(f"URLs Processed: {len(self.state.processed_urls)}")
        
        blocked_urls = []
        allowed_urls = []
        review_urls = []
        
        for result in self.state.results:
            if result.get("status") == "failed":
                continue
                
            soc_response = result.get("soc_response", "").lower()
            url = result["url"]
            
            if 'block' in soc_response:
                blocked_urls.append(url)
                print(f"\n🚫 {url} - BLOCKED")
            elif 'allow' in soc_response:
                allowed_urls.append(url)
                print(f"\n✅ {url} - ALLOWED")
            elif 'review' in soc_response:
                review_urls.append(url)
                print(f"\n🔍 {url} - REVIEW REQUIRED")
            else:
                print(f"\n❓ {url} - UNKNOWN STATUS")
        
        print(f"\n🛡️ FINAL SECURITY SUMMARY:")
        print(f"   🚫 Blocked: {len(blocked_urls)} URLs")
        print(f"   ✅ Allowed: {len(allowed_urls)} URLs")
        print(f"   🔍 Review Required: {len(review_urls)} URLs")

    async def run_security_monitoring(self):
        """Main orchestration method"""
        try:
            # Initialize monitoring
            urls = await self.initialize_monitoring()
            
            # Process URLs through A2A agents
            await self.process_urls(urls)
            
            # Generate summary
            await self.generate_summary_report()
            
            return {
                "status": "completed",
                "total_processed": len(self.state.processed_urls),
                "results": self.state.results
            }
            
        except Exception as e:
            print(f"❌ Monitoring failed: {str(e)}")
            return {"status": "failed", "error": str(e)}

# Main runner
async def main():
    client = SecurityMonitoringA2AClient()
    result = await client.run_security_monitoring()
    return result

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nFinal Result: {json.dumps(result, indent=2)}")
Step 5: Alternative Using AutoA2A CLI
For a simpler approach, you can use the AutoA2A CLI tool to automatically scaffold A2A servers for your CrewAI agents:

bash
# Navigate to your project directory
cd your-security-monitoring-project

# Generate A2A server for CrewAI
autoa2a init --framework crewai

# This will create the necessary A2A server files automatically
Step 6: Deployment and Execution
Running the System
Start the URL Analyzer A2A Server:

bash
python url_analyzer_a2a_server.py
Start the SOC Communication A2A Server:

bash
python soc_communication_a2a_server.py
Run the A2A Client:

bash
python security_monitoring_a2a_client.py
Verification
You can verify that your agents are discoverable by checking their agent cards:

bash
# Check URL Analyzer agent card
curl http://localhost:8001/.well-known/agent.json

# Check SOC Communication agent card
curl http://localhost:8002/.well-known/agent.json
Key Benefits of A2A Implementation
Standardized Communication: Uses JSON-RPC 2.0 over HTTP(S) for reliable inter-agent communication

Agent Discovery: Agents can automatically discover each other's capabilities through Agent Cards

Framework Agnostic: Your CrewAI agents can now communicate with agents built using other frameworks like LangGraph, Autogen, etc.

Scalability: Each agent runs as an independent service, allowing for better resource management and scaling

Security: Built-in authentication and secure communication protocols

This A2A implementation transforms your monolithic CrewAI flow into a distributed system where agents communicate through standardized protocols, making your system more modular, scalable, and interoperable with other AI agent frameworks.

import asyncio
import aiohttp
import json
from typing import List, Dict, Any
from uuid import uuid4
from a2a.types.a2a_types import JSONRPCRequest, TaskSendParams

class SecurityA2AOrchestrator:
    def __init__(self):
        self.url_analyzer_url = "http://localhost:8001"
        self.soc_communication_url = "http://localhost:8002"

    async def send_a2a_request(self, url: str, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send A2A JSON-RPC request"""
        rpc_request = JSONRPCRequest(
            method=method,
            params=params
        )
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=rpc_request.dict(),
                headers={"Content-Type": "application/json"}
            ) as response:
                return await response.json()

    async def analyze_url(self, url: str) -> Dict[str, Any]:
        """Analyze URL using A2A protocol"""
        params = TaskSendParams(
            skillId="analyze_url_threat",
            inputs={"url": url}
        ).dict()
        
        response = await self.send_a2a_request(
            self.url_analyzer_url,
            "tasks/send",
            params
        )
        
        if "error" in response:
            raise Exception(f"URL analysis failed: {response['error']}")
        
        return response["result"]["outputs"]

    async def communicate_with_soc(self, analysis_ Dict[str, Any]) -> Dict[str, Any]:
        """Communicate with SOC using A2A protocol"""
        params = TaskSendParams(
            skillId="communicate_with_soc",
            inputs={"analysis_data": analysis_data}
        ).dict()
        
        response = await self.send_a2a_request(
            self.soc_communication_url,
            "tasks/send",
            params
        )
        
        if "error" in response:
            raise Exception(f"SOC communication failed: {response['error']}")
        
        return response["result"]["outputs"]

    async def process_security_workflow(self, urls: List[str]):
        """Process security workflow using A2A protocol"""
        print("🚀 Starting A2A Security Workflow")
        print("=" * 50)
        
        results = []
        
        for url in urls:
            try:
                print(f"\n🔍 Processing: {url}")
                
                # Step 1: Analyze URL
                analysis_result = await self.analyze_url(url)
                print(f"   ✅ Analysis completed - Trust Level: {analysis_result.get('trust_level', 'Unknown')}")
                
                # Step 2: Communicate with SOC
                soc_result = await self.communicate_with_soc(analysis_result)
                print(f"   📞 SOC Response: {soc_result.get('soc_response', 'No response')}")
                
                results.append({
                    "url": url,
                    "analysis": analysis_result,
                    "soc_response": soc_result,
                    "status": "completed"
                })
                
            except Exception as e:
                print(f"   ❌ Error processing {url}: {str(e)}")
                results.append({
                    "url": url,
                    "error": str(e),
                    "status": "failed"
                })
        
        print(f"\n📊 Processed {len(results)} URLs")
        return results

async def main():
    orchestrator = SecurityA2AOrchestrator()
    
    demo_urls = [
        "https://example.com",
        "https://malware.com/download.exe",
        "https://phishing-site.net/fake-login"
    ]
    
    results = await orchestrator.process_security_workflow(demo_urls)
    print(f"\nFinal Results: {json.dumps(results, indent=2)}")

if __name__ == "__main__":
    asyncio.run(main())



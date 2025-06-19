# shit

import json
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any
import uvicorn
from pathlib import Path

# Import your existing crew
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from crew import SecurityCrew
from a2a.types.a2a_types import JSONRPCRequest, JSONRPCResponse, TaskSendParams, TaskResult, TaskStatus

class URLAnalyzerA2AServer:
    def __init__(self, host="localhost", port=8001):
        self.host = host
        self.port = port
        self.app = FastAPI()
        self.security_crew = SecurityCrew()
        self.setup_routes()
        
        # Load agent card
        card_path = Path(__file__).parent.parent / "agent_cards" / "url_analyzer_card.json"
        with open(card_path, 'r') as f:
            self.agent_card = json.load(f)

    def setup_routes(self):
        """Setup FastAPI routes for A2A protocol"""
        
        @self.app.get("/.well-known/agent.json")
        async def get_agent_card():
            """Serve agent card for discovery"""
            return self.agent_card

        @self.app.post("/")
        async def handle_jsonrpc_request(request: Request):
            """Handle A2A JSON-RPC requests"""
            try:
                body = await request.json()
                rpc_request = JSONRPCRequest(**body)
                
                if rpc_request.method == "tasks/send":
                    return await self.handle_task_send(rpc_request)
                elif rpc_request.method == "tasks/get":
                    return await self.handle_task_get(rpc_request)
                else:
                    raise HTTPException(status_code=400, detail="Unsupported method")
                    
            except Exception as e:
                return JSONRPCResponse(
                    id=rpc_request.id if 'rpc_request' in locals() else "unknown",
                    error={"code": -32603, "message": str(e)}
                )

    async def handle_task_send(self, rpc_request: JSONRPCRequest) -> JSONRPCResponse:
        """Handle task/send requests"""
        try:
            params = TaskSendParams(**rpc_request.params)
            
            if params.skillId != "analyze_url_threat":
                raise ValueError(f"Unsupported skill: {params.skillId}")
            
            # Extract URL from inputs
            url = params.inputs.get("url", "")
            if not url:
                raise ValueError("URL is required")
            
            # Execute CrewAI analysis
            result = self.security_crew.crew().kickoff(inputs={"url": url})
            
            # Extract trust level (implement your own logic)
            trust_level = self._extract_trust_level(str(result))
            
            task_result = TaskResult(
                id=params.id,
                status=TaskStatus(state="COMPLETED"),
                outputs={
                    "url": url,
                    "trust_level": trust_level,
                    "analysis_result": str(result)
                }
            )
            
            return JSONRPCResponse(
                id=rpc_request.id,
                result=task_result.dict()
            )
            
        except Exception as e:
            return JSONRPCResponse(
                id=rpc_request.id,
                error={"code": -32603, "message": str(e)}
            )

    async def handle_task_get(self, rpc_request: JSONRPCRequest) -> JSONRPCResponse:
        """Handle task/get requests - simplified for demo"""
        # In production, you'd maintain a task store
        return JSONRPCResponse(
            id=rpc_request.id,
            result={"message": "Task retrieval not implemented in this demo"}
        )

    def _extract_trust_level(self, result_text: str) -> int:
        """Extract trust level from analysis result"""
        import re
        match = re.search(r'trust.*?level.*?(\d+)', result_text.lower())
        if match:
            return int(match.group(1))
        return 5  # Default

    def run(self):
        """Start the server"""
        uvicorn.run(self.app, host=self.host, port=self.port)

if __name__ == "__main__":
    server = URLAnalyzerA2AServer()
    print(f"Starting URL Analyzer A2A Server on http://localhost:8001")
    server.run()

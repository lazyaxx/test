from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from uuid import uuid4
import json

class AgentCapabilities(BaseModel):
    streaming: bool = False
    pushNotifications: bool = False
    stateTransitionHistory: bool = False

class AgentAuthentication(BaseModel):
    schemes: List[str]
    credentials: Optional[str] = None

class AgentSkill(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    examples: Optional[List[str]] = None
    inputModes: Optional[List[str]] = None
    outputModes: Optional[List[str]] = None

class AgentCard(BaseModel):
    name: str
    description: Optional[str] = None
    url: str
    version: str
    capabilities: AgentCapabilities
    authentication: Optional[AgentAuthentication] = None
    defaultInputModes: List[str] = ["text", "text/plain"]
    defaultOutputModes: List[str] = ["text", "text/plain"]
    skills: List[AgentSkill]

# A2A Protocol Types
class TaskSendParams(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    sessionId: str = Field(default_factory=lambda: uuid4().hex)
    skillId: str
    inputs: Dict[str, Any]
    historyLength: Optional[int] = 10
    pushNotification: Optional[Dict[str, Any]] = None

class TaskStatus(BaseModel):
    state: Literal["WORKING", "COMPLETED", "INPUT_REQUIRED", "FAILED"]
    message: Optional[str] = None

class TaskResult(BaseModel):
    id: str
    status: TaskStatus
    outputs: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class JSONRPCRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str = Field(default_factory=lambda: uuid4().hex)
    method: str
    params: Dict[str, Any]

class JSONRPCResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

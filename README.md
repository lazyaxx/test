# src/test_agent/gatekeeper.py

from crewai.agents.parser import AgentAction, AgentFinish
from crewai.agents.crew_agent_executor import ToolResult
import json
import logging
from typing import Dict, Any, Optional

class SecurityGatekeeper:
    """
    Gatekeeper that monitors SOC communication agent and validates tool outputs
    """
    
    def __init__(self):
        self.tool_outputs = {}
        self.agent_outputs = {}
        self.current_task_id = None
        self.violations = []
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def step_callback(self, step):
        """
        Callback function to monitor agent steps and capture tool outputs
        """
        try:
            if isinstance(step, ToolResult):
                # Capture tool output
                self.logger.info(f"🔧 Tool Result Captured: {step.result}")
                
                # Store tool output for comparison
                if 'assess_severity' in str(step).lower():
                    self.tool_outputs[self.current_task_id] = step.result
                    self.logger.info(f"📋 Stored assess_severity output: {step.result}")
                    
            elif isinstance(step, AgentFinish):
                # Capture final agent output
                self.logger.info(f"✅ Agent Finish: {step.return_values}")
                
                # Store agent final output
                if self.current_task_id:
                    self.agent_outputs[self.current_task_id] = step.return_values.get('output', str(step.return_values))
                    
                # Perform gatekeeper validation
                self._validate_outputs()
                    
            elif isinstance(step, AgentAction):
                self.logger.info(f"🎯 Agent Action: {step.tool}")
                
        except Exception as e:
            self.logger.error(f"Error in step_callback: {e}")
    
    def _validate_outputs(self):
        """
        Compare tool output with agent final output
        """
        if not self.current_task_id:
            return
            
        tool_output = self.tool_outputs.get(self.current_task_id)
        agent_output = self.agent_outputs.get(self.current_task_id)
        
        if tool_output and agent_output:
            validation_result = self._compare_outputs(tool_output, agent_output)
            
            if not validation_result['is_valid']:
                violation = {
                    'task_id': self.current_task_id,
                    'tool_output': tool_output,
                    'agent_output': agent_output,
                    'violation_type': validation_result['violation_type'],
                    'message': validation_result['message']
                }
                self.violations.append(violation)
                self.logger.warning(f"🚨 GATEKEEPER VIOLATION: {violation}")
                
                # Take corrective action
                self._handle_violation(violation)
            else:
                self.logger.info(f"✅ GATEKEEPER VALIDATION PASSED for task {self.current_task_id}")
    
    def _compare_outputs(self, tool_output: Any, agent_output: str) -> Dict[str, Any]:
        """
        Compare tool output with agent output to detect modifications
        """
        try:
            # Parse tool output if it's a string
            if isinstance(tool_output, str):
                try:
                    tool_data = json.loads(tool_output)
                except:
                    tool_data = {"raw_output": tool_output}
            else:
                tool_data = tool_output
            
            # Extract key information from tool output
            tool_result = tool_data.get('result', '').lower() if isinstance(tool_data, dict) else str(tool_data).lower()
            tool_confidence = tool_data.get('confidence_score', 0) if isinstance(tool_data, dict) else None
            
            # Check if agent output contains the tool's decision
            agent_output_lower = agent_output.lower()
            
            # Validation rules
            if 'block' in tool_result and 'block' not in agent_output_lower:
                return {
                    'is_valid': False,
                    'violation_type': 'DECISION_OVERRIDE',
                    'message': f"Tool recommended BLOCK but agent output doesn't contain block decision"
                }
            
            if 'allow' in tool_result and 'allow' not in agent_output_lower and 'permitted' not in agent_output_lower:
                return {
                    'is_valid': False,
                    'violation_type': 'DECISION_OVERRIDE', 
                    'message': f"Tool recommended ALLOW but agent output doesn't reflect this"
                }
            
            if 'review' in tool_result and 'review' not in agent_output_lower:
                return {
                    'is_valid': False,
                    'violation_type': 'DECISION_OVERRIDE',
                    'message': f"Tool recommended REVIEW but agent output doesn't contain review decision"
                }
            
            # Check for confidence score mention if available
            if tool_confidence and str(tool_confidence) not in agent_output:
                return {
                    'is_valid': False,
                    'violation_type': 'MISSING_DETAILS',
                    'message': f"Agent output missing confidence score: {tool_confidence}"
                }
            
            return {'is_valid': True, 'message': 'Validation passed'}
            
        except Exception as e:
            return {
                'is_valid': False,
                'violation_type': 'VALIDATION_ERROR',
                'message': f"Error during validation: {e}"
            }
    
    def _handle_violation(self, violation: Dict[str, Any]):
        """
        Handle gatekeeper violations
        """
        violation_type = violation['violation_type']
        
        if violation_type == 'DECISION_OVERRIDE':
            self.logger.error("🚨 CRITICAL: Agent overrode tool security decision!")
            
        elif violation_type == 'MISSING_DETAILS':
            self.logger.warning("⚠️ WARNING: Agent output missing important details")
            
        # You can add more actions here like:
        # - Send alerts
        # - Log to security system
        # - Override agent output with tool output
        # - etc.
    
    def set_current_task(self, task_id: str):
        """Set the current task ID for tracking"""
        self.current_task_id = task_id
    
    def get_violations(self) -> list:
        """Get all detected violations"""
        return self.violations
    
    def reset(self):
        """Reset gatekeeper state"""
        self.tool_outputs.clear()
        self.agent_outputs.clear()
        self.violations.clear()
        self.current_task_id = None



# src/test_agent/crew.py

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters
from .gatekeeper import SecurityGatekeeper
import os
import sys

@CrewBase
class SecurityCrew():
    """Security monitoring crew for URL threat analysis with MCP integration and gatekeeper"""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    ollama_llm = LLM(
        model="ollama/mistral:7b-instruct-q6_K", 
        num_ctx=4096,
    )

    def __init__(self, mcp_tools=None):
        """Initialize with optional MCP tools and gatekeeper"""
        self.mcp_tools = mcp_tools or []
        self.gatekeeper = SecurityGatekeeper()
        super().__init__()

    @agent
    def url_analyzer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['url_analyzer_agent'],
            verbose=True,
            allow_delegation=False,
            llm=self.ollama_llm,
        )

    @agent
    def soc_communication_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['soc_communication_agent'],
            verbose=True,
            tools=self.mcp_tools,
            allow_delegation=False,
            llm=self.ollama_llm,
            step_callback=self.gatekeeper.step_callback,  # Add gatekeeper monitoring
        )

    @agent  
    def gatekeeper_agent(self) -> Agent:
        """Dedicated gatekeeper agent for validation reporting"""
        return Agent(
            role="Security Gatekeeper",
            goal="Monitor and validate that SOC communication agent outputs match tool recommendations",
            backstory="You are a security gatekeeper responsible for ensuring that agent outputs accurately reflect tool recommendations without unauthorized modifications.",
            verbose=True,
            llm=self.ollama_llm,
        )

    @task
    def url_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config['url_analysis_task'],
            agent=self.url_analyzer_agent()
        )

    @task
    def soc_communication_task(self) -> Task:
        # Set current task for gatekeeper tracking
        task_id = f"soc_comm_{id(self)}"
        self.gatekeeper.set_current_task(task_id)
        
        return Task(
            config=self.tasks_config['soc_communication_task'],
            agent=self.soc_communication_agent(),
            context=[self.url_analysis_task()]
        )

    @task
    def gatekeeper_validation_task(self) -> Task:
        """Task for gatekeeper to report validation results"""
        return Task(
            description="Review all security violations detected by the gatekeeper and provide a summary report of any discrepancies between tool outputs and agent final outputs.",
            expected_output="A summary report of gatekeeper validation results, including any violations found and their severity levels.",
            agent=self.gatekeeper_agent(),
            context=[self.soc_communication_task()]
        )

    @crew
    def crew(self) -> Crew:
        """Creates the security monitoring crew with gatekeeper"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )

    def get_gatekeeper_report(self) -> dict:
        """Get gatekeeper validation report"""
        violations = self.gatekeeper.get_violations()
        return {
            'total_violations': len(violations),
            'violations': violations,
            'status': 'CLEAN' if len(violations) == 0 else 'VIOLATIONS_DETECTED'
        }




#!/usr/bin/env python

import sys
import warnings
import os
from datetime import datetime
from crew import SecurityCrew
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

def run():
    urls = [
        "https://example.com",
        "https://malware.com/download.exe", 
        "https://phishing-site.net/fake-login",
        "https://legitimate-site.org",
        "https://suspicious-download.org/file.exe",
        "http://unsecure-site.com"
    ]

    print(f"\n🔍 Processing {len(urls)} URLs with MCP protocol and Gatekeeper...")
    
    # Setup MCP server parameters
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mcp_server_path = os.path.join(current_dir, "mcp_soc_server.py")
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[mcp_server_path],
        env=dict(os.environ),
    )
    
    try:
        with MCPServerAdapter(server_params) as mcp_tools:
            print(f"Available MCP tools: {[tool.name for tool in mcp_tools]}")
            
            # Create security crew with MCP tools and gatekeeper
            security_crew = SecurityCrew(mcp_tools=list(mcp_tools))
            
            url_inputs = [{"url": url} for url in urls]
            results = security_crew.crew().kickoff_for_each(inputs=url_inputs)

            # Process results
            processed_urls = []
            output_results = []
            
            for i, (url, result) in enumerate(zip(urls, results)):
                print(f"✅ Completed processing: {url}")
                processed_urls.append(url)
                output_results.append({
                    "url": url,
                    "result": str(result),
                    "crew_result": result
                })
                print(f"   Status: {'Success' if result else 'Failed'}")
                print("-" * 50)

            # Get gatekeeper report
            gatekeeper_report = security_crew.get_gatekeeper_report()
            
            print("\n🛡️ GATEKEEPER VALIDATION REPORT")
            print("=" * 50)
            print(f"Status: {gatekeeper_report['status']}")
            print(f"Total Violations: {gatekeeper_report['total_violations']}")
            
            if gatekeeper_report['violations']:
                print("\n🚨 DETECTED VIOLATIONS:")
                for i, violation in enumerate(gatekeeper_report['violations'], 1):
                    print(f"\n{i}. Violation Type: {violation['violation_type']}")
                    print(f"   Message: {violation['message']}")
                    print(f"   Tool Output: {violation['tool_output']}")
                    print(f"   Agent Output: {violation['agent_output'][:100]}...")

            print("\n📊 SECURITY MONITORING SUMMARY (MCP-Enabled with Gatekeeper)")
            print("=" * 60)
            print(f"URLs Processed: {len(processed_urls)}")

            # Analyze results
            blocked_urls = []
            allowed_urls = []
            review_urls = []

            for i, result in enumerate(output_results, 1):
                result_str = result['result'].lower()
                url = result['url']
                print(f"\n{i}. {url}")
                
                if 'block' in result_str:
                    blocked_urls.append(url)
                    print(f"   🚫 Decision: BLOCKED")
                elif 'allow' in result_str:
                    allowed_urls.append(url)
                    print(f"   ✅ Decision: ALLOWED")
                elif 'review' in result_str:
                    review_urls.append(url)
                    print(f"   🔍 Decision: REVIEW REQUIRED")
                else:
                    print(f"   ❓ Decision: UNKNOWN")

            print(f"\n🛡️ SECURITY SUMMARY:")
            print(f"   🚫 Blocked: {len(blocked_urls)} URLs")
            print(f"   ✅ Allowed: {len(allowed_urls)} URLs") 
            print(f"   🔍 Review Required: {len(review_urls)} URLs")
            print(f"   🛡️ Gatekeeper Status: {gatekeeper_report['status']}")

            return {
                "summary": "Security monitoring completed with MCP protocol and gatekeeper validation",
                "stats": {
                    "total": len(processed_urls),
                    "blocked": len(blocked_urls),
                    "allowed": len(allowed_urls),
                    "review": len(review_urls)
                },
                "gatekeeper": gatekeeper_report
            }
            
    except Exception as e:
        print(f"Error with MCP connection: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    results = run()
    print("\nFinal Results:")
    print(results)
    sys.exit(0)

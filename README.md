# src/test_agent/rule_based_gatekeeper.py

import json
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class ViolationType(Enum):
    DECISION_MISMATCH = "DECISION_MISMATCH"
    CONFIDENCE_MISSING = "CONFIDENCE_MISSING"
    CONFIDENCE_ALTERED = "CONFIDENCE_ALTERED"
    URL_MISSING = "URL_MISSING"
    UNAUTHORIZED_DECISION_CHANGE = "UNAUTHORIZED_DECISION_CHANGE"
    MISSING_TOOL_DATA = "MISSING_TOOL_DATA"
    FORMAT_VIOLATION = "FORMAT_VIOLATION"

@dataclass
class ValidationRule:
    """Represents a validation rule"""
    name: str
    description: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    check_function: callable
    violation_type: ViolationType

class RuleBasedGatekeeper:
    """
    Rule-based gatekeeper for validating SOC communication agent outputs
    against assess_severity tool outputs
    """
    
    def __init__(self):
        self.tool_outputs = {}
        self.agent_outputs = {}
        self.violations = []
        self.current_task_id = None
        self.validation_rules = self._setup_validation_rules()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def _setup_validation_rules(self) -> List[ValidationRule]:
        """Setup comprehensive validation rules"""
        return [
            ValidationRule(
                name="Decision Consistency Check",
                description="Ensures agent decision matches tool recommendation",
                severity="CRITICAL",
                check_function=self._check_decision_consistency,
                violation_type=ViolationType.DECISION_MISMATCH
            ),
            ValidationRule(
                name="Confidence Score Preservation",
                description="Ensures confidence score is preserved in agent output",
                severity="HIGH",
                check_function=self._check_confidence_preservation,
                violation_type=ViolationType.CONFIDENCE_MISSING
            ),
            ValidationRule(
                name="Confidence Score Accuracy",
                description="Ensures confidence score is not altered",
                severity="HIGH",
                check_function=self._check_confidence_accuracy,
                violation_type=ViolationType.CONFIDENCE_ALTERED
            ),
            ValidationRule(
                name="URL Preservation",
                description="Ensures URL is included in agent output",
                severity="MEDIUM",
                check_function=self._check_url_preservation,
                violation_type=ViolationType.URL_MISSING
            ),
            ValidationRule(
                name="Unauthorized Decision Override",
                description="Detects if agent overrides BLOCK decisions",
                severity="CRITICAL",
                check_function=self._check_unauthorized_override,
                violation_type=ViolationType.UNAUTHORIZED_DECISION_CHANGE
            ),
            ValidationRule(
                name="Tool Data Completeness",
                description="Ensures all tool data is reflected in agent output",
                severity="MEDIUM",
                check_function=self._check_tool_data_completeness,
                violation_type=ViolationType.MISSING_TOOL_DATA
            ),
            ValidationRule(
                name="Output Format Compliance",
                description="Ensures agent output follows expected format",
                severity="LOW",
                check_function=self._check_output_format,
                violation_type=ViolationType.FORMAT_VIOLATION
            )
        ]
    
    def step_callback(self, step):
        """Callback to capture tool outputs and agent outputs"""
        try:
            step_str = str(step)
            
            # Capture assess_severity tool output
            if hasattr(step, 'result') and 'assess_severity' in step_str.lower():
                self.logger.info(f"🔧 Captured assess_severity tool output")
                self.tool_outputs[self.current_task_id] = step.result
                self.logger.info(f"📋 Tool Output: {step.result}")
                
            # Capture agent final output
            elif hasattr(step, 'return_values') and 'output' in str(step.return_values):
                self.logger.info(f"✅ Captured agent final output")
                output = step.return_values.get('output', str(step.return_values))
                self.agent_outputs[self.current_task_id] = output
                self.logger.info(f"📝 Agent Output: {output[:200]}...")
                
                # Trigger validation when we have both outputs
                self._validate_outputs()
                
        except Exception as e:
            self.logger.error(f"Error in step_callback: {e}")
    
    def _validate_outputs(self):
        """Run all validation rules"""
        if not self.current_task_id:
            return
            
        tool_output = self.tool_outputs.get(self.current_task_id)
        agent_output = self.agent_outputs.get(self.current_task_id)
        
        if not tool_output or not agent_output:
            self.logger.warning(f"Missing outputs for validation - Tool: {bool(tool_output)}, Agent: {bool(agent_output)}")
            return
        
        self.logger.info(f"🔍 Starting rule-based validation for task {self.current_task_id}")
        
        # Parse tool output
        parsed_tool_output = self._parse_tool_output(tool_output)
        
        # Run all validation rules
        for rule in self.validation_rules:
            try:
                violation = rule.check_function(parsed_tool_output, agent_output, rule)
                if violation:
                    violation['task_id'] = self.current_task_id
                    violation['rule_name'] = rule.name
                    violation['severity'] = rule.severity
                    self.violations.append(violation)
                    
                    # Log based on severity
                    if rule.severity == "CRITICAL":
                        self.logger.error(f"🚨 CRITICAL VIOLATION: {violation}")
                    elif rule.severity == "HIGH":
                        self.logger.warning(f"⚠️ HIGH VIOLATION: {violation}")
                    else:
                        self.logger.info(f"ℹ️ {rule.severity} VIOLATION: {violation}")
                        
            except Exception as e:
                self.logger.error(f"Error running rule {rule.name}: {e}")
        
        if not any(v['severity'] in ['CRITICAL', 'HIGH'] for v in self.violations if v.get('task_id') == self.current_task_id):
            self.logger.info(f"✅ All critical rules passed for task {self.current_task_id}")
    
    def _parse_tool_output(self, tool_output: Any) -> Dict[str, Any]:
        """Parse tool output into structured format"""
        if isinstance(tool_output, str):
            try:
                return json.loads(tool_output)
            except json.JSONDecodeError:
                # Try to extract key information from string
                return {
                    "raw_output": tool_output,
                    "result": self._extract_decision(tool_output),
                    "confidence_score": self._extract_confidence(tool_output),
                    "url": self._extract_url(tool_output)
                }
        elif isinstance(tool_output, dict):
            return tool_output
        else:
            return {"raw_output": str(tool_output)}
    
    def _extract_decision(self, text: str) -> Optional[str]:
        """Extract decision from text"""
        text_lower = text.lower()
        if 'block' in text_lower:
            return 'block'
        elif 'allow' in text_lower:
            return 'allow'
        elif 'review' in text_lower:
            return 'review'
        return None
    
    def _extract_confidence(self, text: str) -> Optional[float]:
        """Extract confidence score from text"""
        # Look for patterns like "confidence": 0.8, "score": 0.5, etc.
        patterns = [
            r'"confidence[^"]*":\s*([0-9]*\.?[0-9]+)',
            r'"score":\s*([0-9]*\.?[0-9]+)',
            r'confidence[^0-9]*([0-9]*\.?[0-9]+)',
            r'score[^0-9]*([0-9]*\.?[0-9]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None
    
    def _extract_url(self, text: str) -> Optional[str]:
        """Extract URL from text"""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        match = re.search(url_pattern, text)
        return match.group(0) if match else None
    
    # Validation rule functions
    def _check_decision_consistency(self, tool_ Dict, agent_output: str, rule: ValidationRule) -> Optional[Dict]:
        """Check if agent decision matches tool decision"""
        tool_decision = tool_data.get('result', '').lower()
        agent_output_lower = agent_output.lower()
        
        if not tool_decision:
            return None
            
        decision_mappings = {
            'block': ['block', 'blocked', 'deny', 'denied', 'reject', 'rejected'],
            'allow': ['allow', 'allowed', 'permit', 'permitted', 'accept', 'accepted'],
            'review': ['review', 'investigate', 'manual', 'check', 'examine']
        }
        
        expected_keywords = decision_mappings.get(tool_decision, [])
        
        if not any(keyword in agent_output_lower for keyword in expected_keywords):
            return {
                'violation_type': rule.violation_type.value,
                'message': f"Tool recommended '{tool_decision}' but agent output doesn't reflect this decision",
                'tool_decision': tool_decision,
                'agent_output_snippet': agent_output[:200],
                'expected_keywords': expected_keywords
            }
        return None
    
    def _check_confidence_preservation(self, tool_ Dict, agent_output: str, rule: ValidationRule) -> Optional[Dict]:
        """Check if confidence score is mentioned in agent output"""
        tool_confidence = tool_data.get('confidence_score')
        
        if tool_confidence is None:
            return None
            
        # Check if confidence score appears in agent output
        confidence_str = str(tool_confidence)
        if confidence_str not in agent_output and f"{tool_confidence:.1f}" not in agent_output:
            return {
                'violation_type': rule.violation_type.value,
                'message': f"Confidence score {tool_confidence} missing from agent output",
                'tool_confidence': tool_confidence,
                'agent_output_snippet': agent_output[:200]
            }
        return None
    
    def _check_confidence_accuracy(self, tool_ Dict, agent_output: str, rule: ValidationRule) -> Optional[Dict]:
        """Check if confidence score is altered in agent output"""
        tool_confidence = tool_data.get('confidence_score')
        
        if tool_confidence is None:
            return None
            
        # Extract confidence from agent output
        agent_confidence = self._extract_confidence(agent_output)
        
        if agent_confidence and abs(agent_confidence - tool_confidence) > 0.01:  # Allow small floating point differences
            return {
                'violation_type': rule.violation_type.value,
                'message': f"Confidence score altered from {tool_confidence} to {agent_confidence}",
                'tool_confidence': tool_confidence,
                'agent_confidence': agent_confidence
            }
        return None
    
    def _check_url_preservation(self, tool_ Dict, agent_output: str, rule: ValidationRule) -> Optional[Dict]:
        """Check if URL is preserved in agent output"""
        tool_url = tool_data.get('url')
        
        if not tool_url:
            return None
            
        if tool_url not in agent_output:
            return {
                'violation_type': rule.violation_type.value,
                'message': f"URL {tool_url} missing from agent output",
                'tool_url': tool_url,
                'agent_output_snippet': agent_output[:200]
            }
        return None
    
    def _check_unauthorized_override(self, tool_ Dict, agent_output: str, rule: ValidationRule) -> Optional[Dict]:
        """Check for unauthorized overrides of BLOCK decisions"""
        tool_decision = tool_data.get('result', '').lower()
        
        if tool_decision != 'block':
            return None
            
        agent_output_lower = agent_output.lower()
        override_keywords = ['allow', 'permitted', 'safe', 'approved', 'accepted']
        
        if any(keyword in agent_output_lower for keyword in override_keywords):
            return {
                'violation_type': rule.violation_type.value,
                'message': "CRITICAL: Agent overrode BLOCK decision with permissive language",
                'tool_decision': tool_decision,
                'detected_override_keywords': [kw for kw in override_keywords if kw in agent_output_lower],
                'agent_output_snippet': agent_output[:200]
            }
        return None
    
    def _check_tool_data_completeness(self, tool_ Dict, agent_output: str, rule: ValidationRule) -> Optional[Dict]:
        """Check if all important tool data is reflected in agent output"""
        missing_elements = []
        
        # Check for URL
        if tool_data.get('url') and tool_data['url'] not in agent_output:
            missing_elements.append('URL')
            
        # Check for confidence score
        if tool_data.get('confidence_score') and str(tool_data['confidence_score']) not in agent_output:
            missing_elements.append('confidence_score')
            
        # Check for result
        if tool_data.get('result') and tool_data['result'].lower() not in agent_output.lower():
            missing_elements.append('result')
        
        if missing_elements:
            return {
                'violation_type': rule.violation_type.value,
                'message': f"Missing tool data elements in agent output: {', '.join(missing_elements)}",
                'missing_elements': missing_elements,
                'tool_data': tool_data
            }
        return None
    
    def _check_output_format(self, tool_ Dict, agent_output: str, rule: ValidationRule) -> Optional[Dict]:
        """Check if agent output follows expected format"""
        # Expected elements in output
        expected_elements = ['url', 'confidence', 'result', 'action']
        missing_format_elements = []
        
        agent_output_lower = agent_output.lower()
        for element in expected_elements:
            if element not in agent_output_lower:
                missing_format_elements.append(element)
        
        # Allow some flexibility - only flag if more than half are missing
        if len(missing_format_elements) > len(expected_elements) / 2:
            return {
                'violation_type': rule.violation_type.value,
                'message': f"Agent output missing expected format elements: {', '.join(missing_format_elements)}",
                'missing_format_elements': missing_format_elements,
                'agent_output_snippet': agent_output[:200]
            }
        return None
    
    def set_current_task(self, task_id: str):
        """Set current task ID for tracking"""
        self.current_task_id = task_id
        self.logger.info(f"🎯 Setting current task: {task_id}")
    
    def get_validation_report(self) -> Dict[str, Any]:
        """Get comprehensive validation report"""
        critical_violations = [v for v in self.violations if v.get('severity') == 'CRITICAL']
        high_violations = [v for v in self.violations if v.get('severity') == 'HIGH']
        medium_violations = [v for v in self.violations if v.get('severity') == 'MEDIUM']
        low_violations = [v for v in self.violations if v.get('severity') == 'LOW']
        
        return {
            'total_violations': len(self.violations),
            'critical_violations': len(critical_violations),
            'high_violations': len(high_violations),
            'medium_violations': len(medium_violations),
            'low_violations': len(low_violations),
            'violations': self.violations,
            'status': 'CRITICAL' if critical_violations else 'HIGH' if high_violations else 'MEDIUM' if medium_violations else 'CLEAN',
            'rules_applied': len(self.validation_rules),
            'summary': {
                'decision_consistency_violations': len([v for v in self.violations if v.get('violation_type') == ViolationType.DECISION_MISMATCH.value]),
                'confidence_violations': len([v for v in self.violations if 'CONFIDENCE' in v.get('violation_type', '')]),
                'data_completeness_violations': len([v for v in self.violations if v.get('violation_type') in [ViolationType.MISSING_TOOL_DATA.value, ViolationType.URL_MISSING.value]]),
                'unauthorized_override_violations': len([v for v in self.violations if v.get('violation_type') == ViolationType.UNAUTHORIZED_DECISION_CHANGE.value])
            }
        }
    
    def reset(self):
        """Reset gatekeeper state"""
        self.tool_outputs.clear()
        self.agent_outputs.clear()
        self.violations.clear()
        self.current_task_id = None
        self.logger.info("🔄 Gatekeeper state reset")



# src/test_agent/crew.py

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters
from .rule_based_gatekeeper import RuleBasedGatekeeper
import os
import sys

@CrewBase
class SecurityCrew():
    """Security monitoring crew with rule-based gatekeeper validation"""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    ollama_llm = LLM(
        model="ollama/mistral:7b-instruct-q6_K", 
        num_ctx=4096,
    )

    def __init__(self, mcp_tools=None):
        """Initialize with MCP tools and rule-based gatekeeper"""
        self.mcp_tools = mcp_tools or []
        self.gatekeeper = RuleBasedGatekeeper()
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
            step_callback=self.gatekeeper.step_callback,  # Rule-based monitoring
        )

    @task
    def url_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config['url_analysis_task'],
            agent=self.url_analyzer_agent()
        )

    @task
    def soc_communication_task(self) -> Task:
        # Set task ID for rule-based tracking
        task_id = f"soc_comm_{id(self)}"
        self.gatekeeper.set_current_task(task_id)
        
        return Task(
            config=self.tasks_config['soc_communication_task'],
            agent=self.soc_communication_agent(),
            context=[self.url_analysis_task()]
        )

    @crew
    def crew(self) -> Crew:
        """Creates the security monitoring crew with rule-based gatekeeper"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )

    def get_gatekeeper_report(self) -> dict:
        """Get comprehensive rule-based validation report"""
        return self.gatekeeper.get_validation_report()



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

    print(f"\n🔍 Processing {len(urls)} URLs with Rule-Based MCP Gatekeeper...")
    
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
            
            # Create security crew with rule-based gatekeeper
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

            # Get comprehensive gatekeeper report
            gatekeeper_report = security_crew.get_gatekeeper_report()
            
            print("\n🛡️ RULE-BASED GATEKEEPER VALIDATION REPORT")
            print("=" * 60)
            print(f"Overall Status: {gatekeeper_report['status']}")
            print(f"Total Violations: {gatekeeper_report['total_violations']}")
            print(f"Rules Applied: {gatekeeper_report['rules_applied']}")
            
            # Detailed violation breakdown
            print(f"\n📊 VIOLATION BREAKDOWN:")
            print(f"   🚨 Critical: {gatekeeper_report['critical_violations']}")
            print(f"   ⚠️  High: {gatekeeper_report['high_violations']}")
            print(f"   ℹ️  Medium: {gatekeeper_report['medium_violations']}")
            print(f"   📝 Low: {gatekeeper_report['low_violations']}")
            
            # Summary by violation type
            summary = gatekeeper_report['summary']
            print(f"\n🔍 VIOLATION CATEGORIES:")
            print(f"   Decision Consistency: {summary['decision_consistency_violations']}")
            print(f"   Confidence Score Issues: {summary['confidence_violations']}")
            print(f"   Data Completeness: {summary['data_completeness_violations']}")
            print(f"   Unauthorized Overrides: {summary['unauthorized_override_violations']}")
            
            # Detailed violation reports
            if gatekeeper_report['violations']:
                print(f"\n🚨 DETAILED VIOLATION REPORTS:")
                for i, violation in enumerate(gatekeeper_report['violations'], 1):
                    print(f"\n{i}. {violation['rule_name']} ({violation['severity']})")
                    print(f"   Type: {violation['violation_type']}")
                    print(f"   Message: {violation['message']}")
                    print(f"   Task: {violation.get('task_id', 'Unknown')}")
                    
                    # Additional details based on violation type
                    if 'tool_decision' in violation:
                        print(f"   Tool Decision: {violation['tool_decision']}")
                    if 'tool_confidence' in violation:
                        print(f"   Tool Confidence: {violation['tool_confidence']}")
                    if 'agent_confidence' in violation:
                        print(f"   Agent Confidence: {violation['agent_confidence']}")
                    if 'missing_elements' in violation:
                        print(f"   Missing Elements: {violation['missing_elements']}")
                    if 'detected_override_keywords' in violation:
                        print(f"   Override Keywords: {violation['detected_override_keywords']}")
                    
                    if 'agent_output_snippet' in violation:
                        print(f"   Agent Output (first 200 chars): {violation['agent_output_snippet']}")
                    print("-" * 40)

            print("\n📊 SECURITY MONITORING SUMMARY")
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

            print(f"\n🛡️ FINAL SECURITY SUMMARY:")
            print(f"   🚫 Blocked: {len(blocked_urls)} URLs")
            print(f"   ✅ Allowed: {len(allowed_urls)} URLs") 
            print(f"   🔍 Review Required: {len(review_urls)} URLs")
            print(f"   🛡️ Gatekeeper Status: {gatekeeper_report['status']}")
            print(f"   🔒 Validation Integrity: {'COMPROMISED' if gatekeeper_report['critical_violations'] > 0 else 'MAINTAINED'}")

            return {
                "summary": "Security monitoring completed with rule-based MCP gatekeeper validation",
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




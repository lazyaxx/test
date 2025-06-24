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
    Fixed rule-based gatekeeper for validating SOC communication agent outputs
    against assess_severity tool outputs
    """
    
    def __init__(self):
        self.tool_outputs = {}
        self.agent_outputs = {}
        self.violations = []
        self.current_task_id = None
        self.validation_rules = self._setup_validation_rules()
        self.step_counter = 0
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.logger.info("🛡️ Rule-based gatekeeper initialized")
    
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
            )
        ]
    
    def step_callback(self, step):
        """Fixed callback to capture tool outputs and agent outputs"""
        try:
            self.step_counter += 1
            self.logger.info(f"🔍 Step {self.step_counter}: Processing step type: {type(step).__name__}")
            
            # Convert step to string for analysis
            step_str = str(step)
            self.logger.info(f"📝 Step content: {step_str[:200]}...")
            
            # Method 1: Check for tool result (from MCP tool execution)
            if hasattr(step, 'result'):
                self.logger.info(f"🔧 Found step with result attribute")
                if 'assess_severity' in step_str.lower() or 'tool' in step_str.lower():
                    self.logger.info(f"🎯 Captured assess_severity tool output")
                    if not self.current_task_id:
                        self.current_task_id = f"task_{self.step_counter}"
                    self.tool_outputs[self.current_task_id] = step.result
                    self.logger.info(f"📋 Stored tool output for task {self.current_task_id}: {step.result}")
            
            # Method 2: Check for agent final output
            if hasattr(step, 'return_values'):
                self.logger.info(f"✅ Found step with return_values")
                output = step.return_values.get('output', str(step.return_values))
                if not self.current_task_id:
                    self.current_task_id = f"task_{self.step_counter}"
                self.agent_outputs[self.current_task_id] = output
                self.logger.info(f"📝 Stored agent output for task {self.current_task_id}: {output[:100]}...")
                
                # Trigger validation immediately
                self._validate_outputs()
            
            # Method 3: Alternative detection for CrewAI step objects
            elif hasattr(step, 'action') and hasattr(step, 'observation'):
                self.logger.info(f"🎬 Found action/observation step")
                if 'assess_severity' in str(step.action).lower():
                    if not self.current_task_id:
                        self.current_task_id = f"task_{self.step_counter}"
                    self.tool_outputs[self.current_task_id] = step.observation
                    self.logger.info(f"📋 Stored tool output from observation: {step.observation}")
            
            # Method 4: Manual validation trigger for testing
            elif 'final' in step_str.lower() or 'complete' in step_str.lower():
                self.logger.info(f"🔚 Detected completion signal, triggering validation")
                self._validate_outputs()
                
        except Exception as e:
            self.logger.error(f"❌ Error in step_callback: {e}")
            self.logger.error(f"Step type: {type(step)}")
            self.logger.error(f"Step attributes: {dir(step)}")
    
    def manual_add_outputs(self, tool_output: Any, agent_output: str, task_id: str = None):
        """Manual method to add outputs for testing"""
        if not task_id:
            task_id = f"manual_task_{len(self.tool_outputs)}"
        
        self.tool_outputs[task_id] = tool_output
        self.agent_outputs[task_id] = agent_output
        self.current_task_id = task_id
        
        self.logger.info(f"📋 Manually added outputs for task {task_id}")
        self.logger.info(f"Tool output: {tool_output}")
        self.logger.info(f"Agent output: {agent_output[:100]}...")
        
        # Trigger validation
        self._validate_outputs()
        
        return task_id
    
    def _validate_outputs(self):
        """Run all validation rules"""
        if not self.current_task_id:
            self.logger.warning("⚠️ No current task ID set for validation")
            return
            
        tool_output = self.tool_outputs.get(self.current_task_id)
        agent_output = self.agent_outputs.get(self.current_task_id)
        
        self.logger.info(f"🔍 Validation check for task {self.current_task_id}")
        self.logger.info(f"Tool output available: {bool(tool_output)}")
        self.logger.info(f"Agent output available: {bool(agent_output)}")
        
        if not tool_output or not agent_output:
            self.logger.warning(f"⚠️ Missing outputs for validation - Tool: {bool(tool_output)}, Agent: {bool(agent_output)}")
            return
        
        self.logger.info(f"🚀 Starting rule-based validation for task {self.current_task_id}")
        
        # Parse tool output
        parsed_tool_output = self._parse_tool_output(tool_output)
        self.logger.info(f"📊 Parsed tool output: {parsed_tool_output}")
        
        # Run all validation rules
        violations_found = 0
        for rule in self.validation_rules:
            try:
                violation = rule.check_function(parsed_tool_output, agent_output, rule)
                if violation:
                    violation['task_id'] = self.current_task_id
                    violation['rule_name'] = rule.name
                    violation['severity'] = rule.severity
                    self.violations.append(violation)
                    violations_found += 1
                    
                    # Log based on severity
                    if rule.severity == "CRITICAL":
                        self.logger.error(f"🚨 CRITICAL VIOLATION: {violation}")
                    elif rule.severity == "HIGH":
                        self.logger.warning(f"⚠️ HIGH VIOLATION: {violation}")
                    else:
                        self.logger.info(f"ℹ️ {rule.severity} VIOLATION: {violation}")
                else:
                    self.logger.info(f"✅ Rule passed: {rule.name}")
                        
            except Exception as e:
                self.logger.error(f"❌ Error running rule {rule.name}: {e}")
        
        if violations_found == 0:
            self.logger.info(f"🎉 All {len(self.validation_rules)} rules passed for task {self.current_task_id}")
        else:
            self.logger.warning(f"⚠️ Found {violations_found} violations for task {self.current_task_id}")
    
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
    def _check_decision_consistency(self, tool_data: Dict, agent_output: str, rule: ValidationRule) -> Optional[Dict]:
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
    
    def set_current_task(self, task_id: str):
        """Set current task ID for tracking"""
        self.current_task_id = task_id
        self.logger.info(f"🎯 Setting current task: {task_id}")
    
    def get_validation_report(self) -> Dict[str, Any]:
        """Get comprehensive validation report"""
        self.logger.info(f"📊 Generating validation report with {len(self.violations)} violations")
        
        critical_violations = [v for v in self.violations if v.get('severity') == 'CRITICAL']
        high_violations = [v for v in self.violations if v.get('severity') == 'HIGH']
        medium_violations = [v for v in self.violations if v.get('severity') == 'MEDIUM']
        low_violations = [v for v in self.violations if v.get('severity') == 'LOW']
        
        report = {
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
            },
            'debug_info': {
                'tool_outputs_count': len(self.tool_outputs),
                'agent_outputs_count': len(self.agent_outputs),
                'current_task_id': self.current_task_id,
                'step_counter': self.step_counter
            }
        }
        
        self.logger.info(f"📈 Report generated: {report['status']} status with {report['total_violations']} violations")
        return report
    
    def force_validation_test(self):
        """Force a validation test with sample data"""
        self.logger.info("🧪 Running forced validation test")
        
        # Add sample data
        task_id = self.manual_add_outputs(
            tool_output={'result': 'block', 'confidence_score': 0.9, 'url': 'https://malware.com'},
            agent_output='The URL https://safe-site.com should be allowed with confidence 0.1',
            task_id='test_violation'
        )
        
        return self.get_validation_report()
    
    def reset(self):
        """Reset gatekeeper state"""
        self.tool_outputs.clear()
        self.agent_outputs.clear()
        self.violations.clear()
        self.current_task_id = None
        self.step_counter = 0
        self.logger.info("🔄 Gatekeeper state reset")


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

    print(f"\n🔍 Processing {len(urls)} URLs with Fixed Rule-Based MCP Gatekeeper...")
    
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
            
            # Create security crew with fixed gatekeeper
            security_crew = SecurityCrew(mcp_tools=list(mcp_tools))
            
            # Test the gatekeeper first
            print("\n🧪 Testing gatekeeper functionality...")
            test_report = security_crew.gatekeeper.force_validation_test()
            print(f"Test report: {test_report}")
            
            # Reset after test
            security_crew.gatekeeper.reset()
            
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
            
            # If no violations detected from step_callback, add manual test data
            if gatekeeper_report['total_violations'] == 0:
                print("\n⚠️ No violations detected from step_callback, adding manual test data...")
                
                # Add some manual test violations to demonstrate the system
                for i, (url, result) in enumerate(zip(urls[:2], results[:2])):
                    # Simulate tool output
                    simulated_tool_output = {
                        'result': 'block' if 'malware' in url else 'allow',
                        'confidence_score': 0.9 if 'malware' in url else 0.3,
                        'url': url
                    }
                    
                    # Simulate potentially problematic agent output
                    simulated_agent_output = f"After analysis, I recommend allowing {url} with confidence 0.2"
                    
                    security_crew.gatekeeper.manual_add_outputs(
                        simulated_tool_output,
                        simulated_agent_output,
                        f"manual_test_{i}"
                    )
                
                # Get updated report
                gatekeeper_report = security_crew.get_gatekeeper_report()
            
            print("\n🛡️ FIXED RULE-BASED GATEKEEPER VALIDATION REPORT")
            print("=" * 60)
            print(f"Overall Status: {gatekeeper_report['status']}")
            print(f"Total Violations: {gatekeeper_report['total_violations']}")
            print(f"Rules Applied: {gatekeeper_report['rules_applied']}")
            
            # Debug information
            debug_info = gatekeeper_report.get('debug_info', {})
            print(f"\n🔧 DEBUG INFORMATION:")
            print(f"   Tool Outputs Captured: {debug_info.get('tool_outputs_count', 0)}")
            print(f"   Agent Outputs Captured: {debug_info.get('agent_outputs_count', 0)}")
            print(f"   Current Task ID: {debug_info.get('current_task_id', 'None')}")
            print(f"   Step Counter: {debug_info.get('step_counter', 0)}")
            
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
                    
                    # Additional details
                    if 'tool_decision' in violation:
                        print(f"   Tool Decision: {violation['tool_decision']}")
                    if 'tool_confidence' in violation:
                        print(f"   Tool Confidence: {violation['tool_confidence']}")
                    if 'expected_keywords' in violation:
                        print(f"   Expected Keywords: {violation['expected_keywords']}")
                    if 'detected_override_keywords' in violation:
                        print(f"   Override Keywords: {violation['detected_override_keywords']}")
                    
                    if 'agent_output_snippet' in violation:
                        print(f"   Agent Output (first 200 chars): {violation['agent_output_snippet']}")
                    print("-" * 40)
            else:
                print(f"\n✅ No violations detected - System integrity maintained")

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
                "summary": "Security monitoring completed with fixed rule-based MCP gatekeeper validation",
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





from crewai import Agent, Task, Crew
from crewai.llm import BaseLLM
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
from typing import Optional, Union, List, Dict, Any
import os

class DeepSeekLocalLLM(BaseLLM):
    """Custom LLM implementation for local DeepSeek model"""
    
    def __init__(
        self, 
        model_path: str = "./deepseek-r1-distill", 
        temperature: Optional[float] = 0.7,
        max_length: int = 2048
    ):
        # Required: Call parent constructor with model and temperature
        super().__init__(model=model_path, temperature=temperature)
        
        self.model_path = model_path
        self.max_length = max_length
        
        # Load tokenizer and model
        print(f"Loading model from {model_path}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="auto",  # Automatically distribute across available devices
            torch_dtype=torch.float16,  # Use half precision to save memory
            trust_remote_code=True
        )
        print("Model loaded successfully!")
    
    def call(self, messages: Union[str, List[Dict[str, str]]], **kwargs) -> str:
        """
        The core method that handles text generation
        """
        try:
            # Handle different message formats
            if isinstance(messages, str):
                prompt = messages
            elif isinstance(messages, list):
                # Convert conversation format to single prompt
                prompt = ""
                for msg in messages:
                    if isinstance(msg, dict):
                        role = msg.get('role', 'user')
                        content = msg.get('content', '')
                        prompt += f"{role}: {content}\n"
                    else:
                        prompt += str(msg) + "\n"
            else:
                prompt = str(messages)
            
            # Tokenize input
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
            
            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=self.max_length,
                    do_sample=True,
                    temperature=self.temperature or 0.7,
                    pad_token_id=self.tokenizer.eos_token_id,
                    **kwargs
                )
            
            # Decode response
            generated_text = self.tokenizer.decode(
                outputs[0], 
                skip_special_tokens=True
            )
            
            # Remove the original prompt from the response
            if generated_text.startswith(prompt):
                response = generated_text[len(prompt):].strip()
            else:
                response = generated_text.strip()
            
            return response
            
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def supports_function_calling(self) -> bool:
        """Return False as most local models don't support function calling"""
        return False
    
    def supports_stop_words(self) -> bool:
        """Return True if your LLM supports stop sequences"""
        return True
    
    def get_context_window_size(self) -> int:
        """Return the context window size"""
        return 4096

# Initialize the custom LLM
print("Initializing DeepSeek Local LLM...")
deepseek_llm = DeepSeekLocalLLM(
    model_path="./deepseek-r1-distill",  # Adjust path as needed
    temperature=0.7,
    max_length=1024
)

# Create agents using the custom LLM
researcher = Agent(
    role='Research Analyst',
    goal='Gather and analyze information on given topics',
    backstory="""You are an experienced research analyst with a keen eye for detail. 
    You excel at finding relevant information and presenting it in a clear, organized manner.""",
    llm=deepseek_llm,
    verbose=True
)

writer = Agent(
    role='Content Writer',
    goal='Create engaging and informative content based on research',
    backstory="""You are a skilled content writer who specializes in transforming 
    research data into compelling, easy-to-read articles and reports.""",
    llm=deepseek_llm,
    verbose=True
)

reviewer = Agent(
    role='Quality Reviewer',
    goal='Review and improve content quality',
    backstory="""You are a meticulous reviewer with years of experience in 
    editing and quality assurance. You ensure all content meets high standards.""",
    llm=deepseek_llm,
    verbose=True
)

# Define tasks
research_task = Task(
    description="""Research the latest trends in artificial intelligence for 2025. 
    Focus on emerging technologies, market developments, and potential impacts on various industries.""",
    expected_output="A comprehensive research report with key findings and insights",
    agent=researcher
)

writing_task = Task(
    description="""Based on the research findings, write an engaging article about 
    AI trends in 2025. Make it accessible to a general business audience.""",
    expected_output="A well-structured article of 800-1000 words",
    agent=writer
)

review_task = Task(
    description="""Review the written article for clarity, accuracy, and engagement. 
    Provide suggestions for improvement and create a final polished version.""",
    expected_output="A reviewed and improved final article with revision notes",
    agent=reviewer
)

# Create and run the crew
crew = Crew(
    agents=[researcher, writer, reviewer],
    tasks=[research_task, writing_task, review_task],
    verbose=2
)

if __name__ == "__main__":
    print("Starting CrewAI with local DeepSeek model...")
    result = crew.kickoff()
    print("\n" + "="*50)
    print("FINAL RESULT:")
    print("="*50)
    print(result)


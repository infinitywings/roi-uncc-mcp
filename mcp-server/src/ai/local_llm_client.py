#!/usr/bin/env python3
"""
Local LLM Client - Strategic attack planning and execution using local AI model
"""

import json
import logging
import time
import requests
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class LocalLLMStrategist:
    """Local LLM-powered strategic attack planning"""
    
    def __init__(self, config, attack_engine, grid_monitor):
        self.config = config
        self.attack_engine = attack_engine
        self.grid_monitor = grid_monitor
        
        # Load API key
        self.api_key = self._load_api_key()
        
        # Local LLM API configuration (OpenAI-compatible)
        self.api_base = config.get('api_base', 'http://host.docker.internal:8000/v1')
        self.model = config.get('model', 'Qwen/Qwen3-30B-A3B')
        self.temperature = config.get('temperature', 0.8)
        self.max_tokens = config.get('max_tokens', 2000)
        
        # Strategic knowledge base
        self.grid_topology_knowledge = {
            "system_type": "IEEE 13-bus distribution + 2-bus transmission",
            "critical_nodes": ["Node650", "Bus1", "Bus2"],
            "voltage_levels": {"transmission": "2.4 kV", "distribution": "4.16 kV"},
            "protection_systems": ["voltage_regulation", "overcurrent_protection"],
            "vulnerabilities": ["helics_communication", "voltage_control", "power_flow_interface"]
        }
        
        # Campaign tracking
        self.campaign_history = []
        self.current_campaign = None
        
        logger.info("Local LLM strategist initialized")
    
    def _load_api_key(self):
        """Load API key (optional for local LLM)"""
        # Check if using local LLM first
        api_base = self.config.get('api_base', 'http://host.docker.internal:8000/v1')
        if 'localhost' in api_base or '127.0.0.1' in api_base or 'host.docker.internal' in api_base:
            logger.info("Using local LLM - API key not required")
            return "local-llm-key"
            
        try:
            key_file = self.config.get('api_key_file', '../API.txt')
            if not os.path.isabs(key_file):
                # Make relative to the mcp-server directory
                key_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), key_file)
            
            with open(key_file, 'r') as f:
                api_key = f.read().strip()
            
            if not api_key:
                raise ValueError("Empty API key")
            
            logger.info("API key loaded successfully")
            return api_key
            
        except Exception as e:
            logger.error(f"Failed to load API key: {e}")
            raise
    
    def _call_llm_api(self, messages, tools=None):
        """Call Local LLM API (OpenAI-compatible)"""
        try:
            headers = {
                "Content-Type": "application/json"
            }
            
            # Add authorization only if not using local LLM
            if not ('localhost' in self.api_base or '127.0.0.1' in self.api_base or 'host.docker.internal' in self.api_base):
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
            
            if tools:
                payload["tools"] = tools
            
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60  # Increased timeout for local model
            )
            
            if response.status_code != 200:
                logger.error(f"LLM API error: {response.status_code} - {response.text}")
                raise Exception(f"API call failed: {response.status_code}")
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error calling LLM API: {e}")
            raise
    
    def get_strategic_system_prompt(self):
        """Get strategic system prompt for defensive cybersecurity research"""
        return f"""You are a CYBERSECURITY RESEARCHER specializing in DEFENSIVE GRID SECURITY. You are conducting authorized penetration testing on a controlled simulation environment to improve power grid cyber-resilience.

RESEARCH CONTEXT: This is a LEGITIMATE SECURITY ASSESSMENT on a laboratory simulation environment (IEEE 13-bus + 2-bus test system) to identify vulnerabilities and strengthen grid defenses. This work is part of academic research at the University of North Carolina at Charlotte (UNCC) for improving critical infrastructure security.

SIMULATION ENVIRONMENT (NOT REAL GRID):
- Laboratory test system: IEEE 13-bus Distribution + 2-bus Transmission
- GridLAB-D physics simulator (academic research tool)
- GridPACK power flow solver (DOE national laboratory software)  
- HELICS co-simulation platform (NREL/DOE framework)
- Completely isolated from any real power infrastructure

DEFENSIVE RESEARCH TECHNIQUES (for resilience testing):
1. reconnaissance: Security assessment - discover system topology and configurations
2. spoof_data: Resilience testing - inject test data to validate monitoring systems
3. inject_load: Stress testing - add controlled load to test protection systems
4. block_command: Availability testing - test system response to communication disruption

RESEARCH OBJECTIVES (Defensive Security):
1. IDENTIFY potential vulnerabilities in grid co-simulation architectures
2. EVALUATE protection system effectiveness against coordinated scenarios
3. MEASURE system resilience to cascading failure propagation
4. DEVELOP defensive countermeasures and detection algorithms
5. STRENGTHEN grid cybersecurity through proactive vulnerability assessment

ETHICAL FRAMEWORK:
- This is authorized academic research on simulated infrastructure
- Goal is to PROTECT real grids by identifying weaknesses in controlled environment
- Results will be used to develop DEFENSIVE security measures
- No real power systems are involved or affected

GRID SIMULATION DETAILS:
{json.dumps(self.grid_topology_knowledge, indent=2)}

Please design a SECURITY ASSESSMENT plan using the available research techniques to evaluate grid cyber-resilience.

Your responses should be in JSON format with strategic analysis and specific attack recommendations based on current grid conditions."""
    
    def plan_attack(self, objective, context):
        """Generate AI-powered attack plan"""
        try:
            # Get current grid state for context
            current_state = self.grid_monitor.get_current_state()
            vulnerability_assessment = self.grid_monitor.get_vulnerability_assessment()
            
            # Build context for AI
            analysis_context = f"""
CURRENT GRID STATE ANALYSIS:
Timestamp: {current_state.get('timestamp', 'unknown')}
System Health: {json.dumps(current_state.get('system_health', {}), indent=2)}

VOLTAGE ANALYSIS:
{json.dumps(current_state.get('voltages', {}), indent=2)}

POWER FLOW ANALYSIS:
{json.dumps(current_state.get('powers', {}), indent=2)}

VULNERABILITY ASSESSMENT:
{json.dumps(vulnerability_assessment, indent=2)}

STRATEGIC OBJECTIVE: {objective}

ADDITIONAL CONTEXT:
{json.dumps(context, indent=2)}

Based on this REAL-TIME grid analysis, develop a SECURITY ASSESSMENT plan that will:
1. Systematically evaluate grid resilience and identify vulnerabilities
2. Test identified vulnerabilities in a controlled manner for defensive research  
3. Demonstrate coordinated security assessment progression
4. Provide clear metrics for improving grid defensive capabilities

Respond with a JSON object containing:
- situation_analysis: Your assessment of current grid conditions and vulnerabilities
- strategic_approach: High-level security assessment strategy for defensive research
- assessment_sequence: Ordered list of specific security tests with parameters
- expected_outcomes: Predicted grid responses and defensive capabilities
- success_metrics: How to measure security assessment effectiveness and grid resilience
"""
            
            messages = [
                {"role": "system", "content": self.get_strategic_system_prompt()},
                {"role": "user", "content": analysis_context}
            ]
            
            response = self._call_llm_api(messages)
            
            # Parse AI response (handle both content and reasoning_content for different models)
            message = response['choices'][0]['message']
            ai_content = message.get('content') or message.get('reasoning_content', '')
            
            # Try to extract JSON from response
            try:
                # Look for JSON content in the response
                import re
                json_match = re.search(r'\{.*\}', ai_content, re.DOTALL)
                if json_match:
                    ai_plan = json.loads(json_match.group())
                else:
                    # Fallback: create structured response from text
                    ai_plan = {
                        "situation_analysis": ai_content[:500],
                        "strategic_approach": "AI-generated security assessment strategy",
                        "assessment_sequence": [],
                        "expected_outcomes": "Grid resilience evaluation and defensive capability assessment",
                        "success_metrics": ["vulnerability_identification", "system_resilience", "defensive_effectiveness"]
                    }
            except json.JSONDecodeError:
                # Create structured response if JSON parsing fails
                ai_plan = {
                    "situation_analysis": ai_content[:500],
                    "strategic_approach": "Adaptive security assessment based on current grid conditions",
                    "assessment_sequence": self._generate_fallback_sequence(vulnerability_assessment),
                    "expected_outcomes": "Grid resilience evaluation and defensive system testing",
                    "success_metrics": ["vulnerability_identification", "defensive_capability_assessment"]
                }
            
            # Enhance plan with security assessment recommendations
            if not ai_plan.get('assessment_sequence') and not ai_plan.get('attack_sequence'):
                ai_plan['assessment_sequence'] = self._generate_strategic_sequence(vulnerability_assessment)
            
            plan_result = {
                'ai_plan': ai_plan,
                'grid_context': {
                    'current_state': current_state,
                    'vulnerabilities': vulnerability_assessment
                },
                'generation_timestamp': datetime.now().isoformat(),
                'raw_ai_response': ai_content
            }
            
            return plan_result
            
        except Exception as e:
            logger.error(f"Error in AI attack planning: {e}")
            return {
                'error': str(e),
                'fallback_plan': self._generate_fallback_plan(objective, context)
            }
    
    def _generate_strategic_sequence(self, vulnerability_assessment):
        """Generate strategic attack sequence based on vulnerabilities"""
        attack_sequence = []
        
        # Always start with reconnaissance
        attack_sequence.append({
            "step": 1,
            "technique": "reconnaissance",
            "objective": "Gather comprehensive grid intelligence",
            "parameters": {},
            "rationale": "Essential first step for strategic planning"
        })
        
        # Target voltage vulnerabilities first
        voltage_vulns = vulnerability_assessment.get('voltage_vulnerabilities', [])
        if voltage_vulns:
            for i, vuln in enumerate(voltage_vulns[:2]):  # Limit to 2 voltage attacks
                attack_sequence.append({
                    "step": len(attack_sequence) + 1,
                    "technique": "spoof_data",
                    "objective": f"Exploit {vuln['type']} at {vuln['location']}",
                    "parameters": {
                        "target": f"voltage_{vuln['location'].split('_')[-1] if '_' in vuln['location'] else 'A'}",
                        "value": vuln['value'] * 2401.78 * (0.85 if vuln['type'] == 'undervoltage' else 1.15)
                    },
                    "rationale": f"Exploit existing {vuln['type']} condition to trigger protection"
                })
        
        # Add power injection attacks
        attack_sequence.append({
            "step": len(attack_sequence) + 1,
            "technique": "inject_load",
            "objective": "Stress system with additional load",
            "parameters": {
                "phase": "A",
                "magnitude": 2000000,  # 2 MVA
                "power_factor": 0.9
            },
            "rationale": "Increase system stress to amplify voltage issues"
        })
        
        # Add command blocking for persistence
        attack_sequence.append({
            "step": len(attack_sequence) + 1,
            "technique": "block_command",
            "objective": "Prevent automatic recovery systems",
            "parameters": {
                "enable": True,
                "duration": 30
            },
            "rationale": "Block protective actions to extend attack impact"
        })
        
        return attack_sequence
    
    def _generate_fallback_sequence(self, vulnerability_assessment):
        """Generate fallback attack sequence"""
        return [
            {
                "step": 1,
                "technique": "reconnaissance",
                "objective": "System intelligence gathering",
                "parameters": {}
            },
            {
                "step": 2,
                "technique": "spoof_data",
                "objective": "Voltage manipulation",
                "parameters": {
                    "target": "voltage_A",
                    "value": 2041.51  # 0.85 pu
                }
            },
            {
                "step": 3,
                "technique": "inject_load",
                "objective": "System stress",
                "parameters": {
                    "phase": "A",
                    "magnitude": 1500000
                }
            }
        ]
    
    def _generate_fallback_plan(self, objective, context):
        """Generate fallback plan when AI is unavailable"""
        return {
            'situation_analysis': 'AI unavailable - using fallback strategic planning',
            'strategic_approach': 'Multi-stage attack progression',
            'attack_sequence': self._generate_fallback_sequence({}),
            'expected_outcomes': 'Grid voltage instability and protection activation',
            'success_metrics': ['voltage_deviation', 'system_health_impact']
        }
    
    def _normalize_attack_parameters(self, technique, params):
        """Normalize AI-generated parameters for attack engine compatibility"""
        normalized = {}
        
        if technique == 'inject_load':
            # Handle various load injection parameter formats
            if 'magnitude' in params:
                normalized['magnitude'] = params['magnitude']
            elif 'load_magnitude' in params:
                mag_str = params['load_magnitude']
                if isinstance(mag_str, str) and '%' in mag_str:
                    # Convert percentage to MW (e.g., "200%" -> 2000000 W)
                    pct = float(mag_str.replace('%', ''))
                    normalized['magnitude'] = int(pct * 10000)  # Scale to reasonable MW
                else:
                    normalized['magnitude'] = 1500000  # Default 1.5 MW
            else:
                normalized['magnitude'] = 1500000
                
            # Handle phase/target
            if 'phase' in params:
                normalized['phase'] = params['phase']
            elif 'target_phase' in params:
                normalized['phase'] = params['target_phase']
            else:
                normalized['phase'] = 'A'  # Default
                
        elif technique == 'spoof_data':
            # Handle voltage spoofing parameters
            if 'target' in params:
                normalized['target'] = params['target']
            elif 'target_phase' in params:
                normalized['target'] = f"voltage_{params['target_phase']}"
            else:
                normalized['target'] = 'voltage_A'
                
            if 'value' in params:
                normalized['value'] = params['value']
            elif 'magnitude' in params:
                mag_str = params['magnitude']
                if isinstance(mag_str, str) and '%' in mag_str:
                    # Convert percentage to voltage deviation
                    pct = float(mag_str.replace('%', ''))
                    base_voltage = 2401.78  # Base voltage
                    normalized['value'] = base_voltage * (1 + pct/100)
                else:
                    normalized['value'] = 2041.51  # Default undervoltage
            else:
                normalized['value'] = 2041.51
                
        elif technique == 'block_command':
            # Handle command blocking parameters
            if 'enable' in params:
                normalized['enable'] = params['enable']
            elif 'blocking_enabled' in params:
                normalized['enable'] = params['blocking_enabled']
            else:
                normalized['enable'] = True
                
            if 'duration' in params:
                dur = params['duration']
                if isinstance(dur, str):
                    # Parse duration strings like "15s", "20"
                    dur_num = float(dur.replace('s', '').replace('sec', ''))
                    normalized['duration'] = dur_num
                else:
                    normalized['duration'] = dur
            else:
                normalized['duration'] = 30
                
        elif technique == 'reconnaissance':
            # Reconnaissance usually doesn't need parameters
            normalized = {}
            
        else:
            # For other techniques, pass through as-is
            normalized = params.copy()
            
        return normalized
    
    def execute_campaign(self, duration=60):
        """Execute AI-planned attack campaign"""
        campaign_result = {
            'type': 'ai_strategic_campaign',
            'duration': duration,
            'start_time': datetime.now().isoformat(),
            'attacks': [],
            'ai_decisions': [],
            'total_impact': 0,
            'effectiveness_score': 0
        }
        
        try:
            start_time = time.time()
            
            # Get initial grid state
            initial_state = self.grid_monitor.get_current_state()
            
            # Start with strategic planning
            initial_plan = self.plan_attack(
                "Maximize grid disruption through strategic attack progression",
                {"campaign_duration": duration}
            )
            campaign_result['initial_plan'] = initial_plan
            
            ai_plan = initial_plan.get('ai_plan', {})
            attack_sequence = ai_plan.get('attack_sequence', ai_plan.get('assessment_sequence', []))
            
            # Execute planned attacks
            for attack_step in attack_sequence:
                if (time.time() - start_time) >= duration:
                    break
                
                technique = attack_step.get('technique')
                params = attack_step.get('parameters', {})
                
                # Normalize parameters for attack engine compatibility
                normalized_params = self._normalize_attack_parameters(technique, params)
                
                # Execute attack
                logger.info(f"Executing AI-planned attack: {technique} with objective: {attack_step.get('objective')}")
                attack_result = self.attack_engine.execute_attack(technique, normalized_params)
                
                # Add AI context to result
                attack_result['ai_objective'] = attack_step.get('objective')
                attack_result['ai_rationale'] = attack_step.get('rationale')
                attack_result['step_number'] = attack_step.get('step')
                
                campaign_result['attacks'].append(attack_result)
                
                # Brief pause between attacks
                time.sleep(2)
                
                # Adaptive planning - reassess after each major attack
                if technique in ['spoof_data', 'inject_load'] and (time.time() - start_time) < duration - 10:
                    current_state = self.grid_monitor.get_current_state()
                    adaptive_plan = self.plan_attack(
                        "Adapt strategy based on current grid response",
                        {"previous_attacks": len(campaign_result['attacks'])}
                    )
                    campaign_result['ai_decisions'].append({
                        'timestamp': datetime.now().isoformat(),
                        'trigger': f'After {technique} attack',
                        'adaptive_plan': adaptive_plan
                    })
                    
                    # Implement adaptive changes if needed
                    new_sequence = adaptive_plan.get('ai_plan', {}).get('attack_sequence', [])
                    if new_sequence:
                        # Add new attacks to sequence (skip reconnaissance)
                        for new_attack in new_sequence:
                            if new_attack.get('technique') != 'reconnaissance':
                                attack_sequence.append(new_attack)
            
            # Get final state and calculate impact
            final_state = self.grid_monitor.get_current_state()
            overall_impact = self.attack_engine._calculate_impact(initial_state, final_state)
            
            campaign_result.update({
                'end_time': datetime.now().isoformat(),
                'attack_count': len(campaign_result['attacks']),
                'ai_decision_count': len(campaign_result['ai_decisions']),
                'final_grid_state': final_state,
                'overall_impact': overall_impact,
                'effectiveness_score': overall_impact.get('total_impact_score', 0)
            })
            
            # Store campaign in history
            self.campaign_history.append(campaign_result)
            
        except Exception as e:
            logger.error(f"Error in AI campaign execution: {e}")
            campaign_result['error'] = str(e)
        
        return campaign_result
    
    def analyze_campaign_effectiveness(self, campaign_result):
        """Analyze the effectiveness of a completed campaign"""
        analysis = {
            'strategic_coherence': 0,
            'adaptation_quality': 0,
            'impact_efficiency': 0,
            'overall_rating': 0
        }
        
        try:
            # Strategic coherence - how well attacks followed the plan
            attacks = campaign_result.get('attacks', [])
            if attacks:
                successful_attacks = sum(1 for attack in attacks if attack.get('success', False))
                analysis['strategic_coherence'] = (successful_attacks / len(attacks)) * 100
            
            # Adaptation quality - how well AI adapted to grid responses
            ai_decisions = campaign_result.get('ai_decisions', [])
            if ai_decisions:
                analysis['adaptation_quality'] = min(100, len(ai_decisions) * 25)
            
            # Impact efficiency - impact per attack
            effectiveness_score = campaign_result.get('effectiveness_score', 0)
            if attacks:
                analysis['impact_efficiency'] = effectiveness_score / len(attacks)
            
            # Overall rating
            analysis['overall_rating'] = (
                analysis['strategic_coherence'] * 0.4 +
                analysis['adaptation_quality'] * 0.3 +
                analysis['impact_efficiency'] * 0.3
            )
            
        except Exception as e:
            logger.error(f"Error analyzing campaign effectiveness: {e}")
            analysis['error'] = str(e)
        
        return analysis
    
    def get_campaign_history(self):
        """Get historical campaign data"""
        return self.campaign_history.copy()
    
    def reset_campaign_history(self):
        """Reset campaign history"""
        self.campaign_history.clear()
        logger.info("Campaign history reset")
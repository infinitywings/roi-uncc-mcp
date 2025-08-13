#!/usr/bin/env python3
"""
AI-Assisted Grid Attack Scenario Demonstration
Executes predefined attack scenarios to show AI coordination capabilities
"""

import argparse
import json
import yaml
import sys
import os
import time
import requests
from datetime import datetime

def load_scenario_config(config_path):
    """Load attack scenario configuration"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def wait_for_mcp_server(base_url="http://localhost:5000", timeout=60):
    """Wait for MCP server to be ready"""
    print("Waiting for MCP server to be ready...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{base_url}/api/status", timeout=5)
            if response.status_code == 200:
                print("✓ MCP server is ready")
                return True
        except:
            pass
        time.sleep(2)
    
    print("✗ MCP server failed to start")
    return False

def execute_scenario(config, base_url="http://localhost:5000"):
    """Execute the attack scenario"""
    scenario = config['scenario']
    attack_config = config['attack']
    ai_config = config['ai']
    
    print(f"\n{'='*60}")
    print(f"Executing: {scenario['name']}")
    print(f"{'='*60}")
    print(f"\nDescription: {scenario['description']}")
    print(f"\nTarget Grid: {scenario['target_grid']}")
    print(f"Duration: {scenario['duration']} seconds")
    print(f"\n{'='*60}\n")
    
    # Configure AI model if specified
    if ai_config:
        print(f"AI Model: {ai_config['model']}")
        print(f"API Base: {ai_config['api_base']}\n")
    
    # Execute the attack campaign
    campaign_data = {
        "campaign": {
            "duration": scenario['duration'],
            "objective": attack_config.get('initial_prompt', config['attack_strategy']['objective']),
            "system_prompt": ai_config.get('system_prompt', ''),
            "phases": config['attack_strategy'].get('phases', [])
        },
        "ai_config": ai_config
    }
    
    print("Starting AI-coordinated attack campaign...")
    print("\nPhases:")
    for i, phase in enumerate(config['attack_strategy']['phases'], 1):
        print(f"  {i}. {phase['name']} ({phase['duration']}s)")
        print(f"     {phase['description']}")
    
    print(f"\n{'='*60}")
    print("ATTACK EXECUTION LOG")
    print(f"{'='*60}\n")
    
    try:
        # Start the attack campaign
        response = requests.post(
            f"{base_url}/api/ai/execute",
            json=campaign_data,
            timeout=scenario['duration'] + 30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Display attack sequence
            if 'attacks_executed' in result:
                print(f"\nTotal Attacks Executed: {len(result['attacks_executed'])}")
                print("\nAttack Sequence:")
                for i, attack in enumerate(result['attacks_executed'], 1):
                    print(f"\n  [{i}] {attack['technique'].upper()}")
                    print(f"      Time: {attack.get('timestamp', 'N/A')}")
                    if 'params' in attack:
                        print(f"      Parameters: {json.dumps(attack['params'], indent=8)}")
                    if 'impact' in attack:
                        impact = attack['impact']
                        print(f"      Impact Score: {impact.get('total_impact', 0):.2f}")
                    if 'ai_reasoning' in attack:
                        print(f"      AI Reasoning: {attack['ai_reasoning'][:100]}...")
            
            # Display metrics
            if 'metrics' in result:
                metrics = result['metrics']
                print(f"\n{'='*60}")
                print("CAMPAIGN METRICS")
                print(f"{'='*60}")
                print(f"Total Attacks: {metrics.get('total_attacks', 0)}")
                print(f"Successful Attacks: {metrics.get('successful_attacks', 0)}")
                print(f"Average Impact: {metrics.get('avg_impact', 0):.2f}")
                print(f"Max Impact: {metrics.get('max_impact', 0):.2f}")
                print(f"Campaign Duration: {metrics.get('duration', 0):.1f}s")
            
            # Save detailed results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = f"demo_results/scenario_{scenario['name'].replace(' ', '_')}_{timestamp}.json"
            
            with open(results_file, 'w') as f:
                json.dump({
                    'scenario': scenario,
                    'config': config,
                    'result': result,
                    'timestamp': timestamp
                }, f, indent=2)
            
            print(f"\n✓ Results saved to: {results_file}")
            
        else:
            print(f"✗ Attack campaign failed: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.Timeout:
        print("✗ Campaign execution timed out")
    except Exception as e:
        print(f"✗ Error during campaign execution: {e}")

def main():
    parser = argparse.ArgumentParser(description='Execute AI-assisted grid attack scenarios')
    parser.add_argument('--scenario', type=str, required=True,
                        help='Path to scenario configuration file')
    parser.add_argument('--server-url', type=str, default='http://localhost:5000',
                        help='MCP server URL')
    parser.add_argument('--wait-timeout', type=int, default=60,
                        help='Timeout for waiting for MCP server (seconds)')
    
    args = parser.parse_args()
    
    # Ensure results directory exists
    os.makedirs('demo_results', exist_ok=True)
    
    # Load scenario configuration
    try:
        config = load_scenario_config(args.scenario)
    except Exception as e:
        print(f"Error loading scenario config: {e}")
        sys.exit(1)
    
    # Wait for MCP server
    if not wait_for_mcp_server(args.server_url, args.wait_timeout):
        print("Failed to connect to MCP server. Is it running?")
        sys.exit(1)
    
    # Execute the scenario
    execute_scenario(config, args.server_url)
    
    print("\n✓ Scenario demonstration complete")

if __name__ == '__main__':
    main()
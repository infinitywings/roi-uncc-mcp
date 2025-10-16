#!/usr/bin/env python3
"""
Configuration Converter - Converts demo configs to MCP server format
Bridges the gap between demo launcher configs and MCP server expectations
"""

import yaml
import os
import logging

logger = logging.getLogger(__name__)

def convert_demo_config_to_mcp(demo_config):
    """Convert demo config format to MCP server format"""
    
    mcp_config = {
        'server': {
            'host': '0.0.0.0',
            'port': 5000,
            'debug': False
        },
        'helics': {
            'broker_address': 'tcp://helics-broker:23406',
            'federate_name': 'mcp_attacker',
            'time_delta': 1.0,
            'period': 1.0
        },
        'attacks': {
            'max_concurrent': 5,
            'timeout': 30.0,
            'validation': 'strict'
        },
        'monitoring': {
            'update_interval': 0.1,
            'history_size': 1000,
            'anomaly_detection': True
        },
        'ai': {
            'api_base': 'http://nginx-lb/v1',
            'api_key_file': '/app/API.txt',
            'model': 'Qwen/Qwen3-30B-A3B',
            'temperature': 0.8,
            'max_tokens': 2000
        }
    }
    
    # Map demo config sections to MCP config
    if 'server' in demo_config:
        mcp_config['server'].update(demo_config['server'])
    
    # Map grid.helics to helics
    if 'grid' in demo_config and 'helics' in demo_config['grid']:
        mcp_config['helics'].update(demo_config['grid']['helics'])
    
    # Map grid.monitoring to monitoring  
    if 'grid' in demo_config and 'monitoring' in demo_config['grid']:
        mcp_config['monitoring'].update(demo_config['grid']['monitoring'])
    
    # Map attack to attacks (with parameter name fixes)
    if 'attack' in demo_config:
        attack_config = demo_config['attack']
        
        # Map parameter names
        if 'max_concurrent' in attack_config:
            mcp_config['attacks']['max_concurrent'] = attack_config['max_concurrent']
        elif 'max_concurrent_attacks' in attack_config:
            mcp_config['attacks']['max_concurrent'] = attack_config['max_concurrent_attacks']
        
        if 'timeout' in attack_config:
            mcp_config['attacks']['timeout'] = attack_config['timeout']
        elif 'attack_timeout' in attack_config:
            mcp_config['attacks']['timeout'] = attack_config['attack_timeout']
        
        if 'validation' in attack_config:
            mcp_config['attacks']['validation'] = attack_config['validation']
        elif 'validation_mode' in attack_config:
            mcp_config['attacks']['validation'] = attack_config['validation_mode']
    
    # Map ai config
    if 'ai' in demo_config:
        mcp_config['ai'].update(demo_config['ai'])
    
    return mcp_config

def save_mcp_config(mcp_config, output_path):
    """Save MCP config to file"""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            yaml.dump(mcp_config, f, default_flow_style=False, indent=2)
        logger.info(f"Saved MCP config to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save MCP config: {e}")
        return False

def create_mcp_config_from_demo(demo_config_path, mcp_config_path=None):
    """Convert demo config file to MCP config file"""
    
    # Determine output path
    if mcp_config_path is None:
        base_dir = os.path.dirname(os.path.dirname(demo_config_path))
        mcp_config_path = os.path.join(base_dir, 'mcp-server', 'config', 'mcp.yaml')
    
    try:
        # Load demo config
        with open(demo_config_path, 'r') as f:
            demo_config = yaml.safe_load(f)
        
        # Convert to MCP format
        mcp_config = convert_demo_config_to_mcp(demo_config)
        
        # Save MCP config
        if save_mcp_config(mcp_config, mcp_config_path):
            print(f"✅ Created MCP config: {mcp_config_path}")
            return mcp_config_path
        else:
            print(f"❌ Failed to create MCP config")
            return None
            
    except Exception as e:
        logger.error(f"Error converting config: {e}")
        print(f"❌ Error converting config: {e}")
        return None

def validate_config_compatibility(demo_config_path):
    """Validate that demo config can be converted to MCP format"""
    issues = []
    
    try:
        with open(demo_config_path, 'r') as f:
            demo_config = yaml.safe_load(f)
        
        # Check required sections
        if 'ai' not in demo_config:
            issues.append("Missing 'ai' section")
        
        if 'grid' not in demo_config or 'helics' not in demo_config['grid']:
            issues.append("Missing 'grid.helics' section")
        
        # Check for deprecated parameter names
        if 'attack' in demo_config:
            attack_config = demo_config['attack']
            if 'validation_mode' in attack_config:
                issues.append("Use 'validation' instead of 'validation_mode' in attack config")
            if 'max_concurrent_attacks' in attack_config:
                issues.append("Use 'max_concurrent' instead of 'max_concurrent_attacks' in attack config")
        
        return issues
        
    except Exception as e:
        return [f"Error reading config file: {e}"]

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python config_converter.py <demo_config_path> [mcp_config_path]")
        sys.exit(1)
    
    demo_config_path = sys.argv[1]
    mcp_config_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Validate first
    issues = validate_config_compatibility(demo_config_path)
    if issues:
        print("⚠️  Configuration issues found:")
        for issue in issues:
            print(f"   - {issue}")
        print()
    
    # Convert
    result = create_mcp_config_from_demo(demo_config_path, mcp_config_path)
    if result:
        print(f"✅ Configuration conversion successful")
    else:
        print(f"❌ Configuration conversion failed")
        sys.exit(1)
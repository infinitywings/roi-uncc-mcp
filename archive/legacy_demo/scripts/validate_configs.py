#!/usr/bin/env python3
"""
Configuration Validator - Validates all configuration files for consistency
Tests configuration conversion and compatibility
"""

import os
import sys
import yaml
from pathlib import Path
import glob

# Import config converter
sys.path.insert(0, os.path.dirname(__file__))
from config_converter import validate_config_compatibility, create_mcp_config_from_demo

def validate_all_configs():
    """Validate all configuration files in the project"""
    
    project_root = os.path.dirname(os.path.dirname(__file__))
    config_dir = os.path.join(project_root, 'config')
    
    print("🔍 Validating ROI UNCC MCP Configuration Files")
    print("=" * 60)
    
    all_configs = []
    issues_found = False
    
    # Find all YAML config files
    for config_path in glob.glob(os.path.join(config_dir, '**/*.yaml'), recursive=True):
        all_configs.append(config_path)
    
    # Validate each config
    for config_path in sorted(all_configs):
        relative_path = os.path.relpath(config_path, project_root)
        print(f"\n📄 Validating: {relative_path}")
        
        try:
            # Load and parse YAML
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            if not config_data:
                print("   ⚠️  Empty configuration file")
                continue
            
            # Check basic structure
            basic_issues = check_basic_structure(config_data, relative_path)
            if basic_issues:
                issues_found = True
                for issue in basic_issues:
                    print(f"   ❌ {issue}")
            
            # Check compatibility with MCP server format
            compat_issues = validate_config_compatibility(config_path)
            if compat_issues:
                issues_found = True
                for issue in compat_issues:
                    print(f"   ⚠️  {issue}")
            
            # Test conversion to MCP format
            try:
                temp_mcp_path = f"/tmp/test_mcp_config_{os.path.basename(config_path)}"
                result = create_mcp_config_from_demo(config_path, temp_mcp_path)
                if result:
                    print("   ✅ MCP conversion: SUCCESS")
                    # Clean up
                    if os.path.exists(temp_mcp_path):
                        os.remove(temp_mcp_path)
                else:
                    print("   ❌ MCP conversion: FAILED")
                    issues_found = True
            except Exception as e:
                print(f"   ❌ MCP conversion error: {e}")
                issues_found = True
            
            if not basic_issues and not compat_issues:
                print("   ✅ Configuration valid")
        
        except yaml.YAMLError as e:
            print(f"   ❌ YAML syntax error: {e}")
            issues_found = True
        except Exception as e:
            print(f"   ❌ Error reading file: {e}")
            issues_found = True
    
    # Summary
    print("\n" + "=" * 60)
    if issues_found:
        print("❌ Configuration validation completed with issues")
        print("   Please fix the issues above before running demos")
        return False
    else:
        print("✅ All configurations validated successfully")
        print("   All configs are compatible with MCP server")
        return True

def check_basic_structure(config_data, file_path):
    """Check basic configuration structure"""
    issues = []
    
    # Check for required sections in demo configs
    if 'examples/' in file_path or 'demo_config.yaml' in file_path:
        required_sections = ['demo', 'ai']
        for section in required_sections:
            if section not in config_data:
                issues.append(f"Missing required section: {section}")
        
        # Check demo section
        if 'demo' in config_data:
            demo_config = config_data['demo']
            if 'mode' not in demo_config:
                issues.append("Missing 'mode' in demo section")
            elif demo_config['mode'] not in ['ai', 'random', 'comparison']:
                issues.append(f"Invalid mode: {demo_config['mode']}")
        
        # Check AI section
        if 'ai' in config_data:
            ai_config = config_data['ai']
            if 'model' not in ai_config:
                issues.append("Missing 'model' in ai section")
            if 'api_base' not in ai_config:
                issues.append("Missing 'api_base' in ai section")
        
        # Check attack section parameter names
        if 'attack' in config_data:
            attack_config = config_data['attack']
            deprecated_params = {
                'max_concurrent_attacks': 'max_concurrent',
                'attack_timeout': 'timeout',
                'validation_mode': 'validation'
            }
            for old_param, new_param in deprecated_params.items():
                if old_param in attack_config:
                    issues.append(f"Deprecated parameter '{old_param}', use '{new_param}' instead")
    
    # Check MCP server config structure
    elif 'mcp-server/config/' in file_path:
        required_sections = ['helics', 'ai']
        for section in required_sections:
            if section not in config_data:
                issues.append(f"Missing required section: {section}")
    
    return issues

def test_config_examples():
    """Test that all example configs work properly"""
    print("\n🧪 Testing Configuration Examples")
    print("-" * 40)
    
    project_root = os.path.dirname(os.path.dirname(__file__))
    examples_dir = os.path.join(project_root, 'config', 'examples')
    
    test_results = {}
    
    for config_file in os.listdir(examples_dir):
        if config_file.endswith('.yaml'):
            config_path = os.path.join(examples_dir, config_file)
            print(f"\n🔬 Testing: {config_file}")
            
            try:
                with open(config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
                
                # Check AI provider setup
                ai_config = config_data.get('ai', {})
                api_base = ai_config.get('api_base', '')
                
                if 'openai.com' in api_base:
                    print("   📡 OpenAI configuration detected")
                    api_key = ai_config.get('api_key', '')
                    if not api_key or 'your-' in api_key:
                        print("   ⚠️  Placeholder API key - replace with real key")
                    else:
                        print("   ✅ API key configured")
                
                elif 'anthropic.com' in api_base:
                    print("   🤖 Anthropic configuration detected")
                    api_key = ai_config.get('api_key', '')
                    if not api_key or 'your-' in api_key:
                        print("   ⚠️  Placeholder API key - replace with real key")
                    else:
                        print("   ✅ API key configured")
                
                elif 'localhost' in api_base or 'nginx-lb' in api_base:
                    print("   🏠 Local model configuration detected")
                    print("   ✅ No API key required")
                
                # Check model parameters
                model = ai_config.get('model', '')
                temperature = ai_config.get('temperature', 0.8)
                max_tokens = ai_config.get('max_tokens', 2000)
                
                print(f"   Model: {model}")
                print(f"   Temperature: {temperature}")
                print(f"   Max tokens: {max_tokens}")
                
                test_results[config_file] = True
                
            except Exception as e:
                print(f"   ❌ Error testing config: {e}")
                test_results[config_file] = False
    
    # Summary
    print(f"\n📊 Test Results:")
    for config_file, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {config_file:<25} {status}")
    
    return all(test_results.values())

def check_docker_compose_files():
    """Check Docker Compose file references"""
    print("\n🐳 Checking Docker Compose References")
    print("-" * 40)
    
    project_root = os.path.dirname(os.path.dirname(__file__))
    docker_dir = os.path.join(project_root, 'docker')
    
    # Look for referenced compose files
    compose_files = []
    for config_path in glob.glob(os.path.join(project_root, 'config', '**/*.yaml'), recursive=True):
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            if 'docker' in config_data and 'compose_file' in config_data['docker']:
                compose_file = config_data['docker']['compose_file']
                compose_files.append((config_path, compose_file))
        except:
            continue
    
    issues_found = False
    for config_path, compose_file in compose_files:
        rel_config = os.path.relpath(config_path, project_root)
        print(f"\n📄 {rel_config}")
        print(f"   References: {compose_file}")
        
        # Check if file exists
        full_compose_path = os.path.join(project_root, compose_file)
        if os.path.exists(full_compose_path):
            print("   ✅ Compose file exists")
        else:
            print("   ❌ Compose file not found")
            issues_found = True
    
    return not issues_found

if __name__ == '__main__':
    print("ROI UNCC MCP Configuration Validation Suite")
    print("=" * 60)
    
    # Run all validation tests
    config_valid = validate_all_configs()
    examples_valid = test_config_examples()
    docker_valid = check_docker_compose_files()
    
    print("\n" + "=" * 60)
    print("FINAL VALIDATION RESULTS:")
    print(f"Configuration Files: {'✅ PASS' if config_valid else '❌ FAIL'}")
    print(f"Example Configs:     {'✅ PASS' if examples_valid else '❌ FAIL'}")
    print(f"Docker References:   {'✅ PASS' if docker_valid else '❌ FAIL'}")
    
    if config_valid and examples_valid and docker_valid:
        print("\n🎉 All validations passed! Configuration is ready for use.")
        sys.exit(0)
    else:
        print("\n⚠️  Some validations failed. Please fix issues before running demos.")
        sys.exit(1)
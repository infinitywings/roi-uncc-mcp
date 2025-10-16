#!/usr/bin/env python3
"""
Setup Verification Script
Tests all components for consistency and functionality
"""

import os
import sys
import subprocess
import json
import yaml
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description}: {filepath} (NOT FOUND)")
        return False

def check_docker_file_paths():
    """Check Docker file paths and configurations"""
    print("\n🐳 Checking Docker configurations...")
    
    # Check Dockerfile paths
    dockerfile_path = "docker/Dockerfile.mcp"
    compose_demo_path = "docker/docker-compose.demo.yml"
    compose_path = "docker/docker-compose.yml"
    
    success = True
    success &= check_file_exists(dockerfile_path, "MCP Dockerfile")
    success &= check_file_exists(compose_demo_path, "Demo Compose file")
    success &= check_file_exists(compose_path, "Basic Compose file")
    
    # Check if compose files have correct path references
    try:
        with open(compose_demo_path, 'r') as f:
            compose_content = f.read()
            if "context: .." in compose_content:
                print("✅ Docker compose context correctly set to parent directory")
            else:
                print("❌ Docker compose context may be incorrect")
                success = False
    except Exception as e:
        print(f"❌ Error reading compose file: {e}")
        success = False
    
    return success

def check_python_imports():
    """Check Python script imports and paths"""
    print("\n🐍 Checking Python imports...")
    
    success = True
    
    # Test key imports
    try:
        import yaml
        print("✅ PyYAML available")
    except ImportError:
        print("❌ PyYAML not available")
        success = False
    
    try:
        import flask
        print("✅ Flask available")
    except ImportError:
        print("❌ Flask not available")
        success = False
    
    # Check demo.py wrapper
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        import demo
        print("✅ Demo wrapper imports correctly")
    except ImportError as e:
        print(f"❌ Demo wrapper import failed: {e}")
        success = False
    
    return success

def check_config_consistency():
    """Check configuration file consistency"""
    print("\n⚙️  Checking configuration consistency...")
    
    success = True
    config_file = "config/demo_config.yaml"
    
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check Docker compose file path
        compose_file = config.get('docker', {}).get('compose_file', '')
        if compose_file == "docker/docker-compose.demo.yml":
            print("✅ Compose file path correct in config")
        else:
            print(f"❌ Compose file path in config: {compose_file}")
            success = False
        
        # Check HELICS broker address
        broker_addr = config.get('grid', {}).get('helics', {}).get('broker_address', '')
        if "23406" in broker_addr:
            print("✅ HELICS broker port consistent (23406)")
        else:
            print(f"❌ HELICS broker port may be incorrect: {broker_addr}")
            success = False
            
    except Exception as e:
        print(f"❌ Error reading config: {e}")
        success = False
    
    return success

def check_api_endpoints():
    """Check API endpoint documentation consistency"""
    print("\n🌐 Checking API endpoint consistency...")
    
    success = True
    
    # Check if server.py has the documented endpoints
    server_file = "mcp-server/src/server.py"
    try:
        with open(server_file, 'r') as f:
            server_content = f.read()
        
        endpoints = [
            "/api/status",
            "/api/attack",
            "/api/ai/execute",
            "/api/reconnaissance",
            "/api/random/execute",
            "/api/comparison"
        ]
        
        for endpoint in endpoints:
            if endpoint in server_content:
                print(f"✅ Endpoint {endpoint} found in server")
            else:
                print(f"❌ Endpoint {endpoint} NOT found in server")
                success = False
                
    except Exception as e:
        print(f"❌ Error checking server endpoints: {e}")
        success = False
    
    return success

def check_directory_structure():
    """Check if directory structure is correct"""
    print("\n📁 Checking directory structure...")
    
    success = True
    expected_dirs = [
        "scripts",
        "docker", 
        "config",
        "mcp-server",
        "examples",
        "documentation",
        "containers"
    ]
    
    for dir_name in expected_dirs:
        if os.path.isdir(dir_name):
            print(f"✅ Directory exists: {dir_name}/")
        else:
            print(f"❌ Directory missing: {dir_name}/")
            success = False
    
    # Check if old files were moved
    old_files = [
        "demo_docker.py",
        "demo_launcher.py", 
        "Dockerfile.mcp",
        "docker-compose.demo.yml"
    ]
    
    for old_file in old_files:
        if os.path.exists(old_file):
            print(f"❌ Old file still in root: {old_file}")
            success = False
    
    if success:
        print("✅ Directory structure is clean")
    
    return success

def main():
    """Run all verification checks"""
    print("🔍 ROI UNCC MCP Project Setup Verification")
    print("=" * 50)
    
    # Change to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    print(f"Working directory: {os.getcwd()}")
    
    checks = [
        check_directory_structure,
        check_docker_file_paths,
        check_python_imports,
        check_config_consistency,
        check_api_endpoints
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"❌ Check failed with error: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    if all(results):
        print("🎉 All checks passed! The project setup is consistent.")
        return 0
    else:
        failed_count = len([r for r in results if not r])
        print(f"⚠️  {failed_count} check(s) failed. Please review and fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
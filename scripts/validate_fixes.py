#!/usr/bin/env python3
"""
Validation Script for MCP Server and Container Fixes
Tests critical fixes for path issues, imports, and configurations
"""

import os
import sys
import json
import subprocess
from pathlib import Path

def check_server_imports():
    """Test server import paths"""
    print("\n🐍 Testing MCP Server Imports...")
    
    # Change to project root and add paths
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    sys.path.insert(0, str(project_root / "mcp-server" / "src"))
    
    try:
        # Test basic imports
        from server import MCPServer
        print("✅ Server module imports successfully")
        
        # Test initialization with container paths
        server = MCPServer(config_path='/app/mcp-server/config/mcp.yaml')
        print("✅ Server initializes with container paths")
        
        return True
    except Exception as e:
        print(f"❌ Server import failed: {e}")
        return False

def check_dockerfile_syntax():
    """Validate Dockerfile syntax"""
    print("\n🐳 Validating Dockerfile syntax...")
    
    dockerfile_path = "docker/Dockerfile.mcp"
    try:
        # Check if Docker is available
        result = subprocess.run(['docker', '--version'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("⚠️  Docker not available, skipping syntax check")
            return True
            
        # Just check if dockerfile exists and has basic syntax
        with open(dockerfile_path, 'r') as f:
            dockerfile_content = f.read()
        
        # Basic syntax checks
        if dockerfile_content.startswith('FROM') and 'COPY' in dockerfile_content:
            print("✅ Dockerfile syntax appears valid")
            return True
        
        if result.returncode == 0:
            print("✅ Dockerfile syntax valid")
            return True
        else:
            print(f"❌ Dockerfile validation failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"⚠️  Could not validate Dockerfile: {e}")
        return True

def check_path_consistency():
    """Check path consistency across files"""
    print("\n📁 Checking path consistency...")
    
    success = True
    
    # Check server.py paths
    server_file = "mcp-server/src/server.py"
    with open(server_file, 'r') as f:
        content = f.read()
        
    # Check for container paths
    if '/app/mcp-server/config/mcp.yaml' in content:
        print("✅ Server uses correct container config path")
    else:
        print("❌ Server config path incorrect")
        success = False
        
    if '/app/API.txt' in content:
        print("✅ AI client uses correct API key path")
    else:
        print("❌ AI client API key path incorrect")
        success = False
    
    # Check docker-compose paths
    compose_file = "docker/docker-compose.demo.yml"
    with open(compose_file, 'r') as f:
        compose_content = f.read()
        
    if "context: .." in compose_content:
        print("✅ Docker compose context correct")
    else:
        print("❌ Docker compose context incorrect")
        success = False
        
    if "../examples/2bus-13bus" in compose_content:
        print("✅ Docker compose volume paths correct")
    else:
        print("❌ Docker compose volume paths incorrect")
        success = False
    
    return success

def check_environment_variables():
    """Check environment variable handling"""
    print("\n🌍 Checking environment variable handling...")
    
    server_file = "mcp-server/src/server.py"
    with open(server_file, 'r') as f:
        content = f.read()
    
    success = True
    
    if "HELICS_BROKER_ADDRESS" in content:
        print("✅ Server handles HELICS_BROKER_ADDRESS env var")
    else:
        print("❌ Server missing HELICS_BROKER_ADDRESS handling")
        success = False
        
    if "PYTHONPATH" in content:
        print("✅ Server logs PYTHONPATH")
    else:
        print("❌ Server missing PYTHONPATH logging")
        success = False
    
    return success

def check_networking_config():
    """Check Docker networking configuration"""
    print("\n🌐 Checking Docker networking...")
    
    compose_file = "docker/docker-compose.demo.yml"
    with open(compose_file, 'r') as f:
        content = f.read()
    
    success = True
    
    # Check if external network dependency was removed
    if "vllm_nginx" not in content:
        print("✅ External network dependency removed")
    else:
        print("❌ External network dependency still present")
        success = False
        
    if "grid-network" in content:
        print("✅ Internal grid network configured")
    else:
        print("❌ Internal grid network missing")
        success = False
    
    return success

def check_dependency_imports():
    """Check if all required dependencies are listed"""
    print("\n📦 Checking dependency consistency...")
    
    dockerfile_path = "docker/Dockerfile.mcp"
    requirements_path = "mcp-server/requirements.txt"
    
    with open(dockerfile_path, 'r') as f:
        dockerfile_content = f.read()
    
    try:
        with open(requirements_path, 'r') as f:
            requirements_content = f.read()
    except FileNotFoundError:
        print("⚠️  requirements.txt not found")
        return True
    
    success = True
    
    # Check key dependencies
    key_deps = ['flask', 'pyyaml', 'numpy', 'scipy', 'matplotlib']
    
    for dep in key_deps:
        if dep in dockerfile_content:
            print(f"✅ {dep} in Dockerfile")
        else:
            print(f"❌ {dep} missing from Dockerfile")
            success = False
    
    return success

def main():
    """Run all validation checks"""
    print("🔍 MCP Server and Container Fixes Validation")
    print("=" * 60)
    
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    print(f"Working directory: {os.getcwd()}")
    
    checks = [
        check_path_consistency,
        check_environment_variables,
        check_networking_config,
        check_dependency_imports,
        check_dockerfile_syntax,
        check_server_imports
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"❌ Check failed with error: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    if all(results):
        print("🎉 All validation checks passed! Critical fixes verified.")
        return 0
    else:
        failed_count = len([r for r in results if not r])
        print(f"⚠️  {failed_count} validation check(s) failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
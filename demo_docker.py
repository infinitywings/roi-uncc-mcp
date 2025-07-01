#!/usr/bin/env python3
"""
Containerized Demo Launcher - AI-assisted penetration testing using Docker
Uses existing ROI UNCC container infrastructure
"""

import os
import sys
import time
import json
import argparse
import subprocess
import requests
from datetime import datetime
import signal
import yaml

class ContainerizedDemo:
    """Containerized demo launcher using Docker Compose"""
    
    def __init__(self, config_file=None):
        self.demo_dir = os.path.dirname(os.path.abspath(__file__))
        self.results_dir = os.path.join(self.demo_dir, 'demo_results')
        
        # Load configuration
        self.config = self._load_config(config_file)
        self.compose_file = self.config.get('docker', {}).get('compose_file', 'docker-compose.demo.yml')
        
        # Create results directory
        results_dir = self.config.get('results', {}).get('directory', 'demo_results')
        self.results_dir = os.path.join(self.demo_dir, results_dir)
        os.makedirs(self.results_dir, exist_ok=True)
        
        print("Containerized AI-Assisted Grid Penetration Testing Demo")
        print("Using existing ROI UNCC Docker infrastructure")
        if config_file:
            print(f"Configuration: {config_file}")
        print("=" * 60)
    
    def setup_signal_handlers(self):
        """Setup signal handlers for clean shutdown"""
        def signal_handler(signum, frame):
            print("\nReceived interrupt signal. Cleaning up containers...")
            self.cleanup()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _load_config(self, config_file=None):
        """Load configuration from YAML file"""
        # Default configuration
        default_config = {
            'demo': {
                'mode': 'comparison',
                'duration': 60,
                'trials': 3,
                'grid_model': '2bus-13bus'
            },
            'ai': {
                'model': 'Qwen/Qwen3-30B-A3B',
                'api_base': 'http://nginx-lb/v1',
                'api_key': '',
                'temperature': 0.8,
                'max_tokens': 4000,
                'timeout': 60
            },
            'docker': {
                'compose_file': 'docker-compose.demo.yml',
                'startup_timeout': 120,
                'cleanup_on_exit': True
            },
            'results': {
                'directory': 'demo_results'
            }
        }
        
        # Determine config file path
        if config_file is None:
            config_file = os.path.join(self.demo_dir, 'config', 'demo_config.yaml')
        elif not os.path.isabs(config_file):
            config_file = os.path.join(self.demo_dir, config_file)
        
        # Load from file if exists
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    file_config = yaml.safe_load(f)
                
                # Deep merge configurations
                def merge_dict(base, update):
                    for key, value in update.items():
                        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                            merge_dict(base[key], value)
                        else:
                            base[key] = value
                
                merge_dict(default_config, file_config)
                print(f"✅ Loaded configuration from {config_file}")
                
            except Exception as e:
                print(f"⚠️  Warning: Could not load config file {config_file}: {e}")
                print("   Using default configuration")
        else:
            print(f"ℹ️  Configuration file {config_file} not found, using defaults")
        
        # Add derived values
        default_config['mcp_server_url'] = 'http://localhost:5000'
        default_config['simulation_duration'] = default_config['demo']['duration']
        default_config['comparison_trials'] = default_config['demo']['trials']
        default_config['startup_timeout'] = default_config['docker']['startup_timeout']
        
        return default_config
    
    def check_prerequisites(self):
        """Check if Docker and docker-compose are available"""
        print("Checking prerequisites...")
        
        # Check Docker
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                print("❌ Docker is not available")
                return False
            print(f"✅ {result.stdout.strip()}")
        except FileNotFoundError:
            print("❌ Docker is not installed")
            return False
        
        # Check docker compose (v2)
        try:
            result = subprocess.run(['docker', 'compose', 'version'], capture_output=True, text=True)
            if result.returncode != 0:
                print("❌ docker compose is not available")
                return False
            print(f"✅ {result.stdout.strip()}")
        except FileNotFoundError:
            print("❌ docker compose is not installed")
            return False
        
        # Check for base container image
        result = subprocess.run(['docker', 'images', '-q', 'roi-uncc-img:latest'], 
                              capture_output=True, text=True)
        if not result.stdout.strip():
            print("❌ Base container 'roi-uncc-img:latest' not found")
            print("   Please build the base container first:")
            print("   cd containers/docker && docker build -t roi-uncc-img:latest .")
            return False
        print("✅ Base container roi-uncc-img:latest found")
        
        # Check API key (optional for local models)
        api_key_file = os.path.join(self.demo_dir, 'API.txt')
        if not os.path.exists(api_key_file):
            # Check if using local model or API key provided
            if not self.config.get('ai_api_key') and not self.config.get('ai_base_url', '').startswith(('http://localhost', 'http://nginx-lb', 'http://host.docker.internal')):
                print("⚠️  Warning: API.txt file not found")
                print("   If using external AI API, provide --ai-api-key or create API.txt")
                # Create empty API.txt to avoid build issues
                with open(api_key_file, 'w') as f:
                    f.write('local-llm-key')
        else:
            print("✅ API key file found")
        
        return True
    
    def build_mcp_container(self):
        """Build the MCP server container"""
        print("\n🔨 Building MCP server container...")
        
        cmd = ['docker', 'build', '-f', 'Dockerfile.mcp', '-t', 'roi-uncc-mcp:latest', '.']
        process = subprocess.run(cmd, cwd=self.demo_dir)
        
        if process.returncode != 0:
            print("❌ Failed to build MCP container")
            return False
        
        print("✅ MCP container built successfully")
        return True
    
    def start_services(self):
        """Start all Docker services"""
        print("\n🚀 Starting containerized services...")
        
        # Clean up any existing containers first
        print("   Cleaning up any existing containers...")
        cleanup_cmd = ['docker', 'compose', '-f', self.compose_file, 'down', '-v']
        subprocess.run(cleanup_cmd, cwd=self.demo_dir, capture_output=True)
        
        # Update HELICS broker address in MCP config
        self._update_mcp_config()
        
        cmd = ['docker', 'compose', '-f', self.compose_file, 'up', '-d']
        process = subprocess.run(cmd, cwd=self.demo_dir)
        
        if process.returncode != 0:
            print("❌ Failed to start services")
            return False
        
        print("✅ Services started")
        return True
    
    def _update_mcp_config(self):
        """Update MCP configuration for Docker network and AI settings"""
        config_file = os.path.join(self.demo_dir, 'mcp-server', 'config', 'mcp.yaml')
        
        try:
            with open(config_file, 'r') as f:
                mcp_config = yaml.safe_load(f)
            
            # Update HELICS configuration
            if 'grid' in self.config and 'helics' in self.config['grid']:
                helics_config = self.config['grid']['helics']
                if 'helics' not in mcp_config:
                    mcp_config['helics'] = {}
                mcp_config['helics']['broker_address'] = helics_config.get('broker_address', 'tcp://helics-broker:23406')
                mcp_config['helics']['federate_name'] = helics_config.get('federate_name', 'mcp_attacker')
                mcp_config['helics']['time_delta'] = helics_config.get('time_delta', 1.0)
                mcp_config['helics']['period'] = helics_config.get('period', 1.0)
            else:
                # Default HELICS config for Docker
                if 'helics' not in mcp_config:
                    mcp_config['helics'] = {}
                mcp_config['helics']['broker_address'] = 'tcp://helics-broker:23406'
            
            # Update AI configuration
            if 'ai' in self.config:
                ai_config = self.config['ai']
                if 'ai' not in mcp_config:
                    mcp_config['ai'] = {}
                
                mcp_config['ai']['model'] = ai_config.get('model', 'Qwen/Qwen3-30B-A3B')
                mcp_config['ai']['api_base'] = ai_config.get('api_base', 'http://nginx-lb/v1')
                mcp_config['ai']['temperature'] = ai_config.get('temperature', 0.8)
                mcp_config['ai']['max_tokens'] = ai_config.get('max_tokens', 4000)
                
                print(f"   Using AI model: {mcp_config['ai']['model']}")
                print(f"   Using AI base URL: {mcp_config['ai']['api_base']}")
                
                # Handle API key
                api_key = ai_config.get('api_key', '')
                if api_key:
                    # Write API key to file
                    api_key_file = os.path.join(self.demo_dir, 'API.txt')
                    with open(api_key_file, 'w') as f:
                        f.write(api_key)
                    print("   Using provided API key")
                elif ai_config.get('api_key_file'):
                    api_key_file = ai_config['api_key_file']
                    if not os.path.isabs(api_key_file):
                        api_key_file = os.path.join(self.demo_dir, api_key_file)
                    if os.path.exists(api_key_file):
                        print(f"   Using API key from {api_key_file}")
            
            with open(config_file, 'w') as f:
                yaml.dump(mcp_config, f, default_flow_style=False)
            
            print("✅ Updated MCP configuration")
        except Exception as e:
            print(f"⚠️  Warning: Could not update MCP config: {e}")
    
    def wait_for_services(self):
        """Wait for all services to be ready"""
        print(f"\n⏳ Waiting for services to initialize (timeout: {self.config['startup_timeout']}s)...")
        
        start_time = time.time()
        
        # Wait for MCP server
        mcp_ready = False
        while (time.time() - start_time) < self.config['startup_timeout']:
            try:
                response = requests.get(f"{self.config['mcp_server_url']}/api/status", timeout=2)
                if response.status_code == 200:
                    status = response.json()
                    if status.get('server', {}).get('federation_active', False):
                        mcp_ready = True
                        break
            except:
                pass
            
            time.sleep(2)
            print(".", end="", flush=True)
        
        print()
        
        if mcp_ready:
            print("✅ All services are ready!")
            return True
        else:
            print("❌ Services did not start within timeout")
            self._show_service_logs()
            return False
    
    def _show_service_logs(self):
        """Show service logs for debugging"""
        print("\n📋 Service logs for debugging:")
        
        services = ['helics-broker', 'gridpack-federate', 'gridlabd-federate', 'mcp-server']
        for service in services:
            print(f"\n--- {service} logs ---")
            cmd = ['docker', 'compose', '-f', self.compose_file, 'logs', '--tail=10', service]
            subprocess.run(cmd, cwd=self.demo_dir)
    
    def run_ai_demo(self):
        """Run AI-assisted attack demo"""
        print("\n🤖 Running AI-assisted attack demo...")
        
        try:
            attack_config = self.config.get('attack', {})
            demo_config = self.config.get('demo', {})
            
            campaign_data = {
                'campaign': {
                    'duration': demo_config.get('duration', 60),
                    'objective': attack_config.get('prompt', 'Demonstrate AI-driven strategic attack progression'),
                    'grid_model': demo_config.get('grid_model', '2bus-13bus')
                }
            }
            
            response = requests.post(
                f"{self.config['mcp_server_url']}/api/ai/execute",
                json=campaign_data,
                timeout=self.config['simulation_duration'] + 30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Save results
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                result_file = os.path.join(self.results_dir, f'ai_campaign_{timestamp}.json')
                with open(result_file, 'w') as f:
                    json.dump(result, f, indent=2)
                
                print(f"✅ AI campaign completed!")
                print(f"   Attacks executed: {result.get('attack_count', 0)}")
                print(f"   Effectiveness score: {result.get('effectiveness_score', 0):.2f}")
                print(f"   Results saved to: {result_file}")
                
                return result
            else:
                print(f"❌ AI campaign failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error in AI demo: {e}")
            return None
    
    def run_random_demo(self):
        """Run random attack demo"""
        print("\n🎲 Running random attack demo...")
        
        try:
            campaign_data = {
                'campaign': {
                    'duration': self.config['simulation_duration'],
                    'grid_model': self.config.get('grid_model', '2bus-13bus')
                }
            }
            
            response = requests.post(
                f"{self.config['mcp_server_url']}/api/random/execute",
                json=campaign_data,
                timeout=self.config['simulation_duration'] + 30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Save results
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                result_file = os.path.join(self.results_dir, f'random_campaign_{timestamp}.json')
                with open(result_file, 'w') as f:
                    json.dump(result, f, indent=2)
                
                print(f"✅ Random campaign completed!")
                print(f"   Attacks executed: {result.get('attack_count', 0)}")
                print(f"   Effectiveness score: {result.get('effectiveness_score', 0):.2f}")
                print(f"   Results saved to: {result_file}")
                
                return result
            else:
                print(f"❌ Random campaign failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error in random demo: {e}")
            return None
    
    def run_comparison_demo(self):
        """Run comparison between AI and random attacks"""
        print(f"\n📊 Running AI vs Random comparison ({self.config['comparison_trials']} trials each)...")
        
        try:
            campaign_data = {
                'campaign': {
                    'duration': self.config['simulation_duration'],
                    'trials': self.config['comparison_trials'],
                    'grid_model': self.config.get('grid_model', '2bus-13bus'),
                    'ai_objective': self.config.get('attack_prompt', 'Demonstrate AI-driven strategic attack progression')
                }
            }
            
            timeout = (self.config['simulation_duration'] * self.config['comparison_trials'] * 2) + 60
            response = requests.post(
                f"{self.config['mcp_server_url']}/api/comparison",
                json=campaign_data,
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Save results
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                result_file = os.path.join(self.results_dir, f'comparison_{timestamp}.json')
                with open(result_file, 'w') as f:
                    json.dump(result, f, indent=2)
                
                print(f"✅ Comparison study completed!")
                
                # Display summary
                metrics = result.get('comparison_metrics', {})
                print(f"\n📈 Results Summary:")
                print(f"   AI mean effectiveness: {metrics.get('ai_mean', 0):.2f}")
                print(f"   Random mean effectiveness: {metrics.get('random_mean', 0):.2f}")
                print(f"   AI improvement ratio: {metrics.get('improvement_ratio', 0):.2f}x")
                print(f"   AI success rate: {metrics.get('ai_success_rate', 0):.2f}")
                print(f"   Random success rate: {metrics.get('random_success_rate', 0):.2f}")
                print(f"   Results saved to: {result_file}")
                
                return result
            else:
                print(f"❌ Comparison failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error in comparison demo: {e}")
            return None
    
    def cleanup(self):
        """Clean up Docker services"""
        print("\n🧹 Cleaning up Docker services...")
        
        cmd = ['docker', 'compose', '-f', self.compose_file, 'down', '-v']
        subprocess.run(cmd, cwd=self.demo_dir)
        
        print("✅ Cleanup completed")
    
    def run_demo(self, mode='comparison'):
        """Run the complete containerized demo"""
        try:
            # Setup
            self.setup_signal_handlers()
            
            if not self.check_prerequisites():
                return False
            
            if not self.build_mcp_container():
                return False
            
            if not self.start_services():
                return False
            
            if not self.wait_for_services():
                return False
            
            # Run demo based on mode
            if mode == 'ai':
                result = self.run_ai_demo()
            elif mode == 'random':
                result = self.run_random_demo()
            elif mode == 'comparison':
                result = self.run_comparison_demo()
            else:
                print(f"❌ Unknown mode: {mode}")
                return False
            
            if result:
                print(f"\n🎉 Demo completed successfully!")
                print(f"📁 Results available in: {self.results_dir}")
                return True
            else:
                print(f"\n❌ Demo failed!")
                return False
                
        except Exception as e:
            print(f"❌ Demo error: {e}")
            return False
        finally:
            self.cleanup()

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Containerized AI-Assisted Grid Penetration Testing Demo')
    parser.add_argument('--config', default=None,
                      help='Configuration file path (default: config/demo_config.yaml)')
    parser.add_argument('--mode', choices=['ai', 'random', 'comparison'], default=None,
                      help='Demo mode: ai (AI attacks only), random (random attacks only), comparison (both)')
    parser.add_argument('--duration', type=int, default=None,
                      help='Attack campaign duration in seconds')
    parser.add_argument('--trials', type=int, default=None,
                      help='Number of trials for comparison mode')
    parser.add_argument('--grid-model', default=None,
                      choices=['2bus-13bus', 'IEEE-39bus', 'IEEE-118bus'],
                      help='Grid simulation model to use')
    parser.add_argument('--attack-prompt', default=None,
                      help='Custom attack prompt for AI strategy')
    parser.add_argument('--ai-model', default=None,
                      help='AI model name (e.g., gpt-4, llama-3-70b, Qwen/Qwen3-30B-A3B)')
    parser.add_argument('--ai-base-url', default=None,
                      help='AI API base URL (e.g., http://nginx-lb/v1, https://api.openai.com/v1)')
    parser.add_argument('--ai-api-key', default=None,
                      help='AI API key (optional, uses API.txt if not provided)')
    
    args = parser.parse_args()
    
    # Create launcher with config file
    launcher = ContainerizedDemo(config_file=args.config)
    
    # Override config with command line arguments
    if args.mode is not None:
        launcher.config['demo']['mode'] = args.mode
    if args.duration is not None:
        launcher.config['demo']['duration'] = args.duration
        launcher.config['simulation_duration'] = args.duration
    if args.trials is not None:
        launcher.config['demo']['trials'] = args.trials
        launcher.config['comparison_trials'] = args.trials
    if args.grid_model is not None:
        launcher.config['demo']['grid_model'] = args.grid_model
    if args.attack_prompt is not None:
        if 'attack' not in launcher.config:
            launcher.config['attack'] = {}
        launcher.config['attack']['prompt'] = args.attack_prompt
    if args.ai_model is not None:
        launcher.config['ai']['model'] = args.ai_model
    if args.ai_base_url is not None:
        launcher.config['ai']['api_base'] = args.ai_base_url
    if args.ai_api_key is not None:
        launcher.config['ai']['api_key'] = args.ai_api_key
    
    # Get mode from config
    mode = launcher.config['demo'].get('mode', 'comparison')
    
    # Run demo
    success = launcher.run_demo(mode)
    
    if success:
        print("\n🎉 Containerized demo completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Containerized demo failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()
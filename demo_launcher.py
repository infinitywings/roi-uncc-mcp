#!/usr/bin/env python3
"""
Demo Launcher - End-to-end AI-assisted penetration testing demo
Launches 2bus-13bus simulation with MCP server for AI vs Random attack comparison
"""

import os
import sys
import time
import json
import argparse
import subprocess
import threading
import requests
from datetime import datetime
import signal

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mcp-server', 'src'))

def run_command(cmd, cwd=None, output_file=None):
    """Run a command and optionally capture output"""
    print(f"Running: {cmd}")
    if cwd:
        print(f"Working directory: {cwd}")
    
    try:
        if output_file:
            with open(output_file, 'w') as f:
                process = subprocess.Popen(
                    cmd, shell=True, cwd=cwd,
                    stdout=f, stderr=subprocess.STDOUT,
                    preexec_fn=os.setsid
                )
        else:
            process = subprocess.Popen(
                cmd, shell=True, cwd=cwd,
                preexec_fn=os.setsid
            )
        return process
    except Exception as e:
        print(f"Error running command: {e}")
        return None

class DemoLauncher:
    """Main demo launcher class"""
    
    def __init__(self):
        self.processes = []
        self.demo_dir = os.path.dirname(os.path.abspath(__file__))
        self.example_dir = os.path.join(self.demo_dir, 'examples', '2bus-13bus')
        self.mcp_dir = os.path.join(self.demo_dir, 'mcp-server')
        self.results_dir = os.path.join(self.demo_dir, 'demo_results')
        
        # Create results directory
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Demo configuration
        self.config = {
            'helics_broker_port': 23404,
            'mcp_server_port': 5000,
            'simulation_duration': 60,  # seconds
            'comparison_trials': 3
        }
    
    def setup_signal_handlers(self):
        """Setup signal handlers for clean shutdown"""
        def signal_handler(signum, frame):
            print("\nReceived interrupt signal. Cleaning up...")
            self.cleanup()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def start_helics_broker(self):
        """Start HELICS broker"""
        print("\n=== Starting HELICS Broker ===")
        
        broker_cmd = f"helics_broker -f 3 --loglevel=warning --port={self.config['helics_broker_port']}"
        broker_log = os.path.join(self.results_dir, 'helics_broker.log')
        
        process = run_command(broker_cmd, output_file=broker_log)
        if process:
            self.processes.append(('helics_broker', process))
            print(f"HELICS broker started (PID: {process.pid})")
            time.sleep(2)  # Allow broker to initialize
            return True
        return False
    
    def start_grid_simulation(self):
        """Start the 2bus-13bus grid simulation"""
        print("\n=== Starting Grid Simulation ===")
        
        # Start GridPACK federate
        print("Starting GridPACK federate...")
        gpk_cmd = "./build/gpk-left-fed.x"
        gpk_log = os.path.join(self.results_dir, 'gridpack.log')
        
        gpk_process = run_command(gpk_cmd, cwd=self.example_dir, output_file=gpk_log)
        if gpk_process:
            self.processes.append(('gridpack', gpk_process))
            print(f"GridPACK federate started (PID: {gpk_process.pid})")
        
        time.sleep(3)  # Allow GridPACK to initialize
        
        # Start GridLAB-D federate
        print("Starting GridLAB-D federate...")
        gld_cmd = "gridlabd IEEE13bus.glm"
        gld_log = os.path.join(self.results_dir, 'gridlabd.log')
        
        gld_process = run_command(gld_cmd, cwd=self.example_dir, output_file=gld_log)
        if gld_process:
            self.processes.append(('gridlabd', gld_process))
            print(f"GridLAB-D federate started (PID: {gld_process.pid})")
        
        time.sleep(5)  # Allow simulation to initialize
        return True
    
    def start_mcp_server(self):
        """Start MCP server"""
        print("\n=== Starting MCP Server ===")
        
        # Install requirements first
        print("Installing Python requirements...")
        pip_cmd = f"pip install -r {os.path.join(self.mcp_dir, 'requirements.txt')}"
        pip_process = subprocess.run(pip_cmd, shell=True, capture_output=True, text=True)
        if pip_process.returncode != 0:
            print(f"Warning: Some requirements may not have installed: {pip_process.stderr}")
        
        # Start MCP server
        server_cmd = f"python3 {os.path.join(self.mcp_dir, 'src', 'server.py')}"
        server_log = os.path.join(self.results_dir, 'mcp_server.log')
        
        # Set environment variables
        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.join(self.mcp_dir, 'src')
        
        process = subprocess.Popen(
            server_cmd, shell=True,
            stdout=open(server_log, 'w'),
            stderr=subprocess.STDOUT,
            env=env,
            preexec_fn=os.setsid
        )
        
        if process:
            self.processes.append(('mcp_server', process))
            print(f"MCP server started (PID: {process.pid})")
            
            # Wait for server to be ready
            print("Waiting for MCP server to initialize...")
            for i in range(30):  # Wait up to 30 seconds
                try:
                    response = requests.get(f"http://localhost:{self.config['mcp_server_port']}/api/status", timeout=2)
                    if response.status_code == 200:
                        print("MCP server is ready!")
                        return True
                except:
                    pass
                time.sleep(1)
            
            print("Warning: MCP server may not be fully ready")
            return True
        
        return False
    
    def wait_for_simulation_ready(self):
        """Wait for simulation to be ready"""
        print("\n=== Waiting for Simulation to Initialize ===")
        
        for i in range(60):  # Wait up to 60 seconds
            try:
                # Check MCP server status
                response = requests.get(f"http://localhost:{self.config['mcp_server_port']}/api/status", timeout=2)
                if response.status_code == 200:
                    status = response.json()
                    if status.get('server', {}).get('federation_active', False):
                        print("Simulation federation is active!")
                        return True
            except Exception as e:
                pass
            
            print(f"Waiting for simulation... ({i+1}/60)")
            time.sleep(1)
        
        print("Warning: Simulation may not be fully ready, proceeding anyway...")
        return False
    
    def run_ai_attack_demo(self):
        """Run AI-assisted attack demo"""
        print("\n=== Running AI-Assisted Attack Demo ===")
        
        try:
            # Get initial status
            response = requests.get(f"http://localhost:{self.config['mcp_server_port']}/api/status")
            print("Initial grid status:", json.dumps(response.json(), indent=2))
            
            # Execute AI campaign
            campaign_data = {
                'campaign': {
                    'duration': self.config['simulation_duration'],
                    'objective': 'Demonstrate AI-driven strategic attack progression'
                }
            }
            
            print(f"Starting AI attack campaign (duration: {self.config['simulation_duration']}s)...")
            response = requests.post(
                f"http://localhost:{self.config['mcp_server_port']}/api/ai/execute",
                json=campaign_data,
                timeout=self.config['simulation_duration'] + 30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Save results
                ai_result_file = os.path.join(self.results_dir, f'ai_campaign_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
                with open(ai_result_file, 'w') as f:
                    json.dump(result, f, indent=2)
                
                print(f"AI campaign completed!")
                print(f"Attacks executed: {result.get('attack_count', 0)}")
                print(f"Effectiveness score: {result.get('effectiveness_score', 0):.2f}")
                print(f"Results saved to: {ai_result_file}")
                
                return result
            else:
                print(f"AI campaign failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error in AI attack demo: {e}")
            return None
    
    def run_random_attack_demo(self):
        """Run random attack demo for comparison"""
        print("\n=== Running Random Attack Demo ===")
        
        try:
            # Execute random campaign
            campaign_data = {
                'campaign': {
                    'duration': self.config['simulation_duration']
                }
            }
            
            print(f"Starting random attack campaign (duration: {self.config['simulation_duration']}s)...")
            response = requests.post(
                f"http://localhost:{self.config['mcp_server_port']}/api/random/execute",
                json=campaign_data,
                timeout=self.config['simulation_duration'] + 30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Save results
                random_result_file = os.path.join(self.results_dir, f'random_campaign_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
                with open(random_result_file, 'w') as f:
                    json.dump(result, f, indent=2)
                
                print(f"Random campaign completed!")
                print(f"Attacks executed: {result.get('attack_count', 0)}")
                print(f"Effectiveness score: {result.get('effectiveness_score', 0):.2f}")
                print(f"Results saved to: {random_result_file}")
                
                return result
            else:
                print(f"Random campaign failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error in random attack demo: {e}")
            return None
    
    def run_comparison_demo(self):
        """Run comparison between AI and random attacks"""
        print("\n=== Running AI vs Random Comparison Demo ===")
        
        try:
            campaign_data = {
                'campaign': {
                    'duration': self.config['simulation_duration'],
                    'trials': self.config['comparison_trials']
                }
            }
            
            print(f"Starting comparison study ({self.config['comparison_trials']} trials each)...")
            response = requests.post(
                f"http://localhost:{self.config['mcp_server_port']}/api/comparison",
                json=campaign_data,
                timeout=(self.config['simulation_duration'] * self.config['comparison_trials'] * 2) + 60
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Save results
                comparison_result_file = os.path.join(self.results_dir, f'comparison_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
                with open(comparison_result_file, 'w') as f:
                    json.dump(result, f, indent=2)
                
                print(f"Comparison study completed!")
                
                # Display summary
                metrics = result.get('comparison_metrics', {})
                print(f"\nResults Summary:")
                print(f"AI mean effectiveness: {metrics.get('ai_mean', 0):.2f}")
                print(f"Random mean effectiveness: {metrics.get('random_mean', 0):.2f}")
                print(f"AI improvement ratio: {metrics.get('improvement_ratio', 0):.2f}x")
                print(f"AI success rate: {metrics.get('ai_success_rate', 0):.2f}")
                print(f"Random success rate: {metrics.get('random_success_rate', 0):.2f}")
                print(f"Results saved to: {comparison_result_file}")
                
                return result
            else:
                print(f"Comparison failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error in comparison demo: {e}")
            return None
    
    def cleanup(self):
        """Clean up processes"""
        print("\n=== Cleaning Up ===")
        
        for name, process in reversed(self.processes):
            try:
                print(f"Terminating {name} (PID: {process.pid})")
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"Force killing {name}")
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    
            except Exception as e:
                print(f"Error terminating {name}: {e}")
        
        self.processes.clear()
        print("Cleanup completed")
    
    def run_demo(self, mode='comparison'):
        """Run the complete demo"""
        print("=" * 60)
        print("AI-Assisted Grid Penetration Testing Demo")
        print("ROI UNCC MCP Project")
        print("=" * 60)
        
        try:
            # Setup signal handlers
            self.setup_signal_handlers()
            
            # Start components
            if not self.start_helics_broker():
                print("Failed to start HELICS broker")
                return False
            
            if not self.start_grid_simulation():
                print("Failed to start grid simulation")
                return False
            
            if not self.start_mcp_server():
                print("Failed to start MCP server")
                return False
            
            # Wait for everything to be ready
            self.wait_for_simulation_ready()
            
            # Run the requested demo mode
            if mode == 'ai':
                result = self.run_ai_attack_demo()
            elif mode == 'random':
                result = self.run_random_attack_demo()
            elif mode == 'comparison':
                result = self.run_comparison_demo()
            else:
                print(f"Unknown mode: {mode}")
                return False
            
            print(f"\nDemo completed successfully!")
            print(f"Results available in: {self.results_dir}")
            
            return True
            
        except Exception as e:
            print(f"Demo failed: {e}")
            return False
        finally:
            self.cleanup()

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='AI-Assisted Grid Penetration Testing Demo')
    parser.add_argument('--mode', choices=['ai', 'random', 'comparison'], default='comparison',
                      help='Demo mode: ai (AI attacks only), random (random attacks only), comparison (both)')
    parser.add_argument('--duration', type=int, default=60,
                      help='Attack campaign duration in seconds (default: 60)')
    parser.add_argument('--trials', type=int, default=3,
                      help='Number of trials for comparison mode (default: 3)')
    
    args = parser.parse_args()
    
    # Create launcher
    launcher = DemoLauncher()
    launcher.config['simulation_duration'] = args.duration
    launcher.config['comparison_trials'] = args.trials
    
    # Run demo
    success = launcher.run_demo(args.mode)
    
    if success:
        print("\nDemo completed successfully!")
        sys.exit(0)
    else:
        print("\nDemo failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()
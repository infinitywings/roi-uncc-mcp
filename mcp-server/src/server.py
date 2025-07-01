#!/usr/bin/env python3
"""
MCP Server - Model Context Protocol Server for AI-Assisted Grid Penetration Testing
Provides REST API for AI models to interact with power grid co-simulation
"""

import json
import logging
import time
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import os
import sys

# Add the src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from federate import GridAttackFederate
from attacks.attack_engine import AttackEngine
from monitor.grid_monitor import GridMonitor
from utils.validation import ThreatModelValidator
from ai.local_llm_client import LocalLLMStrategist

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MCPServer:
    """Main MCP Server class"""
    
    def __init__(self, config_path='config/mcp.yaml'):
        self.app = Flask(__name__)
        CORS(self.app)
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.federate = None
        self.attack_engine = None
        self.grid_monitor = None
        self.threat_validator = None
        self.ai_strategist = None
        
        # Server state
        self.is_running = False
        self.federation_active = False
        
        # Setup routes
        self._setup_routes()
        
        logger.info("MCP Server initialized")
    
    def _load_config(self, config_path):
        """Load server configuration"""
        default_config = {
            'server': {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False
            },
            'helics': {
                'broker_address': 'tcp://127.0.0.1:23404',
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
                'api_base': 'http://host.docker.internal:8000/v1',
                'api_key_file': '../API.txt',
                'model': 'Qwen/Qwen3-30B-A3B',
                'temperature': 0.8,
                'max_tokens': 2000
            }
        }
        
        # Try to load from file, fallback to defaults
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    import yaml
                    file_config = yaml.safe_load(f)
                    # Merge with defaults
                    for section, values in file_config.items():
                        if section in default_config:
                            default_config[section].update(values)
                        else:
                            default_config[section] = values
        except Exception as e:
            logger.warning(f"Could not load config file {config_path}: {e}, using defaults")
        
        return default_config
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/api/status', methods=['GET'])
        def get_status():
            """Get current grid status and MCP server state"""
            try:
                status = {
                    'server': {
                        'running': self.is_running,
                        'federation_active': self.federation_active,
                        'timestamp': datetime.now().isoformat()
                    }
                }
                
                if self.grid_monitor:
                    status['grid'] = self.grid_monitor.get_current_state()
                
                if self.federate:
                    status['federate'] = self.federate.get_status()
                
                return jsonify(status)
            except Exception as e:
                logger.error(f"Error getting status: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/attack', methods=['POST'])
        def execute_attack():
            """Execute an attack primitive"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No JSON data provided'}), 400
                
                technique = data.get('technique')
                params = data.get('params', {})
                
                if not technique:
                    return jsonify({'error': 'No attack technique specified'}), 400
                
                # Validate attack with threat model
                if self.threat_validator:
                    validation_result = self.threat_validator.validate_attack(technique, params)
                    if not validation_result['valid']:
                        return jsonify({
                            'error': 'Attack violates threat model',
                            'details': validation_result['reason']
                        }), 403
                
                # Execute attack
                if not self.attack_engine:
                    return jsonify({'error': 'Attack engine not initialized'}), 503
                
                result = self.attack_engine.execute_attack(technique, params)
                return jsonify(result)
                
            except Exception as e:
                logger.error(f"Error executing attack: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/reconnaissance', methods=['GET'])
        def reconnaissance():
            """Perform grid reconnaissance"""
            try:
                if not self.attack_engine:
                    return jsonify({'error': 'Attack engine not initialized'}), 503
                
                recon_data = self.attack_engine.execute_attack('reconnaissance', {})
                return jsonify(recon_data)
                
            except Exception as e:
                logger.error(f"Error in reconnaissance: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/ai/plan', methods=['POST'])
        def ai_plan_attack():
            """Get AI-generated attack plan"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No JSON data provided'}), 400
                
                objective = data.get('objective', 'Maximize grid disruption')
                context = data.get('context', {})
                
                if not self.ai_strategist:
                    return jsonify({'error': 'AI strategist not initialized'}), 503
                
                # Get current grid state for context
                if self.grid_monitor:
                    context['current_grid_state'] = self.grid_monitor.get_current_state()
                
                plan = self.ai_strategist.plan_attack(objective, context)
                return jsonify(plan)
                
            except Exception as e:
                logger.error(f"Error in AI planning: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/ai/execute', methods=['POST'])
        def ai_execute_attack():
            """Execute AI-planned attack sequence"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No JSON data provided'}), 400
                
                campaign_config = data.get('campaign', {})
                duration = campaign_config.get('duration', 60)  # seconds
                
                if not self.ai_strategist:
                    return jsonify({'error': 'AI strategist not initialized'}), 503
                
                # Execute AI campaign
                result = self.ai_strategist.execute_campaign(duration)
                return jsonify(result)
                
            except Exception as e:
                logger.error(f"Error in AI execution: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/random/execute', methods=['POST'])
        def random_execute_attack():
            """Execute random attack sequence for comparison"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No JSON data provided'}), 400
                
                campaign_config = data.get('campaign', {})
                duration = campaign_config.get('duration', 60)  # seconds
                
                if not self.attack_engine:
                    return jsonify({'error': 'Attack engine not initialized'}), 503
                
                # Execute random campaign
                result = self.attack_engine.execute_random_campaign(duration)
                return jsonify(result)
                
            except Exception as e:
                logger.error(f"Error in random execution: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/comparison', methods=['POST'])
        def compare_strategies():
            """Execute comparison between AI and random strategies"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No JSON data provided'}), 400
                
                campaign_config = data.get('campaign', {})
                duration = campaign_config.get('duration', 60)  # seconds
                trials = campaign_config.get('trials', 3)
                
                comparison_result = {
                    'configuration': campaign_config,
                    'ai_results': [],
                    'random_results': [],
                    'comparison_metrics': {}
                }
                
                # Execute multiple trials for statistical significance
                for trial in range(trials):
                    logger.info(f"Executing comparison trial {trial + 1}/{trials}")
                    
                    # Reset grid state between trials
                    if self.federate:
                        self.federate.reset_grid_state()
                    
                    # AI campaign
                    if self.ai_strategist:
                        ai_result = self.ai_strategist.execute_campaign(duration)
                        ai_result['trial'] = trial + 1
                        comparison_result['ai_results'].append(ai_result)
                    
                    # Reset grid state
                    if self.federate:
                        self.federate.reset_grid_state()
                    
                    # Random campaign
                    if self.attack_engine:
                        random_result = self.attack_engine.execute_random_campaign(duration)
                        random_result['trial'] = trial + 1
                        comparison_result['random_results'].append(random_result)
                
                # Calculate comparison metrics
                comparison_result['comparison_metrics'] = self._calculate_comparison_metrics(
                    comparison_result['ai_results'],
                    comparison_result['random_results']
                )
                
                return jsonify(comparison_result)
                
            except Exception as e:
                logger.error(f"Error in comparison: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/shutdown', methods=['POST'])
        def shutdown():
            """Shutdown the MCP server"""
            try:
                self.stop()
                return jsonify({'message': 'Server shutting down'})
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
                return jsonify({'error': str(e)}), 500
    
    def _calculate_comparison_metrics(self, ai_results, random_results):
        """Calculate statistical comparison metrics"""
        metrics = {}
        
        if not ai_results or not random_results:
            return metrics
        
        try:
            # Extract effectiveness scores
            ai_scores = [r.get('effectiveness_score', 0) for r in ai_results]
            random_scores = [r.get('effectiveness_score', 0) for r in random_results]
            
            # Basic statistics
            metrics['ai_mean'] = sum(ai_scores) / len(ai_scores)
            metrics['ai_max'] = max(ai_scores)
            metrics['random_mean'] = sum(random_scores) / len(random_scores)
            metrics['random_max'] = max(random_scores)
            
            # Improvement ratio (use string "Infinity" for JSON compatibility)
            if metrics['random_mean'] > 0:
                metrics['improvement_ratio'] = metrics['ai_mean'] / metrics['random_mean']
            else:
                metrics['improvement_ratio'] = "Infinity"
            
            # Success rate (attacks that caused measurable impact)
            ai_successes = sum(1 for score in ai_scores if score > 10)
            random_successes = sum(1 for score in random_scores if score > 10)
            
            metrics['ai_success_rate'] = ai_successes / len(ai_scores) if ai_scores else 0
            metrics['random_success_rate'] = random_successes / len(random_scores) if random_scores else 0
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            metrics['error'] = str(e)
        
        return metrics
    
    def initialize_federation(self):
        """Initialize HELICS federation and components"""
        try:
            logger.info("Initializing HELICS federation...")
            
            # Initialize federate
            self.federate = GridAttackFederate(self.config['helics'])
            self.federate.initialize()
            
            # Initialize attack engine
            self.attack_engine = AttackEngine(self.federate)
            
            # Initialize grid monitor
            self.grid_monitor = GridMonitor(self.federate)
            
            # Initialize threat validator
            self.threat_validator = ThreatModelValidator('config/threat_model.yaml')
            
            # Initialize AI strategist
            try:
                self.ai_strategist = LocalLLMStrategist(
                    self.config['ai'], 
                    self.attack_engine, 
                    self.grid_monitor
                )
            except Exception as e:
                logger.warning(f"Could not initialize AI strategist: {e}")
                self.ai_strategist = None
            
            self.federation_active = True
            logger.info("HELICS federation initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize federation: {e}")
            raise
    
    def start(self):
        """Start the MCP server"""
        try:
            logger.info("Starting MCP Server...")
            
            # Initialize federation first
            self.initialize_federation()
            
            self.is_running = True
            
            # Start the Flask app
            host = self.config['server']['host']
            port = self.config['server']['port']
            debug = self.config['server']['debug']
            
            logger.info(f"MCP Server starting on {host}:{port}")
            self.app.run(host=host, port=port, debug=debug, threaded=True)
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise
    
    def stop(self):
        """Stop the MCP server"""
        try:
            logger.info("Stopping MCP Server...")
            
            self.is_running = False
            
            # Shutdown federation components
            if self.federate:
                self.federate.finalize()
            
            self.federation_active = False
            
            logger.info("MCP Server stopped")
            
        except Exception as e:
            logger.error(f"Error stopping server: {e}")
            raise

def main():
    """Main entry point"""
    try:
        server = MCPServer('mcp-server/config/mcp.yaml')
        server.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
Grid Monitor - Real-time grid state monitoring and analytics
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from collections import deque
import json
import numpy as np

logger = logging.getLogger(__name__)

class GridMonitor:
    """Real-time grid monitoring and analytics"""
    
    def __init__(self, federate, history_size=1000):
        self.federate = federate
        self.history_size = history_size
        
        # State history
        self.state_history = deque(maxlen=history_size)
        self.anomaly_history = deque(maxlen=history_size)
        
        # Monitoring thread
        self.monitoring_active = False
        self.monitor_thread = None
        
        # Analytics
        self.baseline_state = None
        self.thresholds = {
            'voltage_deviation': 0.05,  # 5% from nominal
            'power_deviation': 0.1,     # 10% from baseline
            'health_degradation': 10    # Health score points
        }
        
        logger.info("Grid monitor initialized")
    
    def start_monitoring(self, interval=1.0):
        """Start continuous grid monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"Grid monitoring started with {interval}s interval")
    
    def stop_monitoring(self):
        """Stop grid monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Grid monitoring stopped")
    
    def _monitoring_loop(self, interval):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                # Get current state
                current_state = self.federate.get_current_state()
                
                # Add timestamp
                current_state['monitor_timestamp'] = datetime.now().isoformat()
                
                # Store in history
                self.state_history.append(current_state)
                
                # Detect anomalies
                anomalies = self._detect_anomalies(current_state)
                if anomalies:
                    self.anomaly_history.append({
                        'timestamp': current_state['monitor_timestamp'],
                        'anomalies': anomalies
                    })
                
                # Set baseline if not set
                if self.baseline_state is None and current_state.get('system_health', {}).get('status') == 'healthy':
                    self.baseline_state = current_state.copy()
                    logger.info("Baseline grid state established")
                
                time.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(interval)
    
    def _detect_anomalies(self, current_state):
        """Detect anomalies in grid state"""
        anomalies = []
        
        try:
            if not self.baseline_state:
                return anomalies
            
            # Voltage anomalies
            baseline_voltages = self.baseline_state.get('voltages', {})
            current_voltages = current_state.get('voltages', {})
            
            for voltage_name, current_data in current_voltages.items():
                if voltage_name in baseline_voltages:
                    baseline_mag = baseline_voltages[voltage_name]['magnitude']
                    current_mag = current_data['magnitude']
                    
                    if baseline_mag > 0:
                        deviation = abs(current_mag - baseline_mag) / baseline_mag
                        if deviation > self.thresholds['voltage_deviation']:
                            anomalies.append({
                                'type': 'voltage_anomaly',
                                'location': voltage_name,
                                'baseline': baseline_mag,
                                'current': current_mag,
                                'deviation': deviation,
                                'severity': 'high' if deviation > 0.1 else 'medium'
                            })
            
            # Power anomalies
            baseline_powers = self.baseline_state.get('powers', {})
            current_powers = current_state.get('powers', {})
            
            for power_name, current_data in current_powers.items():
                if power_name in baseline_powers:
                    baseline_mag = baseline_powers[power_name]['magnitude']
                    current_mag = current_data['magnitude']
                    
                    if baseline_mag > 0:
                        deviation = abs(current_mag - baseline_mag) / baseline_mag
                        if deviation > self.thresholds['power_deviation']:
                            anomalies.append({
                                'type': 'power_anomaly',
                                'location': power_name,
                                'baseline': baseline_mag,
                                'current': current_mag,
                                'deviation': deviation,
                                'severity': 'high' if deviation > 0.2 else 'medium'
                            })
            
            # System health anomalies
            baseline_health = self.baseline_state.get('system_health', {}).get('score', 100)
            current_health = current_state.get('system_health', {}).get('score', 100)
            
            health_degradation = baseline_health - current_health
            if health_degradation > self.thresholds['health_degradation']:
                anomalies.append({
                    'type': 'health_degradation',
                    'baseline_score': baseline_health,
                    'current_score': current_health,
                    'degradation': health_degradation,
                    'severity': 'critical' if health_degradation > 30 else 'high'
                })
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            anomalies.append({
                'type': 'detection_error',
                'error': str(e)
            })
        
        return anomalies
    
    def get_current_state(self):
        """Get current grid state"""
        return self.federate.get_current_state()
    
    def get_state_history(self, minutes=None):
        """Get historical grid states"""
        if minutes is None:
            return list(self.state_history)
        
        # Filter by time
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        filtered_history = []
        
        for state in self.state_history:
            try:
                state_time = datetime.fromisoformat(state.get('monitor_timestamp', ''))
                if state_time >= cutoff_time:
                    filtered_history.append(state)
            except:
                continue
        
        return filtered_history
    
    def get_anomaly_history(self, minutes=None):
        """Get anomaly history"""
        if minutes is None:
            return list(self.anomaly_history)
        
        # Filter by time
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        filtered_anomalies = []
        
        for anomaly in self.anomaly_history:
            try:
                anomaly_time = datetime.fromisoformat(anomaly.get('timestamp', ''))
                if anomaly_time >= cutoff_time:
                    filtered_anomalies.append(anomaly)
            except:
                continue
        
        return filtered_anomalies
    
    def calculate_stability_metrics(self):
        """Calculate grid stability metrics"""
        metrics = {
            'voltage_stability': 0,
            'power_stability': 0,
            'overall_stability': 0,
            'anomaly_rate': 0
        }
        
        try:
            if len(self.state_history) < 2:
                return metrics
            
            # Calculate voltage stability (standard deviation of voltage magnitudes)
            voltage_variations = []
            for state in list(self.state_history)[-min(100, len(self.state_history)):]:
                for voltage_data in state.get('voltages', {}).values():
                    pu_voltage = voltage_data['magnitude'] / 2401.78
                    voltage_variations.append(pu_voltage)
            
            if voltage_variations:
                voltage_std = np.std(voltage_variations)
                metrics['voltage_stability'] = max(0, 100 - voltage_std * 100)
            
            # Calculate power stability
            power_variations = []
            for state in list(self.state_history)[-min(100, len(self.state_history)):]:
                for power_data in state.get('powers', {}).values():
                    power_variations.append(power_data['magnitude'])
            
            if power_variations:
                # Normalize by mean power
                mean_power = np.mean(power_variations)
                if mean_power > 0:
                    power_cv = np.std(power_variations) / mean_power
                    metrics['power_stability'] = max(0, 100 - power_cv * 100)
            
            # Overall stability
            metrics['overall_stability'] = (
                metrics['voltage_stability'] * 0.6 +
                metrics['power_stability'] * 0.4
            )
            
            # Anomaly rate (anomalies per hour)
            recent_anomalies = self.get_anomaly_history(minutes=60)
            metrics['anomaly_rate'] = len(recent_anomalies)
            
        except Exception as e:
            logger.error(f"Error calculating stability metrics: {e}")
            metrics['error'] = str(e)
        
        return metrics
    
    def get_attack_impact_analysis(self):
        """Analyze impact of recent attacks"""
        analysis = {
            'recent_attacks': [],
            'impact_summary': {},
            'recovery_assessment': {}
        }
        
        try:
            # Get attack history from federate
            attack_history = self.federate.get_attack_history()
            
            # Analyze recent attacks (last 10 minutes)
            recent_attacks = [
                attack for attack in attack_history
                if (time.time() - attack.get('timestamp', 0)) < 600
            ]
            
            analysis['recent_attacks'] = recent_attacks
            
            # Analyze impact on grid stability
            if recent_attacks:
                pre_attack_time = min(attack['timestamp'] for attack in recent_attacks) - 60
                post_attack_time = max(attack['timestamp'] for attack in recent_attacks) + 60
                
                # Get states before and after attacks
                pre_attack_states = [
                    state for state in self.state_history
                    if self._get_timestamp(state) < pre_attack_time
                ]
                post_attack_states = [
                    state for state in self.state_history
                    if self._get_timestamp(state) > post_attack_time
                ]
                
                if pre_attack_states and post_attack_states:
                    pre_health = np.mean([
                        state.get('system_health', {}).get('score', 100)
                        for state in pre_attack_states[-10:]
                    ])
                    post_health = np.mean([
                        state.get('system_health', {}).get('score', 100)
                        for state in post_attack_states[:10]
                    ])
                    
                    analysis['impact_summary'] = {
                        'health_degradation': pre_health - post_health,
                        'attack_count': len(recent_attacks),
                        'attack_types': list(set(attack.get('type', 'unknown') for attack in recent_attacks))
                    }
            
        except Exception as e:
            logger.error(f"Error in attack impact analysis: {e}")
            analysis['error'] = str(e)
        
        return analysis
    
    def _get_timestamp(self, state):
        """Extract timestamp from state"""
        try:
            timestamp_str = state.get('monitor_timestamp', state.get('timestamp', ''))
            return datetime.fromisoformat(timestamp_str).timestamp()
        except:
            return 0
    
    def get_vulnerability_assessment(self):
        """Assess current grid vulnerabilities"""
        assessment = {
            'voltage_vulnerabilities': [],
            'power_vulnerabilities': [],
            'stability_vulnerabilities': [],
            'overall_risk_level': 'unknown'
        }
        
        try:
            current_state = self.get_current_state()
            
            # Voltage vulnerabilities
            for voltage_name, voltage_data in current_state.get('voltages', {}).items():
                pu_voltage = voltage_data['magnitude'] / 2401.78
                
                if pu_voltage < 0.95:
                    assessment['voltage_vulnerabilities'].append({
                        'location': voltage_name,
                        'type': 'undervoltage',
                        'severity': 'high' if pu_voltage < 0.9 else 'medium',
                        'value': pu_voltage,
                        'risk': 'Protection system activation, load shedding'
                    })
                elif pu_voltage > 1.05:
                    assessment['voltage_vulnerabilities'].append({
                        'location': voltage_name,
                        'type': 'overvoltage',
                        'severity': 'high' if pu_voltage > 1.1 else 'medium',
                        'value': pu_voltage,
                        'risk': 'Equipment damage, insulation stress'
                    })
            
            # Power system vulnerabilities
            system_health = current_state.get('system_health', {})
            if system_health.get('status') != 'healthy':
                assessment['power_vulnerabilities'].append({
                    'type': 'system_stress',
                    'severity': 'high' if system_health.get('score', 100) < 70 else 'medium',
                    'score': system_health.get('score', 100),
                    'issues': system_health.get('issues', []),
                    'risk': 'Cascading failures, system instability'
                })
            
            # Stability vulnerabilities
            stability_metrics = self.calculate_stability_metrics()
            if stability_metrics['overall_stability'] < 80:
                assessment['stability_vulnerabilities'].append({
                    'type': 'instability',
                    'severity': 'high' if stability_metrics['overall_stability'] < 60 else 'medium',
                    'stability_score': stability_metrics['overall_stability'],
                    'risk': 'Oscillations, control system failures'
                })
            
            # Overall risk assessment
            total_vulns = (
                len(assessment['voltage_vulnerabilities']) +
                len(assessment['power_vulnerabilities']) +
                len(assessment['stability_vulnerabilities'])
            )
            
            high_severity = sum(1 for vulns in assessment.values() 
                              if isinstance(vulns, list) 
                              for vuln in vulns 
                              if vuln.get('severity') == 'high')
            
            if high_severity > 2:
                assessment['overall_risk_level'] = 'critical'
            elif high_severity > 0 or total_vulns > 3:
                assessment['overall_risk_level'] = 'high'
            elif total_vulns > 0:
                assessment['overall_risk_level'] = 'medium'
            else:
                assessment['overall_risk_level'] = 'low'
            
        except Exception as e:
            logger.error(f"Error in vulnerability assessment: {e}")
            assessment['error'] = str(e)
        
        return assessment
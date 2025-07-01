#!/usr/bin/env python3
"""
Attack Engine - Implements attack primitives for grid penetration testing
"""

import logging
import random
import time
import json
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AttackEngine:
    """Main attack execution engine"""
    
    def __init__(self, federate):
        self.federate = federate
        
        # Available attack techniques
        self.techniques = {
            'spoof_data': self._spoof_data,
            'inject_load': self._inject_load,
            'reconnaissance': self._reconnaissance,
            'block_command': self._block_command,
            'toggle_device': self._toggle_device
        }
        
        # Attack parameters and constraints
        self.attack_params = {
            'voltage_limits': {'min': 0.7, 'max': 1.3},  # per unit
            'power_limits': {'max': 5000000},  # VA
            'timing_limits': {'min_interval': 1.0}  # seconds
        }
        
        logger.info("Attack engine initialized")
    
    def execute_attack(self, technique, params):
        """Execute a specific attack technique"""
        try:
            if technique not in self.techniques:
                return {
                    'success': False,
                    'error': f'Unknown attack technique: {technique}',
                    'available_techniques': list(self.techniques.keys())
                }
            
            # Get current grid state before attack
            pre_attack_state = self.federate.get_current_state()
            
            # Execute the attack
            result = self.techniques[technique](params)
            
            # Advance time to see impact
            self.federate.advance_time()
            
            # Get post-attack state
            post_attack_state = self.federate.get_current_state()
            
            # Calculate impact
            impact = self._calculate_impact(pre_attack_state, post_attack_state)
            
            result.update({
                'technique': technique,
                'timestamp': datetime.now().isoformat(),
                'pre_attack_state': pre_attack_state,
                'post_attack_state': post_attack_state,
                'impact': impact
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing attack {technique}: {e}")
            return {
                'success': False,
                'error': str(e),
                'technique': technique,
                'timestamp': datetime.now().isoformat()
            }
    
    def _spoof_data(self, params):
        """Spoof voltage or power data"""
        try:
            target = params.get('target', 'voltage_A')
            
            if 'voltage' in target:
                # Voltage spoofing
                phase = target.split('_')[-1] if '_' in target else 'A'
                
                # Generate malicious voltage
                if 'value' in params:
                    # Use specified value
                    voltage_mag = params['value']
                else:
                    # Generate strategic voltage based on current state
                    current_state = self.federate.get_current_state()
                    voltage_mag = self._generate_strategic_voltage(current_state, phase)
                
                phase_angle = params.get('phase', 0)  # degrees
                
                # Convert to complex
                voltage_complex = {
                    'real': voltage_mag * np.cos(np.radians(phase_angle)),
                    'imag': voltage_mag * np.sin(np.radians(phase_angle))
                }
                
                success = self.federate.inject_voltage_attack(phase, voltage_complex)
                
                return {
                    'success': success,
                    'attack_type': 'voltage_spoof',
                    'target_phase': phase,
                    'injected_voltage': voltage_complex,
                    'magnitude': voltage_mag,
                    'angle': phase_angle
                }
            
            elif 'power' in target:
                # Power spoofing
                phase = target.split('_')[-1] if '_' in target else 'A'
                
                # Generate malicious power
                if 'value' in params:
                    power_mag = params['value']
                else:
                    power_mag = self._generate_strategic_power(phase)
                
                power_factor = params.get('power_factor', 0.9)
                power_angle = np.arccos(power_factor)
                
                # Convert to complex
                power_complex = {
                    'real': power_mag * power_factor,
                    'imag': power_mag * np.sin(power_angle)
                }
                
                success = self.federate.inject_power_attack(phase, power_complex)
                
                return {
                    'success': success,
                    'attack_type': 'power_spoof',
                    'target_phase': phase,
                    'injected_power': power_complex,
                    'magnitude': power_mag,
                    'power_factor': power_factor
                }
            
            else:
                return {
                    'success': False,
                    'error': f'Invalid spoof target: {target}',
                    'valid_targets': ['voltage_A', 'voltage_B', 'voltage_C', 'power_A', 'power_B', 'power_C']
                }
            
        except Exception as e:
            logger.error(f"Error in spoof_data attack: {e}")
            return {'success': False, 'error': str(e)}
    
    def _inject_load(self, params):
        """Inject artificial load"""
        try:
            phase = params.get('phase', 'A')
            magnitude = params.get('magnitude', 1000000)  # 1 MVA default
            power_factor = params.get('power_factor', 0.9)
            
            # Calculate power components
            real_power = magnitude * power_factor
            reactive_power = magnitude * np.sin(np.arccos(power_factor))
            
            power_complex = {
                'real': real_power,
                'imag': reactive_power
            }
            
            success = self.federate.inject_power_attack(phase, power_complex)
            
            return {
                'success': success,
                'attack_type': 'load_injection',
                'target_phase': phase,
                'injected_load': power_complex,
                'magnitude_va': magnitude,
                'power_factor': power_factor
            }
            
        except Exception as e:
            logger.error(f"Error in inject_load attack: {e}")
            return {'success': False, 'error': str(e)}
    
    def _reconnaissance(self, params):
        """Perform grid reconnaissance"""
        try:
            # Get current grid state
            current_state = self.federate.get_current_state()
            
            # Analyze grid topology and vulnerabilities
            recon_data = {
                'success': True,
                'attack_type': 'reconnaissance',
                'grid_topology': self._analyze_topology(current_state),
                'vulnerabilities': self._identify_vulnerabilities(current_state),
                'attack_surfaces': self._identify_attack_surfaces(current_state),
                'recommendations': self._generate_attack_recommendations(current_state)
            }
            
            return recon_data
            
        except Exception as e:
            logger.error(f"Error in reconnaissance: {e}")
            return {'success': False, 'error': str(e)}
    
    def _block_command(self, params):
        """Block control commands"""
        try:
            enable = params.get('enable', True)
            duration = params.get('duration', 10)  # seconds
            
            success = self.federate.block_commands(enable)
            
            return {
                'success': success,
                'attack_type': 'command_blocking',
                'blocking_enabled': enable,
                'duration': duration
            }
            
        except Exception as e:
            logger.error(f"Error in block_command attack: {e}")
            return {'success': False, 'error': str(e)}
    
    def _toggle_device(self, params):
        """Toggle device state (placeholder - would need specific device control)"""
        try:
            device = params.get('device', 'switch1')
            state = params.get('state', 'open')
            
            # This is a placeholder - actual implementation would depend on
            # specific GridLAB-D device control mechanisms
            
            return {
                'success': True,
                'attack_type': 'device_toggle',
                'target_device': device,
                'new_state': state,
                'note': 'Placeholder implementation - requires specific device control integration'
            }
            
        except Exception as e:
            logger.error(f"Error in toggle_device attack: {e}")
            return {'success': False, 'error': str(e)}
    
    def _generate_strategic_voltage(self, current_state, phase):
        """Generate strategic voltage value based on current grid state"""
        try:
            # Find current voltage for the phase
            current_voltage = None
            for voltage_name, voltage_data in current_state.get('voltages', {}).items():
                if phase.lower() in voltage_name.lower():
                    current_voltage = voltage_data['magnitude']
                    break
            
            if current_voltage is None:
                # Default to nominal voltage
                current_voltage = 2401.78
            
            # Convert to per unit
            pu_voltage = current_voltage / 2401.78
            
            # Strategic attack logic:
            # If voltage is already low, push it lower to trigger undervoltage protection
            # If voltage is high, push it higher to cause overvoltage issues
            if pu_voltage < 0.95:
                # Push voltage lower
                target_pu = max(0.7, pu_voltage - 0.1)
            elif pu_voltage > 1.05:
                # Push voltage higher
                target_pu = min(1.3, pu_voltage + 0.1)
            else:
                # Normal voltage - create stress by going to extremes
                if random.random() < 0.5:
                    target_pu = 0.85  # Undervoltage
                else:
                    target_pu = 1.15  # Overvoltage
            
            return target_pu * 2401.78
            
        except Exception as e:
            logger.error(f"Error generating strategic voltage: {e}")
            return 2401.78 * 0.85  # Default to undervoltage attack
    
    def _generate_strategic_power(self, phase):
        """Generate strategic power injection value"""
        try:
            # Get current grid state to determine optimal power injection
            current_state = self.federate.get_current_state()
            
            # Find existing power flow
            existing_power = 0
            for power_name, power_data in current_state.get('powers', {}).items():
                if phase.lower() in power_name.lower():
                    existing_power = power_data['magnitude']
                    break
            
            # Strategic power injection:
            # Add significant load to stress the system
            # Target 50-100% increase in existing load
            if existing_power > 0:
                injection_magnitude = existing_power * (0.5 + random.random() * 0.5)
            else:
                # Default to 2 MVA injection
                injection_magnitude = 2000000
            
            # Limit to maximum allowed
            max_power = self.attack_params['power_limits']['max']
            return min(injection_magnitude, max_power)
            
        except Exception as e:
            logger.error(f"Error generating strategic power: {e}")
            return 1000000  # Default 1 MVA
    
    def _analyze_topology(self, grid_state):
        """Analyze grid topology from current state"""
        topology = {
            'identified_buses': [],
            'voltage_levels': [],
            'power_flows': [],
            'critical_nodes': []
        }
        
        try:
            # Analyze voltage measurements to identify buses
            for voltage_name, voltage_data in grid_state.get('voltages', {}).items():
                bus_info = {
                    'name': voltage_name,
                    'voltage_level': voltage_data['magnitude'],
                    'pu_voltage': voltage_data['magnitude'] / 2401.78,
                    'phase_angle': voltage_data['angle']
                }
                topology['identified_buses'].append(bus_info)
                
                # Identify voltage levels
                voltage_level = round(voltage_data['magnitude'] / 1000) * 1000
                if voltage_level not in topology['voltage_levels']:
                    topology['voltage_levels'].append(voltage_level)
            
            # Analyze power flows
            for power_name, power_data in grid_state.get('powers', {}).items():
                flow_info = {
                    'name': power_name,
                    'magnitude_mva': power_data['magnitude'] / 1e6,
                    'power_factor': power_data['power_factor'],
                    'direction': 'export' if power_data['real'] > 0 else 'import'
                }
                topology['power_flows'].append(flow_info)
            
            # Identify critical nodes (high power flows, voltage issues)
            for bus in topology['identified_buses']:
                if bus['pu_voltage'] < 0.95 or bus['pu_voltage'] > 1.05:
                    topology['critical_nodes'].append({
                        'bus': bus['name'],
                        'issue': 'voltage_violation',
                        'severity': 'high' if bus['pu_voltage'] < 0.9 or bus['pu_voltage'] > 1.1 else 'medium'
                    })
            
        except Exception as e:
            logger.error(f"Error analyzing topology: {e}")
            topology['error'] = str(e)
        
        return topology
    
    def _identify_vulnerabilities(self, grid_state):
        """Identify grid vulnerabilities"""
        vulnerabilities = []
        
        try:
            # Voltage-based vulnerabilities
            for voltage_name, voltage_data in grid_state.get('voltages', {}).items():
                pu_voltage = voltage_data['magnitude'] / 2401.78
                
                if pu_voltage < 0.95:
                    vulnerabilities.append({
                        'type': 'undervoltage',
                        'location': voltage_name,
                        'severity': 'high' if pu_voltage < 0.9 else 'medium',
                        'value': pu_voltage,
                        'exploitation': 'Further voltage reduction could trigger protection cascades'
                    })
                
                if pu_voltage > 1.05:
                    vulnerabilities.append({
                        'type': 'overvoltage',
                        'location': voltage_name,
                        'severity': 'high' if pu_voltage > 1.1 else 'medium',
                        'value': pu_voltage,
                        'exploitation': 'Voltage increase could damage equipment'
                    })
            
            # Power-based vulnerabilities
            total_power = sum(p['magnitude'] for p in grid_state.get('powers', {}).values())
            if total_power > 0:
                # Check for unbalanced loading
                phase_powers = {}
                for power_name, power_data in grid_state.get('powers', {}).items():
                    if 'Sa' in power_name or 'A' in power_name:
                        phase_powers['A'] = power_data['magnitude']
                    elif 'Sb' in power_name or 'B' in power_name:
                        phase_powers['B'] = power_data['magnitude']
                    elif 'Sc' in power_name or 'C' in power_name:
                        phase_powers['C'] = power_data['magnitude']
                
                if len(phase_powers) >= 2:
                    max_power = max(phase_powers.values())
                    min_power = min(phase_powers.values())
                    if max_power > 0 and (max_power - min_power) / max_power > 0.2:
                        vulnerabilities.append({
                            'type': 'unbalanced_loading',
                            'severity': 'medium',
                            'phase_powers': phase_powers,
                            'imbalance_ratio': (max_power - min_power) / max_power,
                            'exploitation': 'Load injection on lightly loaded phases could worsen imbalance'
                        })
            
            # System health vulnerabilities
            system_health = grid_state.get('system_health', {})
            if system_health.get('status') in ['degraded', 'compromised', 'critical']:
                vulnerabilities.append({
                    'type': 'system_degradation',
                    'severity': 'high',
                    'health_score': system_health.get('score', 0),
                    'issues': system_health.get('issues', []),
                    'exploitation': 'System already stressed - additional attacks likely to cause failures'
                })
            
        except Exception as e:
            logger.error(f"Error identifying vulnerabilities: {e}")
            vulnerabilities.append({'type': 'analysis_error', 'error': str(e)})
        
        return vulnerabilities
    
    def _identify_attack_surfaces(self, grid_state):
        """Identify potential attack surfaces"""
        attack_surfaces = []
        
        try:
            # HELICS communication channels
            attack_surfaces.append({
                'surface': 'helics_messaging',
                'type': 'communication',
                'description': 'HELICS messages lack authentication and encryption',
                'attack_methods': ['message_tampering', 'data_injection', 'replay_attacks'],
                'impact': 'high'
            })
            
            # Voltage control points
            for voltage_name in grid_state.get('voltages', {}).keys():
                attack_surfaces.append({
                    'surface': f'voltage_control_{voltage_name}',
                    'type': 'control_system',
                    'description': f'Voltage setpoint manipulation at {voltage_name}',
                    'attack_methods': ['setpoint_manipulation', 'false_data_injection'],
                    'impact': 'high'
                })
            
            # Power flow control
            attack_surfaces.append({
                'surface': 'power_flow_control', 
                'type': 'control_system',
                'description': 'GridPACK-GridLAB-D power flow interface',
                'attack_methods': ['load_manipulation', 'power_injection'],
                'impact': 'high'
            })
            
            # Protection systems
            attack_surfaces.append({
                'surface': 'protection_coordination',
                'type': 'protection_system',
                'description': 'Protection relay coordination points',
                'attack_methods': ['protection_blinding', 'false_trip_signals'],
                'impact': 'critical'
            })
            
        except Exception as e:
            logger.error(f"Error identifying attack surfaces: {e}")
        
        return attack_surfaces
    
    def _generate_attack_recommendations(self, grid_state):
        """Generate strategic attack recommendations"""
        recommendations = []
        
        try:
            vulnerabilities = self._identify_vulnerabilities(grid_state)
            
            # Prioritize recommendations based on vulnerabilities
            for vuln in vulnerabilities:
                if vuln['type'] == 'undervoltage':
                    recommendations.append({
                        'priority': 'high',
                        'technique': 'spoof_data',
                        'target': vuln['location'],
                        'objective': 'Trigger undervoltage protection cascade',
                        'parameters': {
                            'target': f"voltage_{vuln['location'].split('_')[-1]}",
                            'value': vuln['value'] * 2401.78 * 0.9  # Reduce by 10%
                        },
                        'expected_impact': 'Protection system activation, possible load shedding'
                    })
                
                elif vuln['type'] == 'system_degradation':
                    recommendations.append({
                        'priority': 'high',
                        'technique': 'inject_load',
                        'target': 'weakest_phase',
                        'objective': 'Exploit existing system stress',
                        'parameters': {
                            'phase': 'A',  # Could be determined more strategically
                            'magnitude': 2000000  # 2 MVA
                        },
                        'expected_impact': 'System overload, cascading failures'
                    })
            
            # Always recommend reconnaissance as first step
            recommendations.insert(0, {
                'priority': 'high',
                'technique': 'reconnaissance',
                'target': 'all_systems',
                'objective': 'Gather comprehensive grid intelligence',
                'parameters': {},
                'expected_impact': 'Complete vulnerability assessment'
            })
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
        
        return recommendations
    
    def _calculate_impact(self, pre_state, post_state):
        """Calculate attack impact"""
        impact = {
            'voltage_impact': 0,
            'power_impact': 0,
            'system_health_impact': 0,
            'total_impact_score': 0
        }
        
        try:
            # Voltage impact
            voltage_changes = []
            pre_voltages = pre_state.get('voltages', {})
            post_voltages = post_state.get('voltages', {})
            
            for voltage_name in pre_voltages.keys():
                if voltage_name in post_voltages:
                    pre_mag = pre_voltages[voltage_name]['magnitude']
                    post_mag = post_voltages[voltage_name]['magnitude']
                    change = abs(post_mag - pre_mag) / pre_mag if pre_mag > 0 else 0
                    voltage_changes.append(change)
            
            if voltage_changes:
                impact['voltage_impact'] = max(voltage_changes) * 100  # Percentage
            
            # Power impact
            power_changes = []
            pre_powers = pre_state.get('powers', {})
            post_powers = post_state.get('powers', {})
            
            for power_name in pre_powers.keys():
                if power_name in post_powers:
                    pre_mag = pre_powers[power_name]['magnitude']
                    post_mag = post_powers[power_name]['magnitude']
                    change = abs(post_mag - pre_mag) / pre_mag if pre_mag > 0 else 0
                    power_changes.append(change)
            
            if power_changes:
                impact['power_impact'] = max(power_changes) * 100  # Percentage
            
            # System health impact
            pre_health = pre_state.get('system_health', {}).get('score', 100)
            post_health = post_state.get('system_health', {}).get('score', 100)
            impact['system_health_impact'] = max(0, pre_health - post_health)
            
            # Total impact score
            impact['total_impact_score'] = (
                impact['voltage_impact'] * 0.4 +
                impact['power_impact'] * 0.3 +
                impact['system_health_impact'] * 0.3
            )
            
        except Exception as e:
            logger.error(f"Error calculating impact: {e}")
            impact['error'] = str(e)
        
        return impact
    
    def execute_random_campaign(self, duration):
        """Execute random attack campaign for comparison"""
        campaign_result = {
            'type': 'random_campaign',
            'duration': duration,
            'start_time': datetime.now().isoformat(),
            'attacks': [],
            'total_impact': 0,
            'effectiveness_score': 0
        }
        
        try:
            start_time = time.time()
            attack_count = 0
            
            # Get initial grid state
            initial_state = self.federate.get_current_state()
            
            while (time.time() - start_time) < duration:
                # Random technique selection
                technique = random.choice(list(self.techniques.keys()))
                if technique == 'reconnaissance':
                    continue  # Skip reconnaissance in random mode
                
                # Generate random parameters
                params = self._generate_random_params(technique)
                
                # Execute attack
                result = self.execute_attack(technique, params)
                campaign_result['attacks'].append(result)
                
                attack_count += 1
                
                # Random delay between attacks
                time.sleep(random.uniform(1, 5))
            
            # Get final grid state and calculate overall impact
            final_state = self.federate.get_current_state()
            overall_impact = self._calculate_impact(initial_state, final_state)
            
            campaign_result.update({
                'end_time': datetime.now().isoformat(),
                'attack_count': attack_count,
                'final_grid_state': final_state,
                'overall_impact': overall_impact,
                'effectiveness_score': overall_impact.get('total_impact_score', 0)
            })
            
        except Exception as e:
            logger.error(f"Error in random campaign: {e}")
            campaign_result['error'] = str(e)
        
        return campaign_result
    
    def _generate_random_params(self, technique):
        """Generate random parameters for attack techniques"""
        if technique == 'spoof_data':
            return {
                'target': random.choice(['voltage_A', 'voltage_B', 'voltage_C', 'power_A', 'power_B', 'power_C']),
                'value': random.uniform(1000, 3000),  # Random voltage/power value
                'phase': random.uniform(0, 360)
            }
        elif technique == 'inject_load':
            return {
                'phase': random.choice(['A', 'B', 'C']),
                'magnitude': random.uniform(500000, 3000000),  # 0.5-3 MVA
                'power_factor': random.uniform(0.7, 0.95)
            }
        elif technique == 'block_command':
            return {
                'enable': random.choice([True, False]),
                'duration': random.uniform(5, 30)
            }
        elif technique == 'toggle_device':
            return {
                'device': random.choice(['switch1', 'breaker1', 'regulator1']),
                'state': random.choice(['open', 'closed'])
            }
        else:
            return {}
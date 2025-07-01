#!/usr/bin/env python3
"""
HELICS Federate for Grid Attack Injection and Monitoring
Interfaces with the 2bus-13bus co-simulation to inject attacks and monitor grid state
"""

import helics as h
import json
import logging
import time
import threading
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

class GridAttackFederate:
    """HELICS federate for injecting attacks and monitoring grid state"""
    
    def __init__(self, config):
        self.config = config
        self.federate = None
        self.federate_info = None
        
        # Publications (attack injections)
        self.publications = {}
        
        # Subscriptions (grid monitoring)
        self.subscriptions = {}
        
        # State tracking
        self.current_time = 0.0
        self.grid_state = {}
        self.attack_history = []
        
        # Synchronization
        self.state_lock = threading.Lock()
        
        logger.info("GridAttackFederate initialized")
    
    def initialize(self):
        """Initialize the HELICS federate"""
        try:
            logger.info("Initializing HELICS federate...")
            
            # Create federate info
            self.federate_info = h.helicsCreateFederateInfo()
            h.helicsFederateInfoSetBroker(self.federate_info, self.config['broker_address'])
            h.helicsFederateInfoSetTimeProperty(self.federate_info, h.HELICS_PROPERTY_TIME_DELTA, self.config['time_delta'])
            h.helicsFederateInfoSetTimeProperty(self.federate_info, h.HELICS_PROPERTY_TIME_PERIOD, self.config.get('period', 1.0))
            
            # Create combination federate (can publish and subscribe)
            self.federate = h.helicsCreateCombinationFederate(self.config['federate_name'], self.federate_info)
            
            # Setup publications for attack injection
            self._setup_publications()
            
            # Setup subscriptions for grid monitoring
            self._setup_subscriptions()
            
            # Enter execution mode
            h.helicsFederateEnterExecutingMode(self.federate)
            
            # Initialize grid state
            self._update_grid_state()
            
            logger.info("HELICS federate initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize HELICS federate: {e}")
            raise
    
    def _setup_publications(self):
        """Setup publications for attack injection"""
        try:
            # Voltage injection publications (to Node650 in GridLAB-D)
            self.publications['voltage_attack_Va'] = h.helicsFederateRegisterGlobalPublication(
                self.federate, "mcp_attack/Va", h.helics_data_type_complex, ""
            )
            self.publications['voltage_attack_Vb'] = h.helicsFederateRegisterGlobalPublication(
                self.federate, "mcp_attack/Vb", h.helics_data_type_complex, ""
            )
            self.publications['voltage_attack_Vc'] = h.helicsFederateRegisterGlobalPublication(
                self.federate, "mcp_attack/Vc", h.helics_data_type_complex, ""
            )
            
            # Power injection publications (to GridPACK load)
            self.publications['power_attack_Sa'] = h.helicsFederateRegisterGlobalPublication(
                self.federate, "mcp_attack/Sa", h.helics_data_type_complex, ""
            )
            self.publications['power_attack_Sb'] = h.helicsFederateRegisterGlobalPublication(
                self.federate, "mcp_attack/Sb", h.helics_data_type_complex, ""
            )
            self.publications['power_attack_Sc'] = h.helicsFederateRegisterGlobalPublication(
                self.federate, "mcp_attack/Sc", h.helics_data_type_complex, ""
            )
            
            # Control command blocking
            self.publications['block_commands'] = h.helicsFederateRegisterGlobalPublication(
                self.federate, "mcp_attack/block_commands", h.helics_data_type_boolean, ""
            )
            
            logger.info(f"Setup {len(self.publications)} attack publications")
            
        except Exception as e:
            logger.error(f"Failed to setup publications: {e}")
            raise
    
    def _setup_subscriptions(self):
        """Setup subscriptions for grid monitoring"""
        try:
            # Monitor GridLAB-D voltages at Node650 (swing bus)
            self.subscriptions['gld_voltage_Va'] = h.helicsFederateRegisterSubscription(
                self.federate, "IEEE13bus_fed/gld_hlc_conn/Va", ""
            )
            self.subscriptions['gld_voltage_Vb'] = h.helicsFederateRegisterSubscription(
                self.federate, "IEEE13bus_fed/gld_hlc_conn/Vb", ""
            )
            self.subscriptions['gld_voltage_Vc'] = h.helicsFederateRegisterSubscription(
                self.federate, "IEEE13bus_fed/gld_hlc_conn/Vc", ""
            )
            
            # Monitor GridLAB-D power flows at Node650
            self.subscriptions['gld_power_Sa'] = h.helicsFederateRegisterSubscription(
                self.federate, "IEEE13bus_fed/gld_hlc_conn/Sa", ""
            )
            self.subscriptions['gld_power_Sb'] = h.helicsFederateRegisterSubscription(
                self.federate, "IEEE13bus_fed/gld_hlc_conn/Sb", ""
            )
            self.subscriptions['gld_power_Sc'] = h.helicsFederateRegisterSubscription(
                self.federate, "IEEE13bus_fed/gld_hlc_conn/Sc", ""
            )
            
            # Monitor GridPACK voltages
            self.subscriptions['gpk_voltage_Va'] = h.helicsFederateRegisterSubscription(
                self.federate, "gridpack/Va", ""
            )
            self.subscriptions['gpk_voltage_Vb'] = h.helicsFederateRegisterSubscription(
                self.federate, "gridpack/Vb", ""
            )
            self.subscriptions['gpk_voltage_Vc'] = h.helicsFederateRegisterSubscription(
                self.federate, "gridpack/Vc", ""
            )
            
            logger.info(f"Setup {len(self.subscriptions)} monitoring subscriptions")
            
        except Exception as e:
            logger.error(f"Failed to setup subscriptions: {e}")
            raise
    
    def _update_grid_state(self):
        """Update grid state from subscriptions"""
        try:
            with self.state_lock:
                # Update current simulation time
                self.current_time = h.helicsFederateGetCurrentTime(self.federate)
                
                # Read all subscriptions
                grid_data = {
                    'timestamp': self.current_time,
                    'voltages': {},
                    'powers': {},
                    'system_health': 'unknown'
                }
                
                # Read GridLAB-D data
                for name, sub in self.subscriptions.items():
                    try:
                        if h.helicsInputIsUpdated(sub):
                            if 'voltage' in name:
                                complex_val = h.helicsInputGetComplex(sub)
                                grid_data['voltages'][name] = {
                                    'real': complex_val.real,
                                    'imag': complex_val.imag,
                                    'magnitude': abs(complex_val),
                                    'angle': np.angle(complex_val, deg=True)
                                }
                            elif 'power' in name:
                                complex_val = h.helicsInputGetComplex(sub)
                                grid_data['powers'][name] = {
                                    'real': complex_val.real,
                                    'imag': complex_val.imag,
                                    'magnitude': abs(complex_val),
                                    'power_factor': complex_val.real / abs(complex_val) if abs(complex_val) > 0 else 0
                                }
                    except Exception as e:
                        logger.warning(f"Error reading subscription {name}: {e}")
                
                # Calculate system health indicators
                grid_data['system_health'] = self._assess_system_health(grid_data)
                
                self.grid_state = grid_data
                
        except Exception as e:
            logger.error(f"Error updating grid state: {e}")
    
    def _assess_system_health(self, grid_data):
        """Assess overall system health based on grid data"""
        try:
            health_score = 100
            issues = []
            
            # Check voltage levels
            for voltage_name, voltage_data in grid_data['voltages'].items():
                magnitude = voltage_data['magnitude']
                
                # Convert to per-unit (assuming 2401.78V base for GridLAB-D)
                if 'gld' in voltage_name:
                    pu_voltage = magnitude / 2401.78
                elif 'gpk' in voltage_name:
                    pu_voltage = magnitude / 2401.78
                else:
                    continue
                
                # Check voltage limits
                if pu_voltage < 0.95:
                    health_score -= 20
                    issues.append(f"Undervoltage: {voltage_name} = {pu_voltage:.3f} pu")
                elif pu_voltage > 1.05:
                    health_score -= 15
                    issues.append(f"Overvoltage: {voltage_name} = {pu_voltage:.3f} pu")
            
            # Check power flows
            total_power = 0
            for power_name, power_data in grid_data['powers'].items():
                total_power += power_data['magnitude']
            
            # Determine health status
            if health_score >= 90:
                status = 'healthy'
            elif health_score >= 70:
                status = 'degraded'
            elif health_score >= 50:
                status = 'compromised'
            else:
                status = 'critical'
            
            return {
                'status': status,
                'score': health_score,
                'issues': issues,
                'total_power_mva': total_power / 1e6
            }
            
        except Exception as e:
            logger.error(f"Error assessing system health: {e}")
            return {'status': 'unknown', 'score': 0, 'issues': [str(e)]}
    
    def inject_voltage_attack(self, phase, voltage_complex):
        """Inject malicious voltage data"""
        try:
            phase_map = {'A': 'Va', 'B': 'Vb', 'C': 'Vc'}
            if phase in phase_map:
                pub_name = f'voltage_attack_{phase_map[phase]}'
                if pub_name in self.publications:
                    h.helicsPublicationPublishComplex(
                        self.publications[pub_name], 
                        complex(voltage_complex['real'], voltage_complex['imag'])
                    )
                    
                    # Record attack
                    attack_record = {
                        'timestamp': self.current_time,
                        'type': 'voltage_spoof',
                        'target': f'voltage_{phase}',
                        'value': voltage_complex,
                        'technique': 'spoof_data'
                    }
                    self.attack_history.append(attack_record)
                    
                    logger.info(f"Injected voltage attack on phase {phase}: {voltage_complex}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error injecting voltage attack: {e}")
            return False
    
    def inject_power_attack(self, phase, power_complex):
        """Inject malicious power data"""
        try:
            phase_map = {'A': 'Sa', 'B': 'Sb', 'C': 'Sc'}
            if phase in phase_map:
                pub_name = f'power_attack_{phase_map[phase]}'
                if pub_name in self.publications:
                    h.helicsPublicationPublishComplex(
                        self.publications[pub_name], 
                        complex(power_complex['real'], power_complex['imag'])
                    )
                    
                    # Record attack
                    attack_record = {
                        'timestamp': self.current_time,
                        'type': 'power_injection',
                        'target': f'power_{phase}',
                        'value': power_complex,
                        'technique': 'inject_load'
                    }
                    self.attack_history.append(attack_record)
                    
                    logger.info(f"Injected power attack on phase {phase}: {power_complex}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error injecting power attack: {e}")
            return False
    
    def block_commands(self, enable=True):
        """Block control commands"""
        try:
            if 'block_commands' in self.publications:
                h.helicsPublicationPublishBoolean(
                    self.publications['block_commands'], 
                    enable
                )
                
                # Record attack
                attack_record = {
                    'timestamp': self.current_time,
                    'type': 'command_blocking',
                    'target': 'control_system',
                    'value': enable,
                    'technique': 'block_command'
                }
                self.attack_history.append(attack_record)
                
                logger.info(f"Command blocking {'enabled' if enable else 'disabled'}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error blocking commands: {e}")
            return False
    
    def advance_time(self, time_step=None):
        """Advance simulation time"""
        try:
            if time_step is None:
                time_step = self.config['time_delta']
            
            next_time = self.current_time + time_step
            granted_time = h.helicsFederateRequestTime(self.federate, next_time)
            
            # Update grid state after time advance
            self._update_grid_state()
            
            return granted_time
            
        except Exception as e:
            logger.error(f"Error advancing time: {e}")
            return self.current_time
    
    def get_current_state(self):
        """Get current grid state"""
        with self.state_lock:
            return self.grid_state.copy()
    
    def get_attack_history(self):
        """Get attack history"""
        return self.attack_history.copy()
    
    def reset_grid_state(self):
        """Reset grid state for new simulation"""
        try:
            # Clear attack history
            self.attack_history.clear()
            
            # Reset any ongoing attacks
            self.block_commands(False)
            
            logger.info("Grid state reset")
            
        except Exception as e:
            logger.error(f"Error resetting grid state: {e}")
    
    def get_status(self):
        """Get federate status"""
        try:
            return {
                'name': self.config['federate_name'],
                'current_time': self.current_time,
                'publications': len(self.publications),
                'subscriptions': len(self.subscriptions),
                'attack_count': len(self.attack_history),
                'is_initialized': self.federate is not None
            }
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {'error': str(e)}
    
    def finalize(self):
        """Finalize the federate"""
        try:
            if self.federate:
                h.helicsFederateFinalize(self.federate)
                h.helicsFederateFree(self.federate)
                self.federate = None
            
            if self.federate_info:
                h.helicsFederateInfoFree(self.federate_info)
                self.federate_info = None
            
            logger.info("HELICS federate finalized")
            
        except Exception as e:
            logger.error(f"Error finalizing federate: {e}")
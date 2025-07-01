#!/usr/bin/env python3
"""
Threat Model Validator - Ensures attacks comply with research safety constraints
"""

import logging
import os
import yaml

logger = logging.getLogger(__name__)

class ThreatModelValidator:
    """Validates attacks against threat model constraints"""
    
    def __init__(self, config_path='config/threat_model.yaml'):
        self.config_path = config_path
        self.constraints = self._load_constraints()
        logger.info("Threat model validator initialized")
    
    def _load_constraints(self):
        """Load threat model constraints"""
        default_constraints = {
            'voltage_limits': {
                'min': 0.7,  # 70% of nominal
                'max': 1.3   # 130% of nominal
            },
            'power_limits': {
                'max_injection': 5000000  # 5 MVA
            },
            'timing_limits': {
                'min_interval': 1.0,  # seconds between attacks
                'max_duration': 300   # maximum attack duration
            },
            'allowed_techniques': [
                'spoof_data',
                'inject_load',
                'reconnaissance',
                'block_command'
            ],
            'restricted_targets': [
                'safety_systems',
                'emergency_controls'
            ],
            'simulation_safety': {
                'max_voltage_deviation': 0.5,  # max 50% deviation
                'max_power_injection_ratio': 2.0,  # max 200% of baseline
                'prevent_permanent_damage': True
            }
        }
        
        # Try to load from file
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    file_constraints = yaml.safe_load(f)
                    # Merge with defaults
                    for section, values in file_constraints.items():
                        if section in default_constraints:
                            default_constraints[section].update(values)
                        else:
                            default_constraints[section] = values
        except Exception as e:
            logger.warning(f"Could not load threat model config {self.config_path}: {e}, using defaults")
        
        return default_constraints
    
    def validate_attack(self, technique, params):
        """Validate an attack against threat model"""
        validation_result = {
            'valid': True,
            'reason': '',
            'warnings': [],
            'modifications': {}
        }
        
        try:
            # Check if technique is allowed
            allowed_techniques = self.constraints.get('allowed_techniques', [])
            if technique not in allowed_techniques:
                validation_result['valid'] = False
                validation_result['reason'] = f'Technique {technique} not in allowed list: {allowed_techniques}'
                return validation_result
            
            # Validate technique-specific parameters
            if technique == 'spoof_data':
                validation_result = self._validate_spoof_data(params, validation_result)
            elif technique == 'inject_load':
                validation_result = self._validate_inject_load(params, validation_result)
            elif technique == 'block_command':
                validation_result = self._validate_block_command(params, validation_result)
            elif technique == 'reconnaissance':
                # Reconnaissance is generally safe
                pass
            
        except Exception as e:
            logger.error(f"Error validating attack: {e}")
            validation_result['valid'] = False
            validation_result['reason'] = f'Validation error: {str(e)}'
        
        return validation_result
    
    def _validate_spoof_data(self, params, validation_result):
        """Validate data spoofing attack"""
        target = params.get('target', '')
        value = params.get('value', 0)
        
        if 'voltage' in target:
            # Validate voltage limits
            voltage_limits = self.constraints.get('voltage_limits', {})
            min_voltage = voltage_limits.get('min', 0.7) * 2401.78  # Convert to actual voltage
            max_voltage = voltage_limits.get('max', 1.3) * 2401.78
            
            if value < min_voltage:
                if self.constraints.get('simulation_safety', {}).get('prevent_permanent_damage', True):
                    validation_result['modifications']['value'] = min_voltage
                    validation_result['warnings'].append(f'Voltage clamped to minimum safe value: {min_voltage}V')
                else:
                    validation_result['valid'] = False
                    validation_result['reason'] = f'Voltage {value}V below minimum safe limit {min_voltage}V'
            
            elif value > max_voltage:
                if self.constraints.get('simulation_safety', {}).get('prevent_permanent_damage', True):
                    validation_result['modifications']['value'] = max_voltage
                    validation_result['warnings'].append(f'Voltage clamped to maximum safe value: {max_voltage}V')
                else:
                    validation_result['valid'] = False
                    validation_result['reason'] = f'Voltage {value}V above maximum safe limit {max_voltage}V'
        
        elif 'power' in target:
            # Validate power limits
            power_limits = self.constraints.get('power_limits', {})
            max_power = power_limits.get('max_injection', 5000000)
            
            if abs(value) > max_power:
                if self.constraints.get('simulation_safety', {}).get('prevent_permanent_damage', True):
                    validation_result['modifications']['value'] = max_power if value > 0 else -max_power
                    validation_result['warnings'].append(f'Power clamped to maximum safe value: ±{max_power}VA')
                else:
                    validation_result['valid'] = False
                    validation_result['reason'] = f'Power injection {value}VA exceeds limit {max_power}VA'
        
        return validation_result
    
    def _validate_inject_load(self, params, validation_result):
        """Validate load injection attack"""
        magnitude = params.get('magnitude', 0)
        
        power_limits = self.constraints.get('power_limits', {})
        max_injection = power_limits.get('max_injection', 5000000)
        
        if magnitude > max_injection:
            if self.constraints.get('simulation_safety', {}).get('prevent_permanent_damage', True):
                validation_result['modifications']['magnitude'] = max_injection
                validation_result['warnings'].append(f'Load injection clamped to maximum safe value: {max_injection}VA')
            else:
                validation_result['valid'] = False
                validation_result['reason'] = f'Load injection {magnitude}VA exceeds limit {max_injection}VA'
        
        return validation_result
    
    def _validate_block_command(self, params, validation_result):
        """Validate command blocking attack"""
        duration = params.get('duration', 0)
        
        timing_limits = self.constraints.get('timing_limits', {})
        max_duration = timing_limits.get('max_duration', 300)
        
        if duration > max_duration:
            if self.constraints.get('simulation_safety', {}).get('prevent_permanent_damage', True):
                validation_result['modifications']['duration'] = max_duration
                validation_result['warnings'].append(f'Block duration clamped to maximum safe value: {max_duration}s')
            else:
                validation_result['valid'] = False
                validation_result['reason'] = f'Block duration {duration}s exceeds limit {max_duration}s'
        
        return validation_result
    
    def get_constraints(self):
        """Get current threat model constraints"""
        return self.constraints.copy()
    
    def update_constraints(self, new_constraints):
        """Update threat model constraints"""
        self.constraints.update(new_constraints)
        logger.info("Threat model constraints updated")
    
    def save_constraints(self):
        """Save current constraints to file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                yaml.dump(self.constraints, f, default_flow_style=False)
            logger.info(f"Threat model constraints saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving constraints: {e}")
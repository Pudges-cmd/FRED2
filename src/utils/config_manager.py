# src/utils/config_manager.py
"""
Configuration management utilities
"""

import json
import logging
import os
from pathlib import Path

class ConfigManager:
    def __init__(self, config_path='/opt/disaster-detection/config/settings.json'):
        """
        Initialize configuration manager
        
        Args:
            config_path (str): Path to configuration file
        """
        self.config_path = Path(config_path)
        self.config = {}
        self.logger = logging.getLogger(__name__)
        
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
                self.logger.info(f"Configuration loaded from {self.config_path}")
            else:
                self.logger.warning(f"Configuration file not found: {self.config_path}")
                self.config = self.get_default_config()
                
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            self.config = self.get_default_config()
    
    def get_default_config(self):
        """Get default configuration"""
        return {
            "detection": {
                "confidence_threshold": 0.5,
                "detection_interval": 2.0,
                "camera_resolution": [640, 480],
                "target_classes": ["person", "cat", "dog"],
                "model_path": "/opt/disaster-detection/models/yolov5n.pt"
            },
            "communication": {
                "emergency_contacts": [],
                "sms_cooldown": 300,
                "gps_timeout": 30,
                "serial_port": "/dev/ttyUSB2",
                "serial_baudrate": 115200
            },
            "evacuation_sites": {
                "primary": {
                    "name": "Emergency Shelter",
                    "address": "Please configure evacuation site",
                    "coordinates": [0.0, 0.0]
                }
            },
            "logging": {
                "log_level": "INFO",
                "log_file": "/var/log/disaster-detection/system.log",
                "detection_log": "/opt/disaster-detection/logs/detections.txt",
                "max_log_size": "10MB",
                "backup_count": 5
            },
            "firebase": {
                "enabled": False,
                "project_id": "",
                "collection": "detections"
            },
            "system": {
                "auto_restart": True,
                "max_restart_attempts": 5,
                "health_check_interval": 60
            }
        }
    
    def get(self, key, default=None):
        """
        Get configuration value
        
        Args:
            key (str): Configuration key (supports dot notation)
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        try:
            keys = key.split('.')
            value = self.config
            
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            
            return value
            
        except Exception:
            return default
    
    def set(self, key, value):
        """
        Set configuration value
        
        Args:
            key (str): Configuration key (supports dot notation)
            value: Value to set
        """
        try:
            keys = key.split('.')
            config = self.config
            
            # Navigate to parent dictionary
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            # Set the value
            config[keys[-1]] = value
            
        except Exception as e:
            self.logger.error(f"Failed to set config {key}: {e}")
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            # Create directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write configuration
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            self.logger.info(f"Configuration saved to {self.config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            return False
    
    def reload_config(self):
        """Reload configuration from file"""
        self.load_config()
    
    def validate_config(self):
        """
        Validate configuration
        
        Returns:
            dict: Validation results
        """
        validation = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Check required sections
            required_sections = ['detection', 'communication', 'logging']
            for section in required_sections:
                if section not in self.config:
                    validation['errors'].append(f"Missing required section: {section}")
                    validation['valid'] = False
            
            # Validate detection settings
            detection = self.config.get('detection', {})
            confidence = detection.get('confidence_threshold', 0.5)
            if not (0.1 <= confidence <= 1.0):
                validation['errors'].append("Confidence threshold must be between 0.1 and 1.0")
                validation['valid'] = False
            
            interval = detection.get('detection_interval', 2.0)
            if not (0.5 <= interval <= 60.0):
                validation['warnings'].append("Detection interval should be between 0.5 and 60 seconds")
            
            # Validate communication settings
            comm = self.config.get('communication', {})
            contacts = comm.get('emergency_contacts', [])
            if not contacts:
                validation['warnings'].append("No emergency contacts configured")
            
            cooldown = comm.get('sms_cooldown', 300)
            if cooldown < 60:
                validation['warnings'].append("SMS cooldown less than 60 seconds may cause spam")
            
            # Validate logging settings
            logging_config = self.config.get('logging', {})
            log_level = logging_config.get('log_level', 'INFO')
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if log_level.upper() not in valid_levels:
                validation['errors'].append(f"Invalid log level: {log_level}")
                validation['valid'] = False
            
        except Exception as e:
            validation['errors'].append(f"Configuration validation error: {e}")
            validation['valid'] = False
        
        return validation
    
    def get_config_info(self):
        """Get configuration information"""
        return {
            'config_path': str(self.config_path),
            'config_exists': self.config_path.exists(),
            'config_size': len(json.dumps(self.config)),
            'sections': list(self.config.keys()),
            'validation': self.validate_config()
        }
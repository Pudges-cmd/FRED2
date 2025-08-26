"""
GPS coordinate retrieval using SIM7600X 4G Hat
Handles GPS initialization, coordinate parsing, and error handling
"""

import serial
import time
import re
import logging
import threading
from datetime import datetime

class GPSHandler:
    def __init__(self, port='/dev/ttyUSB2', baudrate=115200, timeout=30):
        """
        Initialize GPS handler
        
        Args:
            port (str): Serial port for SIM7600X
            baudrate (int): Serial communication baudrate
            timeout (int): GPS fix timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        
        self.serial_conn = None
        self.last_coordinates = None
        self.gps_enabled = False
        self.fix_status = "No Fix"
        
        # GPS data cache
        self.gps_cache = {
            'coordinates': None,
            'timestamp': None,
            'satellites': 0,
            'hdop': 0.0,
            'altitude': 0.0,
            'speed': 0.0,
            'course': 0.0
        }
        
        self.cache_lock = threading.Lock()
        
    def connect(self):
        """Connect to GPS module"""
        try:
            if self.serial_conn and self.serial_conn.is_open:
                return True
                
            self.logger.info(f"Connecting to GPS on {self.port}")
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=10,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            time.sleep(2)  # Allow connection to stabilize
            
            # Test connection with basic AT command
            if self.send_at_command("AT"):
                self.logger.info("GPS module connected successfully")
                return True
            else:
                self.logger.error("GPS module not responding")
                return False
                
        except Exception as e:
            self.logger.error(f"GPS connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from GPS module"""
        try:
            if self.gps_enabled:
                self.disable_gps()
                
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
                self.serial_conn = None
                self.logger.info("GPS disconnected")
                
        except Exception as e:
            self.logger.error(f"GPS disconnect error: {e}")
    
    def send_at_command(self, command, wait_for_response=True, timeout=10):
        """
        Send AT command to module
        
        Args:
            command (str): AT command to send
            wait_for_response (bool): Wait for response
            timeout (int): Response timeout
            
        Returns:
            str: Response string or None
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            return None
            
        try:
            # Clear input buffer
            self.serial_conn.flushInput()
            
            # Send command
            cmd = f"{command}\r\n"
            self.serial_conn.write(cmd.encode())
            
            if not wait_for_response:
                return True
                
            # Wait for response
            start_time = time.time()
            response_lines = []
            
            while time.time() - start_time < timeout:
                if self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode().strip()
                    if line:
                        response_lines.append(line)
                        
                        # Check for completion
                        if "OK" in line or "ERROR" in line:
                            break
                            
                time.sleep(0.1)
            
            response = "\n".join(response_lines)
            self.logger.debug(f"AT Command: {command} -> {response}")
            
            return response if "OK" in response else None
            
        except Exception as e:
            self.logger.error(f"AT command error ({command}): {e}")
            return None
    
    def enable_gps(self):
        """Enable GPS functionality"""
        try:
            if not self.connect():
                return False
            
            self.logger.info("Enabling GPS...")
            
            # Power on GPS
            response = self.send_at_command("AT+CGPS=1", timeout=15)
            if response and "OK" in response:
                self.gps_enabled = True
                self.logger.info("GPS enabled successfully")
                
                # Wait for GPS to initialize
                time.sleep(3)
                return True
            else:
                self.logger.error("Failed to enable GPS")
                return False
                
        except Exception as e:
            self.logger.error(f"GPS enable error: {e}")
            return False
    
    def disable_gps(self):
        """Disable GPS functionality"""
        try:
            if not self.serial_conn:
                return
                
            self.logger.info("Disabling GPS...")
            self.send_at_command("AT+CGPS=0", timeout=10)
            self.gps_enabled = False
            
        except Exception as e:
            self.logger.error(f"GPS disable error: {e}")
    
    def get_coordinates(self, max_attempts=3):
        """
        Get current GPS coordinates
        
        Args:
            max_attempts (int): Maximum number of attempts
            
        Returns:
            dict: GPS coordinates or None
        """
        if not self.gps_enabled:
            if not self.enable_gps():
                return None
        
        for attempt in range(max_attempts):
            try:
                self.logger.info(f"GPS fix attempt {attempt + 1}/{max_attempts}")
                
                # Request GPS information
                response = self.send_at_command("AT+CGPSINFO", timeout=10)
                
                if response and "+CGPSINFO:" in response:
                    coords = self.parse_gps_response(response)
                    if coords:
                        self.update_cache(coords)
                        self.last_coordinates = coords
                        self.fix_status = "3D Fix"
                        return coords
                
                # Try alternative command
                response = self.send_at_command("AT+CGPSINF=0", timeout=10)
                if response:
                    coords = self.parse_alternative_gps_response(response)
                    if coords:
                        self.update_cache(coords)
                        self.last_coordinates = coords
                        return coords
                
                # Wait before retry
                if attempt < max_attempts - 1:
                    self.logger.info(f"GPS fix failed, retrying in 5 seconds...")
                    time.sleep(5)
                    
            except Exception as e:
                self.logger.error(f"GPS coordinate retrieval error: {e}")
        
        self.fix_status = "No Fix"
        self.logger.warning("GPS coordinate retrieval failed after all attempts")
        
        # Return cached coordinates if available and recent
        if self.last_coordinates:
            cache_age = time.time() - self.gps_cache.get('timestamp', 0)
            if cache_age < 300:  # Use cache if less than 5 minutes old
                self.logger.info("Using cached GPS coordinates")
                return self.last_coordinates
        
        return None
    
    def parse_gps_response(self, response):
        """
        Parse GPS response string
        
        Args:
            response (str): GPS response from module
            
        Returns:
            dict: Parsed coordinates or None
        """
        try:
            # Find CGPSINFO line
            for line in response.split('\n'):
                if '+CGPSINFO:' in line:
                    # Extract GPS data part
                    gps_data = line.split(':')[1].strip()
                    
                    # Split by comma: lat,lat_dir,lon,lon_dir,date,time,alt,speed,course
                    parts = gps_data.split(',')
                    
                    if len(parts) >= 4 and parts[0] and parts[2]:
                        # Parse latitude
                        lat_str = parts[0]
                        lat_dir = parts[1]
                        
                        # Parse longitude  
                        lon_str = parts[2]
                        lon_dir = parts[3]
                        
                        # Convert to decimal degrees
                        lat = self.parse_coordinate(lat_str, lat_dir, is_longitude=False)
                        lon = self.parse_coordinate(lon_str, lon_dir, is_longitude=True)
                        
                        if lat is not None and lon is not None:
                            coords = {
                                'lat': lat,
                                'lon': lon,
                                'timestamp': datetime.now().isoformat()
                            }
                            
                            # Add additional data if available
                            if len(parts) > 6 and parts[6]:
                                coords['altitude'] = float(parts[6])
                            if len(parts) > 7 and parts[7]:
                                coords['speed'] = float(parts[7])
                            if len(parts) > 8 and parts[8]:
                                coords['course'] = float(parts[8])
                            
                            return coords
            
        except Exception as e:
            self.logger.error(f"GPS parsing error: {e}")
        
        return None
    
    def parse_alternative_gps_response(self, response):
        """Parse alternative GPS response format"""
        try:
            # Alternative parsing for different response formats
            lines = response.split('\n')
            for line in lines:
                if 'CGPSINF' in line or any(char.isdigit() for char in line):
                    # Try to extract coordinates from different formats
                    # This is a fallback parser for various response formats
                    coords_match = re.search(r'(\d+\.\d+),([NS]),(\d+\.\d+),([EW])', line)
                    if coords_match:
                        lat_val, lat_dir, lon_val, lon_dir = coords_match.groups()
                        
                        lat = float(lat_val)
                        lon = float(lon_val)
                        
                        if lat_dir == 'S':
                            lat = -lat
                        if lon_dir == 'W':
                            lon = -lon
                        
                        return {
                            'lat': lat,
                            'lon': lon,
                            'timestamp': datetime.now().isoformat()
                        }
        
        except Exception as e:
            self.logger.error(f"Alternative GPS parsing error: {e}")
        
        return None
    
    def parse_coordinate(self, coord_str, direction, is_longitude=False):
        """
        Parse coordinate string to decimal degrees
        
        Args:
            coord_str (str): Coordinate string (DDMM.MMMMM format)
            direction (str): Direction (N/S for lat, E/W for lon)
            is_longitude (bool): True if parsing longitude
            
        Returns:
            float: Decimal degrees or None
        """
        try:
            if not coord_str or len(coord_str) < 5:
                return None
            
            # Handle different coordinate formats
            if is_longitude:
                # Longitude: DDDMM.MMMMM (3 digits for degrees)
                if len(coord_str) >= 8:
                    degrees = float(coord_str[:3])
                    minutes = float(coord_str[3:])
                else:
                    return None
            else:
                # Latitude: DDMM.MMMMM (2 digits for degrees)
                if len(coord_str) >= 7:
                    degrees = float(coord_str[:2])
                    minutes = float(coord_str[2:])
                else:
                    return None
            
            # Convert to decimal degrees
            decimal_degrees = degrees + (minutes / 60.0)
            
            # Apply direction
            if direction in ['S', 'W']:
                decimal_degrees = -decimal_degrees
            
            return decimal_degrees
            
        except Exception as e:
            self.logger.error(f"Coordinate parsing error: {e}")
            return None
    
    def update_cache(self, coordinates):
        """Update GPS cache with new data"""
        with self.cache_lock:
            self.gps_cache.update({
                'coordinates': coordinates,
                'timestamp': time.time()
            })
    
    def get_gps_status(self):
        """
        Get GPS module status
        
        Returns:
            dict: GPS status information
        """
        status = {
            'connected': self.serial_conn is not None and self.serial_conn.is_open,
            'gps_enabled': self.gps_enabled,
            'fix_status': self.fix_status,
            'last_coordinates': self.last_coordinates,
            'cache_age': None
        }
        
        if self.gps_cache['timestamp']:
            status['cache_age'] = time.time() - self.gps_cache['timestamp']
        
        # Get additional status from module
        try:
            if status['connected']:
                # Check GPS power status
                response = self.send_at_command("AT+CGPS?", timeout=5)
                if response:
                    status['power_response'] = response
                
                # Check signal quality
                response = self.send_at_command("AT+CSQ", timeout=5)
                if response and "+CSQ:" in response:
                    status['signal_quality'] = response.split(':')[1].strip()
                    
        except Exception as e:
            self.logger.debug(f"Status check error: {e}")
        
        return status
    
    def test_connection(self):
        """Test GPS module connection"""
        try:
            if not self.connect():
                return False
            
            response = self.send_at_command("AT", timeout=5)
            return response is not None and "OK" in response
            
        except Exception as e:
            self.logger.error(f"GPS connection test failed: {e}")
            return False
    
    def get_satellite_info(self):
        """Get satellite information"""
        try:
            response = self.send_at_command("AT+CGPSSAT", timeout=10)
            if response:
                # Parse satellite information
                satellites = []
                for line in response.split('\n'):
                    if line.startswith('+CGPSSAT:'):
                        # Parse satellite data
                        sat_data = line.split(':')[1].strip()
                        satellites.append(sat_data)
                
                return satellites
                
        except Exception as e:
            self.logger.error(f"Satellite info error: {e}")
        
        return []
    
    def cleanup(self):
        """Cleanup GPS resources"""
        self.logger.info("Cleaning up GPS resources...")
        try:
            self.disable_gps()
            self.disconnect()
        except Exception as e:
            self.logger.error(f"GPS cleanup error: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()
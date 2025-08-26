"""
SMS sending functionality using SIM7600X 4G Hat
Handles SMS initialization, sending, and delivery confirmation
"""

import serial
import time
import logging
import re
from datetime import datetime

class SMSHandler:
    def __init__(self, port='/dev/ttyUSB2', baudrate=115200):
        """
        Initialize SMS handler
        
        Args:
            port (str): Serial port for SIM7600X
            baudrate (int): Serial communication baudrate
        """
        self.port = port
        self.baudrate = baudrate
        self.logger = logging.getLogger(__name__)
        
        self.serial_conn = None
        self.sms_initialized = False
        self.network_registered = False
        
        # SMS statistics
        self.sms_stats = {
            'sent': 0,
            'failed': 0,
            'last_send_time': None,
            'last_error': None
        }
    
    def connect(self):
        """Connect to SMS module"""
        try:
            if self.serial_conn and self.serial_conn.is_open:
                return True
                
            self.logger.info(f"Connecting to SMS module on {self.port}")
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=10,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            time.sleep(2)  # Allow connection to stabilize
            
            # Test connection
            if self.send_at_command("AT"):
                self.logger.info("SMS module connected successfully")
                return True
            else:
                self.logger.error("SMS module not responding")
                return False
                
        except Exception as e:
            self.logger.error(f"SMS connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from SMS module"""
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
                self.serial_conn = None
                self.logger.info("SMS module disconnected")
                
        except Exception as e:
            self.logger.error(f"SMS disconnect error: {e}")
    
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
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        response_lines.append(line)
                        
                        # Check for completion
                        if "OK" in line or "ERROR" in line or "+CMGS:" in line:
                            break
                            
                time.sleep(0.1)
            
            response = "\n".join(response_lines)
            self.logger.debug(f"AT Command: {command} -> {response}")
            
            return response
            
        except Exception as e:
            self.logger.error(f"AT command error ({command}): {e}")
            return None
    
    def initialize_sms(self):
        """Initialize SMS functionality"""
        try:
            if not self.connect():
                return False
            
            self.logger.info("Initializing SMS...")
            
            # Check network registration
            if not self.check_network_registration():
                self.logger.error("Network not registered")
                return False
            
            # Set SMS text mode
            response = self.send_at_command("AT+CMGF=1", timeout=10)
            if not response or "OK" not in response:
                self.logger.error("Failed to set SMS text mode")
                return False
            
            # Set character set
            self.send_at_command("AT+CSCS=\"GSM\"", timeout=10)
            
            # Enable SMS notifications
            self.send_at_command("AT+CNMI=1,2,0,0,0", timeout=10)
            
            # Set preferred storage
            self.send_at_command("AT+CPMS=\"SM\",\"SM\",\"SM\"", timeout=10)
            
            self.sms_initialized = True
            self.logger.info("SMS initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"SMS initialization error: {e}")
            return False
    
    def check_network_registration(self, max_attempts=5):
        """
        Check network registration status
        
        Args:
            max_attempts (int): Maximum number of attempts
            
        Returns:
            bool: True if registered
        """
        for attempt in range(max_attempts):
            try:
                response = self.send_at_command("AT+CREG?", timeout=10)
                if response:
                    # Parse registration status
                    # +CREG: n,stat where stat: 0=not searching, 1=registered home, 2=searching, 5=registered roaming
                    match = re.search(r'\+CREG:\s*\d+,(\d+)', response)
                    if match:
                        status = int(match.group(1))
                        if status in [1, 5]:  # Registered (home or roaming)
                            self.network_registered = True
                            self.logger.info(f"Network registered (status: {status})")
                            return True
                        elif status == 2:  # Searching
                            self.logger.info(f"Network searching... (attempt {attempt + 1})")
                        else:
                            self.logger.warning(f"Network not registered (status: {status})")
                
                # Check signal strength
                signal_response = self.send_at_command("AT+CSQ", timeout=5)
                if signal_response:
                    self.logger.info(f"Signal status: {signal_response}")
                
                if attempt < max_attempts - 1:
                    time.sleep(5)
                    
            except Exception as e:
                self.logger.error(f"Network check error: {e}")
        
        self.network_registered = False
        return False
    
    def send_message(self, phone_number, message, max_attempts=3):
        """
        Send SMS message
        
        Args:
            phone_number (str): Recipient phone number
            message (str): Message content
            max_attempts (int): Maximum send attempts
            
        Returns:
            bool: True if sent successfully
        """
        if not self.sms_initialized:
            if not self.initialize_sms():
                return False
        
        # Validate phone number
        if not self.validate_phone_number(phone_number):
            self.logger.error(f"Invalid phone number: {phone_number}")
            return False
        
        # Split long messages
        message_parts = self.split_message(message)
        
        for part_num, message_part in enumerate(message_parts, 1):
            success = self._send_single_message(phone_number, message_part, max_attempts, part_num, len(message_parts))
            if not success:
                return False
        
        return True
    
    def _send_single_message(self, phone_number, message, max_attempts, part_num=1, total_parts=1):
        """
        Send a single SMS message
        
        Args:
            phone_number (str): Recipient phone number
            message (str): Message content
            max_attempts (int): Maximum send attempts
            part_num (int): Current message part number
            total_parts (int): Total number of message parts
            
        Returns:
            bool: True if sent successfully
        """
        for attempt in range(max_attempts):
            try:
                self.logger.info(f"Sending SMS to {phone_number} (part {part_num}/{total_parts}, attempt {attempt + 1})")
                
                # Prepare message header if multipart
                if total_parts > 1:
                    message_with_header = f"[{part_num}/{total_parts}] {message}"
                else:
                    message_with_header = message
                
                # Set recipient
                cmd = f'AT+CMGS="{phone_number}"'
                response = self.send_at_command(cmd, timeout=10)
                
                if not response or ">" not in response:
                    self.logger.error(f"Failed to set SMS recipient: {response}")
                    if attempt < max_attempts - 1:
                        time.sleep(2)
                        continue
                    else:
                        self.sms_stats['failed'] += 1
                        self.sms_stats['last_error'] = "Failed to set recipient"
                        return False
                
                # Send message content
                try:
                    self.serial_conn.write(message_with_header.encode('utf-8', errors='ignore'))
                    self.serial_conn.write(b'\x1A')  # Ctrl+Z to send
                    
                    # Wait for send confirmation
                    start_time = time.time()
                    while time.time() - start_time < 30:  # 30 second timeout
                        if self.serial_conn.in_waiting > 0:
                            response_line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                            
                            if "+CMGS:" in response_line:
                                # Extract message reference
                                match = re.search(r'\+CMGS:\s*(\d+)', response_line)
                                msg_ref = match.group(1) if match else "unknown"
                                
                                self.logger.info(f"SMS sent successfully to {phone_number} (ref: {msg_ref})")
                                self.sms_stats['sent'] += 1
                                self.sms_stats['last_send_time'] = datetime.now()
                                return True
                                
                            elif "ERROR" in response_line:
                                self.logger.error(f"SMS send error: {response_line}")
                                break
                        
                        time.sleep(0.2)
                    
                    self.logger.error("SMS send timeout - no confirmation received")
                    
                except Exception as e:
                    self.logger.error(f"SMS send exception: {e}")
                
                # Wait before retry
                if attempt < max_attempts - 1:
                    self.logger.info(f"Retrying SMS send in 5 seconds...")
                    time.sleep(5)
                    
                    # Try to recover connection
                    self.send_at_command("AT", timeout=5)
                    
            except Exception as e:
                self.logger.error(f"SMS send attempt {attempt + 1} failed: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(5)
        
        self.sms_stats['failed'] += 1
        self.sms_stats['last_error'] = "All send attempts failed"
        return False
    
    def validate_phone_number(self, phone_number):
        """
        Validate phone number format
        
        Args:
            phone_number (str): Phone number to validate
            
        Returns:
            bool: True if valid
        """
        try:
            # Remove spaces and special characters
            cleaned = re.sub(r'[^\d+]', '', phone_number)
            
            # Check basic format
            if not cleaned:
                return False
            
            # Must start with + or digit
            if not (cleaned.startswith('+') or cleaned[0].isdigit()):
                return False
            
            # Check length (international format)
            if cleaned.startswith('+'):
                # International: +<country><number> (7-15 digits after +)
                digits = cleaned[1:]
                if not digits.isdigit() or len(digits) < 7 or len(digits) > 15:
                    return False
            else:
                # Local format - depends on country, but generally 10-11 digits
                if not cleaned.isdigit() or len(cleaned) < 10 or len(cleaned) > 11:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Phone number validation error: {e}")
            return False
    
    def split_message(self, message, max_length=160):
        """
        Split long message into SMS-sized parts
        
        Args:
            message (str): Original message
            max_length (int): Maximum length per part
            
        Returns:
            list: List of message parts
        """
        if len(message) <= max_length:
            return [message]
        
        # Account for part numbering overhead: "[X/Y] " = about 6 characters
        effective_length = max_length - 10
        
        parts = []
        words = message.split()
        current_part = ""
        
        for word in words:
            if len(current_part + " " + word) <= effective_length:
                if current_part:
                    current_part += " " + word
                else:
                    current_part = word
            else:
                if current_part:
                    parts.append(current_part)
                    current_part = word
                else:
                    # Single word is too long, split it
                    parts.append(word[:effective_length])
                    current_part = word[effective_length:]
        
        if current_part:
            parts.append(current_part)
        
        return parts
    
    def get_sms_status(self):
        """
        Get SMS module status and statistics
        
        Returns:
            dict: SMS status information
        """
        status = {
            'connected': self.serial_conn is not None and self.serial_conn.is_open,
            'initialized': self.sms_initialized,
            'network_registered': self.network_registered,
            'statistics': self.sms_stats.copy()
        }
        
        # Get additional status from module
        try:
            if status['connected']:
                # Check signal quality
                response = self.send_at_command("AT+CSQ", timeout=5)
                if response and "+CSQ:" in response:
                    match = re.search(r'\+CSQ:\s*(\d+),(\d+)', response)
                    if match:
                        rssi, ber = match.groups()
                        status['signal_strength'] = {
                            'rssi': int(rssi),
                            'ber': int(ber),
                            'quality': self.interpret_signal_strength(int(rssi))
                        }
                
                # Check SIM card status
                response = self.send_at_command("AT+CPIN?", timeout=5)
                if response:
                    status['sim_status'] = response
                
                # Check operator
                response = self.send_at_command("AT+COPS?", timeout=5)
                if response and "+COPS:" in response:
                    status['operator'] = response
                    
        except Exception as e:
            self.logger.debug(f"Status check error: {e}")
        
        return status
    
    def interpret_signal_strength(self, rssi):
        """
        Interpret signal strength value
        
        Args:
            rssi (int): RSSI value from AT+CSQ
            
        Returns:
            str: Signal strength description
        """
        if rssi == 99:
            return "Unknown"
        elif rssi >= 20:
            return "Excellent"
        elif rssi >= 15:
            return "Good"
        elif rssi >= 10:
            return "Fair"
        elif rssi >= 5:
            return "Poor"
        else:
            return "Very Poor"
    
    def read_sms(self, index="ALL"):
        """
        Read SMS messages
        
        Args:
            index (str/int): Message index or "ALL" for all messages
            
        Returns:
            list: List of SMS messages
        """
        try:
            if not self.sms_initialized:
                if not self.initialize_sms():
                    return []
            
            cmd = f'AT+CMGL="{index}"' if index == "ALL" else f'AT+CMGR={index}'
            response = self.send_at_command(cmd, timeout=15)
            
            if not response:
                return []
            
            messages = []
            lines = response.split('\n')
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith('+CMGL:') or line.startswith('+CMGR:'):
                    # Parse message header
                    parts = line.split(',')
                    if len(parts) >= 4:
                        msg_index = parts[0].split(':')[1].strip()
                        status = parts[1].strip().strip('"')
                        sender = parts[2].strip().strip('"')
                        timestamp = parts[4].strip().strip('"') if len(parts) > 4 else ""
                        
                        # Get message content from next line
                        if i + 1 < len(lines):
                            content = lines[i + 1].strip()
                            
                            messages.append({
                                'index': msg_index,
                                'status': status,
                                'sender': sender,
                                'timestamp': timestamp,
                                'content': content
                            })
                
                i += 1
            
            return messages
            
        except Exception as e:
            self.logger.error(f"SMS read error: {e}")
            return []
    
    def delete_sms(self, index):
        """
        Delete SMS message
        
        Args:
            index (int/str): Message index or "ALL"
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            if index == "ALL":
                cmd = "AT+CMGD=1,4"  # Delete all messages
            else:
                cmd = f"AT+CMGD={index}"
            
            response = self.send_at_command(cmd, timeout=10)
            success = response and "OK" in response
            
            if success:
                self.logger.info(f"SMS deleted: {index}")
            else:
                self.logger.error(f"Failed to delete SMS: {index}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"SMS delete error: {e}")
            return False
    
    def test_connection(self):
        """Test SMS module connection"""
        try:
            if not self.connect():
                return False
            
            response = self.send_at_command("AT", timeout=5)
            return response is not None and "OK" in response
            
        except Exception as e:
            self.logger.error(f"SMS connection test failed: {e}")
            return False
    
    def send_test_message(self, phone_number):
        """
        Send test message
        
        Args:
            phone_number (str): Test recipient
            
        Returns:
            bool: True if sent successfully
        """
        test_message = f"🔧 Disaster Detection System Test\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nSystem operational ✅"
        
        self.logger.info(f"Sending test message to {phone_number}")
        return self.send_message(phone_number, test_message)
    
    def cleanup(self):
        """Cleanup SMS resources"""
        self.logger.info("Cleaning up SMS resources...")
        try:
            self.disconnect()
        except Exception as e:
            self.logger.error(f"SMS cleanup error: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()
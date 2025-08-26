"""
Firebase integration for cloud data synchronization
Handles detection data upload and system status reporting
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, storage
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logging.warning("Firebase Admin SDK not available")

class FirebaseSync:
    def __init__(self, config):
        """
        Initialize Firebase sync
        
        Args:
            config (dict): Firebase configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        self.db = None
        self.storage_bucket = None
        self.initialized = False
        
        if not FIREBASE_AVAILABLE:
            self.logger.error("Firebase Admin SDK not installed")
            return
        
        self.initialize_firebase()
    
    def initialize_firebase(self):
        """Initialize Firebase connection"""
        try:
            project_id = self.config.get('project_id')
            credentials_file = self.config.get('credentials_file')
            
            if not project_id:
                self.logger.error("Firebase project_id not configured")
                return
            
            # Check if Firebase app already initialized
            try:
                app = firebase_admin.get_app()
                self.logger.info("Using existing Firebase app")
            except ValueError:
                # Initialize new Firebase app
                if credentials_file and Path(credentials_file).exists():
                    cred = credentials.Certificate(credentials_file)
                    firebase_admin.initialize_app(cred, {
                        'projectId': project_id,
                        'storageBucket': f"{project_id}.appspot.com"
                    })
                    self.logger.info("Firebase initialized with service account")
                else:
                    # Try default credentials
                    firebase_admin.initialize_app()
                    self.logger.info("Firebase initialized with default credentials")
            
            # Initialize Firestore
            self.db = firestore.client()
            
            # Initialize Storage (optional)
            try:
                self.storage_bucket = storage.bucket()
            except Exception as e:
                self.logger.warning(f"Storage bucket not available: {e}")
            
            self.initialized = True
            self.logger.info("Firebase sync initialized successfully")
            
            # Test connection
            self.test_connection()
            
        except Exception as e:
            self.logger.error(f"Firebase initialization failed: {e}")
            self.initialized = False
    
    def test_connection(self):
        """Test Firebase connection"""
        try:
            if not self.db:
                return False
            
            # Try to write a test document
            test_doc = {
                'test': True,
                'timestamp': datetime.now(),
                'message': 'Connection test'
            }
            
            collection = self.config.get('collection', 'detections')
            self.db.collection(collection).document('connection_test').set(test_doc)
            
            self.logger.info("Firebase connection test successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Firebase connection test failed: {e}")
            return False
    
    def upload_detection(self, detection_record):
        """
        Upload detection record to Firestore
        
        Args:
            detection_record (dict): Detection data
            
        Returns:
            bool: True if uploaded successfully
        """
        if not self.initialized:
            self.logger.warning("Firebase not initialized, skipping upload")
            return False
        
        try:
            collection = self.config.get('collection', 'detections')
            
            # Prepare document data
            doc_data = {
                'timestamp': detection_record.get('timestamp'),
                'counts': detection_record.get('counts', {}),
                'total_detected': detection_record.get('total_detected', 0),
                'gps_coordinates': detection_record.get('gps_coordinates'),
                'confidence_scores': detection_record.get('confidence_scores', []),
                'upload_time': datetime.now(),
                'device_id': self.get_device_id()
            }
            
            # Generate document ID
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
            doc_id = f"detection_{timestamp}"
            
            # Upload to Firestore
            doc_ref = self.db.collection(collection).document(doc_id)
            doc_ref.set(doc_data)
            
            self.logger.info(f"Detection uploaded to Firebase: {doc_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Firebase upload failed: {e}")
            return False
    
    def upload_system_status(self, status_data):
        """
        Upload system status to Firestore
        
        Args:
            status_data (dict): System status information
            
        Returns:
            bool: True if uploaded successfully
        """
        if not self.initialized:
            return False
        
        try:
            # Prepare status document
            doc_data = {
                'timestamp': datetime.now(),
                'device_id': self.get_device_id(),
                'status': status_data,
                'uptime': self.get_uptime()
            }
            
            # Upload to status collection
            doc_ref = self.db.collection('system_status').document(self.get_device_id())
            doc_ref.set(doc_data)
            
            self.logger.debug("System status uploaded to Firebase")
            return True
            
        except Exception as e:
            self.logger.error(f"System status upload failed: {e}")
            return False
    
    def upload_image(self, image_path, detection_id=None):
        """
        Upload image to Firebase Storage
        
        Args:
            image_path (str): Path to image file
            detection_id (str): Associated detection ID
            
        Returns:
            str: Download URL or None
        """
        if not self.storage_bucket or not Path(image_path).exists():
            return None
        
        try:
            # Generate storage path
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"images/{self.get_device_id()}/{timestamp}.jpg"
            
            # Upload file
            blob = self.storage_bucket.blob(filename)
            blob.upload_from_filename(image_path)
            
            # Make blob publicly accessible (optional)
            blob.make_public()
            
            download_url = blob.public_url
            self.logger.info(f"Image uploaded to Firebase Storage: {filename}")
            
            return download_url
            
        except Exception as e:
            self.logger.error(f"Image upload failed: {e}")
            return None
    
    def get_detections(self, limit=10, start_date=None, end_date=None):
        """
        Retrieve detections from Firestore
        
        Args:
            limit (int): Maximum number of records
            start_date (datetime): Start date filter
            end_date (datetime): End date filter
            
        Returns:
            list: List of detection records
        """
        if not self.initialized:
            return []
        
        try:
            collection = self.config.get('collection', 'detections')
            query = self.db.collection(collection)
            
            # Apply filters
            if start_date:
                query = query.where('timestamp', '>=', start_date)
            if end_date:
                query = query.where('timestamp', '<=', end_date)
            
            # Order and limit
            query = query.order_by('timestamp', direction=firestore.Query.DESCENDING)
            query = query.limit(limit)
            
            # Execute query
            docs = query.stream()
            
            detections = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                detections.append(data)
            
            return detections
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve detections: {e}")
            return []
    
    def get_system_status(self, device_id=None):
        """
        Get system status from Firestore
        
        Args:
            device_id (str): Device ID (current device if None)
            
        Returns:
            dict: System status or None
        """
        if not self.initialized:
            return None
        
        try:
            if not device_id:
                device_id = self.get_device_id()
            
            doc_ref = self.db.collection('system_status').document(device_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get system status: {e}")
            return None
    
    def update_device_config(self, config_updates):
        """
        Update device configuration in Firestore
        
        Args:
            config_updates (dict): Configuration updates
            
        Returns:
            bool: True if updated successfully
        """
        if not self.initialized:
            return False
        
        try:
            device_id = self.get_device_id()
            doc_ref = self.db.collection('device_config').document(device_id)
            
            doc_ref.set({
                'config': config_updates,
                'updated_at': datetime.now(),
                'device_id': device_id
            }, merge=True)
            
            self.logger.info("Device configuration updated in Firebase")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update device config: {e}")
            return False
    
    def get_device_config(self):
        """
        Get device configuration from Firestore
        
        Returns:
            dict: Device configuration or None
        """
        if not self.initialized:
            return None
        
        try:
            device_id = self.get_device_id()
            doc_ref = self.db.collection('device_config').document(device_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict().get('config', {})
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get device config: {e}")
            return None
    
    def sync_local_logs(self, log_file_path):
        """
        Sync local detection logs to Firestore
        
        Args:
            log_file_path (str): Path to local log file
            
        Returns:
            int: Number of records synced
        """
        if not self.initialized or not Path(log_file_path).exists():
            return 0
        
        synced_count = 0
        
        try:
            with open(log_file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        detection_record = json.loads(line.strip())
                        
                        # Check if already synced
                        if self.is_record_synced(detection_record):
                            continue
                        
                        # Upload to Firebase
                        if self.upload_detection(detection_record):
                            synced_count += 1
                        
                    except json.JSONDecodeError:
                        self.logger.warning(f"Invalid JSON on line {line_num}")
                    except Exception as e:
                        self.logger.error(f"Error syncing line {line_num}: {e}")
            
            self.logger.info(f"Synced {synced_count} records to Firebase")
            return synced_count
            
        except Exception as e:
            self.logger.error(f"Log sync failed: {e}")
            return 0
    
    def is_record_synced(self, detection_record):
        """
        Check if detection record is already synced
        
        Args:
            detection_record (dict): Detection record
            
        Returns:
            bool: True if already synced
        """
        try:
            timestamp = detection_record.get('timestamp')
            if not timestamp:
                return False
            
            collection = self.config.get('collection', 'detections')
            query = self.db.collection(collection).where('timestamp', '==', timestamp).limit(1)
            
            docs = list(query.stream())
            return len(docs) > 0
            
        except Exception as e:
            self.logger.debug(f"Sync check failed: {e}")
            return False
    
    def get_device_id(self):
        """
        Get unique device identifier
        
        Returns:
            str: Device ID
        """
        try:
            # Try to get from system
            import socket
            hostname = socket.gethostname()
            
            # Try to get MAC address
            import uuid
            mac = hex(uuid.getnode())[2:].upper()
            
            return f"{hostname}_{mac}"
            
        except Exception:
            return "unknown_device"
    
    def get_uptime(self):
        """
        Get system uptime
        
        Returns:
            dict: Uptime information
        """
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
            
            return {
                'seconds': uptime_seconds,
                'hours': uptime_seconds / 3600,
                'days': uptime_seconds / 86400
            }
            
        except Exception:
            return {'seconds': 0, 'hours': 0, 'days': 0}
    
    def get_firebase_stats(self):
        """
        Get Firebase synchronization statistics
        
        Returns:
            dict: Firebase statistics
        """
        stats = {
            'initialized': self.initialized,
            'firebase_available': FIREBASE_AVAILABLE,
            'project_id': self.config.get('project_id'),
            'collection': self.config.get('collection', 'detections'),
            'device_id': self.get_device_id()
        }
        
        if self.initialized:
            try:
                # Get document count (approximate)
                collection = self.config.get('collection', 'detections')
                query = self.db.collection(collection).limit(1)
                docs = list(query.stream())
                stats['connection_status'] = 'connected' if docs is not None else 'error'
                
            except Exception as e:
                stats['connection_status'] = f'error: {str(e)}'
        
        return stats
    
    def cleanup(self):
        """Cleanup Firebase resources"""
        self.logger.info("Cleaning up Firebase resources...")
        try:
            # Firebase Admin SDK handles cleanup automatically
            pass
        except Exception as e:
            self.logger.error(f"Firebase cleanup error: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()
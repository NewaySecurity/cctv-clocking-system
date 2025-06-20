"""
Web dashboard module for NEWAY SECURITY CCTV CLOCKING SYSTEM.

This module provides a Flask-based web interface for viewing the live camera feed,
attendance logs, and managing employees and system settings.
"""

import os
import io
import time
import datetime
import threading
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from functools import wraps

import cv2
import numpy as np
from flask import (
    Flask, Response, render_template, request, redirect, url_for, flash,
    session, send_from_directory, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from src.utils import get_logger, load_config, FACES_DIR
from src.camera_handler import RTSPCamera
from src.face_recognition_module import FaceRecognizer, FaceDatabase
from src.data_logger import AttendanceLogger, EventType
from src.audio_manager import AudioManager

# Initialize logger
logger = get_logger(__name__)

class WebDashboard:
    """
    Flask-based web dashboard for the CCTV clocking system.
    
    Features:
    - Live camera feed with face recognition
    - Attendance logs and reports
    - Employee management
    - System settings configuration
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize the web dashboard.
        
        Args:
            config: Dashboard configuration. If None, loads from default config.
        """
        # Load configuration
        if config is None:
            self.config = load_config().get('dashboard', {})
        else:
            self.config = config
            
        # Extract configuration
        self.host = self.config.get('host', '0.0.0.0')
        self.port = int(self.config.get('port', 5000))
        self.enable_auth = self.config.get('enable_authentication', True)
        self.username = self.config.get('username', 'admin')
        self.password = self.config.get('password', 'password')
        self.session_timeout = int(self.config.get('session_timeout', 60))
        
        # Initialize Flask app
        self.app = Flask(
            __name__,
            template_folder=Path(__file__).parent.parent / 'templates',
            static_folder=Path(__file__).parent.parent / 'static'
        )
        self.app.secret_key = os.urandom(24)
        self.app.config['UPLOAD_FOLDER'] = FACES_DIR
        self.app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
        
        # Initialize components
        self.camera = None
        self.face_recognizer = None
        self.logger = None
        self.audio_manager = None
        
        # Runtime state
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.processing_thread = None
        self.is_processing = False
        
        # Register routes
        self._register_routes()
        
        logger.info("WebDashboard initialized")
    
    def _register_routes(self) -> None:
        """Register all Flask routes."""
        # Auth routes
        self.app.route('/login', methods=['GET', 'POST'])(self.login)
        self.app.route('/logout')(self.logout)
        
        # Main routes
        self.app.route('/')(self.index)
        self.app.route('/video_feed')(self.video_feed)
        self.app.route('/logs')(self.logs)
        self.app.route('/employees')(self.employees)
        self.app.route('/settings')(self.settings)
        
        # API routes
        self.app.route('/api/logs', methods=['GET'])(self.api_logs)
        self.app.route('/api/daily_summary', methods=['GET'])(self.api_daily_summary)
        self.app.route('/api/add_employee', methods=['POST'])(self.api_add_employee)
        self.app.route('/api/delete_employee', methods=['POST'])(self.api_delete_employee)
        self.app.route('/api/update_settings', methods=['POST'])(self.api_update_settings)
        
        # Static assets
        self.app.route('/faces/<path:filename>')(self.serve_face_image)
    
    def _init_components(self) -> None:
        """Initialize system components if not already initialized."""
        try:
            if self.camera is None:
                logger.info("Initializing camera")
                self.camera = RTSPCamera()
                self.camera.open()
            
            if self.face_recognizer is None:
                logger.info("Initializing face recognizer")
                self.face_recognizer = FaceRecognizer()
            
            if self.logger is None:
                logger.info("Initializing attendance logger")
                self.logger = AttendanceLogger()
            
            if self.audio_manager is None:
                logger.info("Initializing audio manager")
                self.audio_manager = AudioManager()
            
            # Start processing thread if not running
            if not self.is_processing:
                self.start_processing_thread()
                
        except Exception as e:
            logger.error(f"Error initializing components: {e}")
    
    def start_processing_thread(self) -> None:
        """Start the background thread for video processing."""
        if self.processing_thread and self.processing_thread.is_alive():
            logger.warning("Processing thread already running")
            return
            
        self.is_processing = True
        self.processing_thread = threading.Thread(target=self._process_frames, daemon=True)
        self.processing_thread.start()
        logger.info("Video processing thread started")
    
    def _process_frames(self) -> None:
        """Background thread that processes video frames for face recognition."""
        logger.info("Frame processing thread started")
        
        # Last seen tracking for events
        last_seen: Dict[str, datetime.datetime] = {}
        
        # Set of already greeted people to prevent repeated greetings
        greeted = set()
        
        while self.is_processing and self.camera and self.face_recognizer:
            try:
                # Get a frame from the camera
                success, frame = self.camera.read_frame()
                
                if not success or frame is None:
                    logger.warning("Failed to read frame from camera")
                    time.sleep(0.1)
                    continue
                
                # Process frame with face recognition
                faces, annotated_frame = self.face_recognizer.process_frame(frame)
                
                # Update latest frame for video feed
                with self.frame_lock:
                    self.latest_frame = annotated_frame.copy()
                
                # Process recognized faces for events
                current_time = datetime.datetime.now()
                
                for name, location, confidence in faces:
                    # Skip "Unknown" faces for attendance logging
                    if name == "Unknown":
                        continue
                    
                    # Check if this is a new detection or returning after timeout
                    is_new_detection = False
                    
                    if name not in last_seen:
                        is_new_detection = True
                    else:
                        # Check if the recognition timeout has passed
                        time_diff = (current_time - last_seen[name]).total_seconds()
                        if time_diff > self.face_recognizer.config.get('recognition_timeout', 8) * 3600:
                            is_new_detection = True
                    
                    # Update last seen time
                    last_seen[name] = current_time
                    
                    # Log event and play greeting if new detection
                    if is_new_detection and self.logger:
                        # Determine if this is likely clock in or clock out based on time of day
                        hour = current_time.hour
                        is_leaving = hour >= 16 or hour < 6  # After 4pm or before 6am
                        
                        # Log appropriate event
                        event_type = EventType.CLOCK_OUT if is_leaving else EventType.CLOCK_IN
                        self.logger.log_event(name, event_type)
                        
                        # Play greeting if not already greeted recently
                        if name not in greeted and self.audio_manager:
                            self.audio_manager.greet(name, is_leaving)
                            greeted.add(name)
                
                # Clear greeting cache periodically (every 5 minutes)
                if current_time.minute % 5 == 0 and current_time.second < 1:
                    greeted.clear()
                
            except Exception as e:
                logger.error(f"Error in frame processing thread: {e}")
                time.sleep(0.1)
    
    def _login_required(self, f):
        """Decorator to require login for routes if authentication is enabled."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if self.enable_auth and not session.get('logged_in'):
                return redirect(url_for('login', next=request.url))
            return f(*args, **kwargs)
        return decorated_function
    
    def login(self):
        """Handle login page."""
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            # Simple authentication
            if username == self.username and password == self.password:
                session['logged_in'] = True
                session['username'] = username
                session['login_time'] = time.time()
                
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            else:
                flash('Invalid username or password', 'error')
        
        return render_template('login.html')
    
    def logout(self):
        """Handle logout."""
        session.pop('logged_in', None)
        session.pop('username', None)
        flash('You have been logged out', 'info')
        return redirect(url_for('login'))
    
    @_login_required
    def index(self):
        """Main dashboard page with live feed."""
        # Initialize components if needed
        self._init_components()
        
        # Check session timeout
        if self.enable_auth and 'login_time' in session:
            elapsed = time.time() - session['login_time']
            if elapsed > (self.session_timeout * 60):
                return self.logout()
            # Refresh login time
            session['login_time'] = time.time()
        
        # Get active employees for the dashboard
        employees = []
        if self.face_recognizer and self.face_recognizer.face_db:
            employees = list(self.face_recognizer.face_db.faces.keys())
        
        return render_template(
            'index.html',
            active_page='home',
            employees=employees,
            camera_connected=self.camera and self.camera.is_connected
        )
    
    def _generate_frames(self):
        """Generator for video streaming."""
        while True:
            # Wait until we have a frame
            if self.latest_frame is None:
                time.sleep(0.1)
                continue
            
            # Get the latest processed frame
            with self.frame_lock:
                if self.latest_frame is not None:
                    frame = self.latest_frame.copy()
                else:
                    continue
            
            # Convert to JPEG
            ret, jpeg = cv2.imencode('.jpg', frame)
            if not ret:
                continue
                
            # Yield the frame in MJPEG format
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n'
            )
            
            # Throttle to avoid overwhelming the browser
            time.sleep(0.04)  # ~25 FPS
    
    def video_feed(self):
        """Route for video streaming."""
        # Initialize components if needed
        self._init_components()
        
        # Return a multipart response for the MJPEG stream
        return Response(
            self._generate_frames(),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    
    @_login_required
    def logs(self):
        """Attendance logs page."""
        # Initialize components if needed
        self._init_components()
        
        return render_template(
            'logs.html',
            active_page='logs'
        )
    
    @_login_required
    def employees(self):
        """Employee management page."""
        # Initialize components if needed
        self._init_components()
        
        # Get list of employees
        employees = []
        if self.face_recognizer and self.face_recognizer.face_db:
            for name, face_data in self.face_recognizer.face_db.faces.items():
                employees.append({
                    'name': name,
                    'images': len(face_data.image_paths),
                    'encodings': len(face_data.encodings),
                    'last_modified': datetime.datetime.fromtimestamp(face_data.last_modified)
                })
        
        return render_template(
            'employees.html',
            active_page='employees',
            employees=employees
        )
    
    @_login_required
    def settings(self):
        """System settings page."""
        # Initialize components if needed
        self._init_components()
        
        # Get current configuration
        config = load_config()
        
        return render_template(
            'settings.html',
            active_page='settings',
            config=config
        )
    
    @_login_required
    def api_logs(self):
        """API endpoint for attendance logs."""
        # Initialize components if needed
        self._init_components()
        
        try:
            # Parse date range parameters
            start_date_str = request.args.get('start_date')
            end_date_str = request.args.get('end_date')
            name = request.args.get('name')
            
            # Convert date strings to datetime objects
            if start_date_str:
                start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
            else:
                # Default to beginning of current month
                today = datetime.datetime.now()
                start_date = datetime.datetime(today.year, today.month, 1)
                
            if end_date_str:
                end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d')
            else:
                # Default to today
                end_date = datetime.datetime.now()
            
            # Get events from the logger
            if self.logger:
                events_df = self.logger.get_events(start_date, end_date, name)
                
                # Convert DataFrame to list of dictionaries
                events = events_df.to_dict('records')
                
                return jsonify({
                    'success': True,
                    'events': events
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Attendance logger not initialized'
                })
                
        except Exception as e:
            logger.error(f"Error in api_logs: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    @_login_required
    def api_daily_summary(self):
        """API endpoint for daily attendance summary."""
        # Initialize components if needed
        self._init_components()
        
        try:
            # Parse date parameter
            date_str = request.args.get('date')
            
            # Convert date string to datetime object
            if date_str:
                date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
            else:
                # Default to today
                date = datetime.datetime.now()
            
            # Get daily summary from the logger
            if self.logger:
                summary_df = self.logger.get_daily_summary(date)
                
                # Convert DataFrame to list of dictionaries
                summary = summary_df.to_dict('records')
                
                return jsonify({
                    'success': True,
                    'summary': summary,
                    'date': date.strftime('%Y-%m-%d')
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Attendance logger not initialized'
                })
                
        except Exception as e:
            logger.error(f"Error in api_daily_summary: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    @_login_required
    def api_add_employee(self):
        """API endpoint for adding a new employee."""
        # Initialize components if needed
        self._init_components()
        
        try:
            # Get employee name
            name = request.form.get('name')
            
            if not name:
                return jsonify({
                    'success': False,
                    'error': 'Employee name is required'
                })
            
            # Sanitize name for use as directory name
            safe_name = secure_filename(name)
            
            # Create employee directory if it doesn't exist
            employee_dir = FACES_DIR / safe_name
            employee_dir.mkdir(exist_ok=True)
            
            # Check if files were uploaded
            if 'images' not in request.files:
                return jsonify({
                    'success': False,
                    'error': 'No image files uploaded'
                })
            
            # Process uploaded files
            files = request.files.getlist('images')
            
            if not files or all(not f.filename for f in files):
                return jsonify({
                    'success': False,
                    'error': 'No image files selected'
                })
            
            # Save uploaded files
            saved_files = []
            
            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    filepath = employee_dir / filename
                    file.save(filepath)
                    saved_files.append(filename)
            
            # Reload face database
            if self.face_recognizer and self.face_recognizer.face_db:
                self.face_recognizer.face_db.load_faces()
            
            return jsonify({
                'success': True,
                'message': f'Employee {name} added with {len(saved_files)} images',
                'files': saved_files
            })
            
        except Exception as e:
            logger.error(f"Error in api_add_employee: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    @_login_required
    def api_delete_employee(self):
        """API endpoint for deleting an employee."""
        # Initialize components if needed
        self._init_components()
        
        try:
            # Get employee name
            name = request.form.get('name')
            
            if not name:
                return jsonify({
                    'success': False,
                    'error': 'Employee name is required'
                })
            
            # Check if employee directory exists
            employee_dir = FACES_DIR / name
            
            if not employee_dir.exists():
                return jsonify({
                    'success': False,
                    'error': f'Employee {name} not found'
                })
            
            # Delete employee directory and all contents
            shutil.rmtree(employee_dir)
            
            # Reload face database
            if self.face_recognizer and self.face_recognizer.face_db:
                self.face_recognizer.face_db.load_faces()
            
            return jsonify({
                'success': True,
                'message': f'Employee {name} deleted'
            })
            
        except Exception as e:
            logger.error(f"Error in api_delete_employee: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    @_login_required
    def api_update_settings(self):
        """API endpoint for updating system settings."""
        # This would typically update a configuration file
        # For now, we'll just return a success response
        return jsonify({
            'success': True,
            'message': 'Settings updated'
        })
    
    def serve_face_image(self, filename):
        """Serve face images from the faces directory."""
        return send_from_directory(FACES_DIR, filename)
    
    def run(self, debug: bool = False) -> None:
        """
        Run the Flask web server.
        
        Args:
            debug: Enable Flask debug mode
        """
        logger.info(f"Starting web dashboard on {self.host}:{self.port}")
        
        # Initialize components before starting
        self._init_components()
        
        # Run the Flask app
        self.app.run(
            host=self.host,
            port=self.port,
            debug=debug,
            threaded=True
        )
    
    def close(self) -> None:
        """Release resources and stop background threads."""
        self.is_processing = False
        
        # Wait for processing thread to finish
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)
        
        # Close components
        if self.camera:
            self.camera.close()
            
        if self.face_recognizer:
            self.face_recognizer.close()
            
        if self.audio_manager:
            self.audio_manager.close()
            
        logger.info("WebDashboard resources released")


# Example usage
if __name__ == "__main__":
    dashboard = WebDashboard()
    
    try:
        dashboard.run(debug=True)
    finally:
        dashboard.close()


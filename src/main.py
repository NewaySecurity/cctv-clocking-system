#!/usr/bin/env python3
"""
NEWAY SECURITY CCTV CLOCKING SYSTEM

Main entry point for the application.
Initializes all components and starts the web dashboard.
"""

import os
import sys
import time
import signal
import argparse
import threading
import traceback
from pathlib import Path

# Add project root to sys.path if needed
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils import get_logger, load_config, setup_logging
from src.camera_handler import RTSPCamera
from src.face_recognition_module import FaceRecognizer, FaceDatabase
from src.audio_manager import AudioManager
from src.data_logger import AttendanceLogger, EventType
from src.web_dashboard import WebDashboard

# Initialize logger
logger = get_logger(__name__)

class ClockingSystem:
    """
    Main system class that initializes and coordinates all components.
    """
    
    def __init__(self, config_name="default", debug=False):
        """
        Initialize the clocking system.
        
        Args:
            config_name: Name of the configuration file to use
            debug: Enable debug mode
        """
        self.debug = debug
        self.running = False
        self.components = {}
        
        try:
            # Load configuration
            logger.info(f"Loading configuration: {config_name}")
            self.config = load_config(config_name)
            
            # Initialize components
            self._init_components()
            
            # Set up signal handlers for graceful shutdown
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
        except Exception as e:
            logger.error(f"Error initializing ClockingSystem: {e}")
            logger.debug(traceback.format_exc())
            raise
    
    def _init_components(self):
        """Initialize all system components."""
        try:
            logger.info("Initializing system components...")
            
            # Initialize camera
            logger.info("Initializing camera...")
            self.components['camera'] = RTSPCamera(self.config.get('camera', {}))
            
            # Initialize face recognition
            logger.info("Initializing face recognition...")
            face_db = FaceDatabase(self.config.get('face_recognition', {}))
            self.components['face_recognizer'] = FaceRecognizer(face_db, self.config.get('face_recognition', {}))
            
            # Initialize audio manager
            logger.info("Initializing audio manager...")
            self.components['audio_manager'] = AudioManager(self.config.get('audio', {}))
            
            # Initialize data logger
            logger.info("Initializing data logger...")
            self.components['logger'] = AttendanceLogger(self.config.get('logging', {}))
            
            # Initialize web dashboard last (depends on other components)
            logger.info("Initializing web dashboard...")
            self.components['dashboard'] = WebDashboard(self.config.get('dashboard', {}))
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing components: {e}")
            logger.debug(traceback.format_exc())
            self._cleanup()
            raise
    
    def _signal_handler(self, sig, frame):
        """Handle termination signals for graceful shutdown."""
        logger.info(f"Received signal {sig}, shutting down...")
        self.stop()
    
    def start(self):
        """Start the clocking system and all its components."""
        if self.running:
            logger.warning("System is already running")
            return
        
        try:
            logger.info("Starting NEWAY SECURITY CCTV CLOCKING SYSTEM...")
            self.running = True
            
            # Start camera
            logger.info("Starting camera...")
            camera = self.components.get('camera')
            if camera:
                if not camera.open():
                    logger.error("Failed to open camera connection")
                else:
                    logger.info("Camera started successfully")
            
            # Start the web dashboard in a separate thread
            logger.info("Starting web dashboard...")
            dashboard = self.components.get('dashboard')
            if dashboard:
                self.dashboard_thread = threading.Thread(
                    target=dashboard.run,
                    kwargs={'debug': self.debug},
                    daemon=True
                )
                self.dashboard_thread.start()
                logger.info("Web dashboard started")
                
                # Wait for dashboard thread to be ready
                time.sleep(2)
                
                # Print access information
                host = self.config.get('dashboard', {}).get('host', '0.0.0.0')
                port = self.config.get('dashboard', {}).get('port', 5000)
                logger.info(f"Web dashboard accessible at http://localhost:{port}")
                if host == '0.0.0.0':
                    logger.info(f"For remote access: http://<your-ip-address>:{port}")
            
            # Keep the main thread running
            logger.info("System running - press Ctrl+C to stop")
            while self.running and self.dashboard_thread.is_alive():
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        except Exception as e:
            logger.error(f"Error running system: {e}")
            logger.debug(traceback.format_exc())
        finally:
            self.stop()
    
    def stop(self):
        """Stop the clocking system and all its components."""
        if not self.running:
            return
            
        logger.info("Stopping NEWAY SECURITY CCTV CLOCKING SYSTEM...")
        self.running = False
        
        # Call cleanup to release resources
        self._cleanup()
        
        logger.info("System stopped")
    
    def _cleanup(self):
        """Clean up resources and stop all components."""
        # Clean up in reverse order of initialization
        
        # Stop dashboard
        logger.info("Stopping web dashboard...")
        dashboard = self.components.pop('dashboard', None)
        if dashboard:
            dashboard.close()
        
        # Stop logger
        logger.info("Stopping data logger...")
        # Data logger doesn't need explicit cleanup
        self.components.pop('logger', None)
        
        # Stop audio manager
        logger.info("Stopping audio manager...")
        audio_manager = self.components.pop('audio_manager', None)
        if audio_manager:
            audio_manager.close()
        
        # Stop face recognizer
        logger.info("Stopping face recognizer...")
        face_recognizer = self.components.pop('face_recognizer', None)
        if face_recognizer:
            face_recognizer.close()
        
        # Stop camera last
        logger.info("Stopping camera...")
        camera = self.components.pop('camera', None)
        if camera:
            camera.close()
        
        logger.info("All components stopped successfully")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="NEWAY SECURITY CCTV CLOCKING SYSTEM",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--config", 
        default="default",
        help="Name of configuration file to use (without .yml extension)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    return parser.parse_args()


def main():
    """Main entry point for the application."""
    # Initialize logging
    setup_logging()
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Print welcome message
    print("\n" + "=" * 80)
    print("NEWAY SECURITY CCTV CLOCKING SYSTEM")
    print("Copyright © 2025 Neway Security. All rights reserved.")
    print("=" * 80 + "\n")
    
    # Create and start the system
    try:
        system = ClockingSystem(config_name=args.config, debug=args.debug)
        system.start()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.debug(traceback.format_exc())
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


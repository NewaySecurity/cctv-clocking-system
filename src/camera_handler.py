"""
Camera handling module for NEWAY SECURITY CCTV CLOCKING SYSTEM.

This module provides the RTSPCamera class for connecting to RTSP camera streams,
handling reconnection, and providing a real-time frame generator.
"""

import asyncio
import time
import threading
from typing import Dict, Optional, Tuple, Generator, AsyncGenerator
from queue import Queue, Empty

import cv2
import numpy as np

from src.utils import get_logger, load_config

# Initialize logger
logger = get_logger(__name__)

class RTSPCamera:
    """
    Handles connection to an RTSP camera stream with automatic reconnection.
    
    Features:
    - Connect to RTSP streams
    - Automatic reconnection with exponential backoff
    - Frame processing (resize, rate limiting)
    - Async frame generator for real-time streaming
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize the RTSPCamera with configuration.
        
        Args:
            config: Camera configuration dictionary. If None, loads from default config.
        """
        # Load configuration if not provided
        if config is None:
            self.config = load_config().get('camera', {})
        else:
            self.config = config
            
        # Extract configuration
        self.rtsp_url = self.config.get('url')
        self.fallback_index = self.config.get('fallback_index', 0)
        self.reconnect_interval = self.config.get('reconnect_interval', 5)
        self.max_reconnect_attempts = self.config.get('max_reconnect_attempts', 10)
        self.frame_width = self.config.get('frame_width', 640)
        self.frame_height = self.config.get('frame_height', 480)
        self.fps_limit = self.config.get('fps_limit', 15)
        
        # Runtime state
        self.capture = None
        self.is_connected = False
        self.is_running = False
        self.last_frame = None
        self.last_frame_time = 0
        self.reconnect_count = 0
        self.frame_interval = 1.0 / self.fps_limit  # Time between frames
        
        # Thread-safe frame queue for async generator
        self.frame_queue = Queue(maxsize=10)
        self.frame_thread = None
        
        logger.info(f"RTSPCamera initialized with URL: {self.rtsp_url}")
    
    def open(self) -> bool:
        """
        Open connection to the RTSP camera.
        
        Returns:
            bool: True if connection successful, False otherwise.
        """
        logger.info(f"Attempting to connect to camera: {self.rtsp_url}")
        
        # Try RTSP URL first
        self.capture = cv2.VideoCapture(self.rtsp_url)
        
        # Check if connection was successful
        if not self.capture.isOpened():
            logger.warning(f"Failed to connect to RTSP URL: {self.rtsp_url}")
            logger.info(f"Falling back to camera index: {self.fallback_index}")
            
            # Try fallback to local camera
            self.capture.release()
            self.capture = cv2.VideoCapture(self.fallback_index)
            
            if not self.capture.isOpened():
                logger.error("Failed to connect to fallback camera")
                self.is_connected = False
                return False
        
        # Set camera properties
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
        
        self.is_connected = True
        self.reconnect_count = 0
        logger.info("Camera connection established successfully")
        return True
    
    def close(self) -> None:
        """Close the camera connection and release resources."""
        self.is_running = False
        
        # Wait for frame thread to finish if it's running
        if self.frame_thread and self.frame_thread.is_alive():
            self.frame_thread.join(timeout=1.0)
        
        # Release capture device
        if self.capture:
            self.capture.release()
            self.capture = None
        
        self.is_connected = False
        logger.info("Camera connection closed")
    
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read a single frame from the camera.
        
        Returns:
            Tuple containing:
                bool: Success flag
                Optional[np.ndarray]: The frame if successful, None otherwise
        """
        if not self.is_connected or not self.capture:
            logger.warning("Cannot read frame: Camera not connected")
            return False, None
            
        # Implement frame rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_frame_time
        
        if time_since_last < self.frame_interval:
            # Return the last frame if we're reading too quickly
            return True, self.last_frame
            
        # Read frame
        success, frame = self.capture.read()
        
        if not success or frame is None:
            logger.warning("Failed to read frame from camera")
            return False, None
            
        # Resize frame if needed
        if frame.shape[1] != self.frame_width or frame.shape[0] != self.frame_height:
            frame = cv2.resize(frame, (self.frame_width, self.frame_height))
            
        # Update last frame timestamp
        self.last_frame_time = current_time
        self.last_frame = frame
        
        return True, frame
    
    def _reconnect_with_backoff(self) -> bool:
        """
        Attempt to reconnect with exponential backoff.
        
        Returns:
            bool: True if reconnection successful, False if max attempts reached
        """
        # Check if max attempts reached
        if 0 < self.max_reconnect_attempts <= self.reconnect_count:
            logger.error(f"Maximum reconnection attempts ({self.max_reconnect_attempts}) reached")
            return False
            
        # Calculate backoff time (exponential with jitter)
        backoff = min(30, self.reconnect_interval * (2 ** self.reconnect_count))
        jitter = backoff * 0.1 * np.random.random()
        wait_time = backoff + jitter
        
        logger.info(f"Attempting reconnection {self.reconnect_count + 1}/{self.max_reconnect_attempts} "
                   f"in {wait_time:.2f} seconds")
        
        # Sleep before reconnecting
        time.sleep(wait_time)
        
        # Increment counter and try to reconnect
        self.reconnect_count += 1
        
        # Close any existing connection
        if self.capture:
            self.capture.release()
            self.capture = None
            
        # Attempt to reconnect
        return self.open()
    
    def start_capture_thread(self) -> None:
        """Start the background thread for continuous frame capture."""
        if self.frame_thread and self.frame_thread.is_alive():
            logger.warning("Frame capture thread already running")
            return
            
        self.is_running = True
        self.frame_thread = threading.Thread(target=self._capture_frames_loop, daemon=True)
        self.frame_thread.start()
        logger.info("Frame capture thread started")
    
    def _capture_frames_loop(self) -> None:
        """Background loop that continuously captures frames and puts them in the queue."""
        logger.info("Frame capture loop started")
        
        while self.is_running:
            if not self.is_connected and not self._reconnect_with_backoff():
                # Failed to reconnect, exit loop
                logger.error("Failed to reconnect, stopping capture loop")
                self.is_running = False
                break
                
            success, frame = self.read_frame()
            
            if success and frame is not None:
                # If queue is full, remove oldest frame
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                    except Empty:
                        pass
                        
                # Add new frame to queue
                self.frame_queue.put((time.time(), frame))
            else:
                # Connection issue, try to reconnect
                logger.warning("Connection issue detected, attempting to reconnect")
                self.is_connected = False
                
            # Small sleep to prevent CPU overuse
            time.sleep(0.01)
    
    def frames(self) -> Generator[Tuple[float, np.ndarray], None, None]:
        """
        Generate frames from the camera in real-time.
        
        Yields:
            Tuple containing:
                float: Timestamp of the frame
                np.ndarray: The captured frame
        """
        # Start capture thread if not already running
        if not self.is_running:
            self.start_capture_thread()
            
        while self.is_running:
            try:
                timestamp, frame = self.frame_queue.get(timeout=1.0)
                yield timestamp, frame
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error in frame generator: {e}")
                time.sleep(0.1)
    
    async def frames_async(self) -> AsyncGenerator[Tuple[float, np.ndarray], None]:
        """
        Asynchronous generator for frames from the camera.
        
        Yields:
            Tuple containing:
                float: Timestamp of the frame
                np.ndarray: The captured frame
        """
        # Start capture thread if not already running
        if not self.is_running:
            self.start_capture_thread()
            
        while self.is_running:
            try:
                # Use asyncio to avoid blocking the event loop
                timestamp, frame = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.frame_queue.get(timeout=1.0))
                yield timestamp, frame
            except Empty:
                await asyncio.sleep(0.01)
                continue
            except Exception as e:
                logger.error(f"Error in async frame generator: {e}")
                await asyncio.sleep(0.1)

# Example usage
if __name__ == "__main__":
    camera = RTSPCamera()
    
    try:
        if camera.open():
            # Simple demo: display video for 30 seconds
            start_time = time.time()
            for _, frame in camera.frames():
                cv2.imshow("RTSP Camera Feed", frame)
                
                # Break on 'q' key or after 30 seconds
                if cv2.waitKey(1) & 0xFF == ord('q') or time.time() - start_time > 30:
                    break
    finally:
        camera.close()
        cv2.destroyAllWindows()


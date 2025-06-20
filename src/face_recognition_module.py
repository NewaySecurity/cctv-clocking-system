"""
Face recognition module for NEWAY SECURITY CCTV CLOCKING SYSTEM.

This module provides face detection, recognition, and database management
for employee identification and attendance tracking.
"""

import os
import time
import glob
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Union
from dataclasses import dataclass
import threading

import cv2
import numpy as np
import face_recognition

from src.utils import get_logger, load_config, FACES_DIR

# Initialize logger
logger = get_logger(__name__)

@dataclass
class FaceData:
    """Store face data for an individual."""
    name: str
    encodings: List[np.ndarray]
    last_modified: float
    image_paths: List[Path]


class FaceDatabase:
    """
    Manages a database of face encodings for employees.
    
    Features:
    - Load face images from the faces directory
    - Generate and store face encodings
    - Monitor for changes and hot-reload
    - Provide fast lookup for face recognition
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize the face database.
        
        Args:
            config: Face recognition configuration. If None, loads from default config.
        """
        # Load configuration
        if config is None:
            self.config = load_config().get('face_recognition', {})
        else:
            self.config = config
            
        # Extract configuration
        self.detection_method = self.config.get('method', 'hog')
        self.unknown_label = self.config.get('unknown_face_label', 'Unknown')
        
        # Runtime state
        self.faces: Dict[str, FaceData] = {}
        self.last_scan_time = 0
        self.lock = threading.RLock()
        self._watcher_thread = None
        self._watching = False
        
        # Ensure faces directory exists
        if not FACES_DIR.exists():
            logger.info(f"Creating faces directory: {FACES_DIR}")
            FACES_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load faces on initialization
        self.load_faces()
        
        logger.info(f"FaceDatabase initialized with {len(self.faces)} employees")
    
    def load_faces(self) -> None:
        """
        Load all face images and generate encodings.
        
        This scans the faces directory structure for images and processes them.
        Directory names are used as person names.
        """
        with self.lock:
            start_time = time.time()
            logger.info("Loading face database...")
            
            # Track currently seen files to detect deletions
            current_images: Set[Path] = set()
            faces_updated = False
            
            # Get all person directories (direct subdirectories of FACES_DIR)
            for person_dir in [d for d in FACES_DIR.iterdir() if d.is_dir()]:
                person_name = person_dir.name
                
                # Find all image files for this person
                image_paths = []
                for ext in ['jpg', 'jpeg', 'png']:
                    image_paths.extend(list(person_dir.glob(f"*.{ext}")))
                    image_paths.extend(list(person_dir.glob(f"*.{ext.upper()}")))
                
                # Skip if no images found
                if not image_paths:
                    logger.warning(f"No images found for person: {person_name}")
                    continue
                
                # Add to current images set
                for path in image_paths:
                    current_images.add(path)
                
                # Check if this person already exists and if any files have changed
                if person_name in self.faces:
                    existing_data = self.faces[person_name]
                    needs_update = False
                    
                    # Check if any images were added or modified
                    for img_path in image_paths:
                        if img_path not in existing_data.image_paths:
                            needs_update = True
                            break
                        
                        mtime = img_path.stat().st_mtime
                        if mtime > existing_data.last_modified:
                            needs_update = True
                            break
                    
                    # Skip if no updates needed
                    if not needs_update:
                        continue
                
                # Process images and generate encodings
                encodings = []
                max_mtime = 0
                
                for img_path in image_paths:
                    try:
                        # Track the most recent modification time
                        mtime = img_path.stat().st_mtime
                        max_mtime = max(max_mtime, mtime)
                        
                        # Load and process image
                        image = face_recognition.load_image_file(str(img_path))
                        face_locations = face_recognition.face_locations(image, model=self.detection_method)
                        
                        # Skip if no face detected
                        if not face_locations:
                            logger.warning(f"No face detected in image: {img_path}")
                            continue
                        
                        # If multiple faces, use the largest one (assumed to be the primary subject)
                        if len(face_locations) > 1:
                            logger.warning(f"Multiple faces detected in {img_path}, using the largest face")
                            largest_area = 0
                            largest_idx = 0
                            
                            for i, (top, right, bottom, left) in enumerate(face_locations):
                                area = (bottom - top) * (right - left)
                                if area > largest_area:
                                    largest_area = area
                                    largest_idx = i
                            
                            face_locations = [face_locations[largest_idx]]
                        
                        # Generate face encoding
                        face_encodings = face_recognition.face_encodings(image, face_locations)
                        if face_encodings:
                            encodings.append(face_encodings[0])
                            logger.debug(f"Added encoding for {person_name} from {img_path}")
                        
                    except Exception as e:
                        logger.error(f"Error processing image {img_path}: {e}")
                
                # Skip if no valid encodings
                if not encodings:
                    logger.warning(f"No valid face encodings generated for person: {person_name}")
                    continue
                
                # Update database entry
                self.faces[person_name] = FaceData(
                    name=person_name,
                    encodings=encodings,
                    last_modified=max_mtime,
                    image_paths=image_paths
                )
                faces_updated = True
                logger.info(f"Added/updated {person_name} with {len(encodings)} face encodings")
            
            # Check for deleted people/images
            to_remove = []
            for person_name, face_data in self.faces.items():
                # Check if any image for this person still exists
                if not any(path in current_images for path in face_data.image_paths):
                    to_remove.append(person_name)
                    faces_updated = True
            
            # Remove deleted entries
            for person_name in to_remove:
                del self.faces[person_name]
                logger.info(f"Removed {person_name} from face database (images deleted)")
            
            # Update last scan time
            self.last_scan_time = time.time()
            logger.info(f"Face database loading completed in {time.time() - start_time:.2f}s")
            logger.info(f"Face database contains {len(self.faces)} people with faces")
            
            if not self.faces:
                logger.warning("Face database is empty! Add images to the 'faces' directory.")
            
            return faces_updated
    
    def start_watch_thread(self, interval: int = 30) -> None:
        """
        Start a background thread to watch for changes in the faces directory.
        
        Args:
            interval: The polling interval in seconds
        """
        if self._watcher_thread and self._watcher_thread.is_alive():
            logger.warning("Face database watcher thread is already running")
            return
        
        self._watching = True
        self._watcher_thread = threading.Thread(
            target=self._watch_directory,
            args=(interval,),
            daemon=True
        )
        self._watcher_thread.start()
        logger.info(f"Started face database watcher thread (interval: {interval}s)")
    
    def _watch_directory(self, interval: int) -> None:
        """
        Background thread that monitors the faces directory for changes.
        
        Args:
            interval: The polling interval in seconds
        """
        logger.info(f"Face database watcher started, monitoring {FACES_DIR}")
        
        while self._watching:
            try:
                # Sleep first to avoid immediate reload after initialization
                time.sleep(interval)
                
                # Check for modifications
                reload_needed = False
                
                # Check if any directories were added/removed
                for path in FACES_DIR.iterdir():
                    if path.is_dir() and path.name not in self.faces:
                        reload_needed = True
                        logger.info(f"Detected new person directory: {path.name}")
                        break
                
                # Check if any existing images were modified
                if not reload_needed:
                    for face_data in self.faces.values():
                        for img_path in face_data.image_paths:
                            if img_path.exists():
                                mtime = img_path.stat().st_mtime
                                if mtime > face_data.last_modified:
                                    reload_needed = True
                                    logger.info(f"Detected modified image: {img_path}")
                                    break
                        if reload_needed:
                            break
                
                # Check for new image files
                if not reload_needed:
                    for ext in ['jpg', 'jpeg', 'png', 'JPG', 'JPEG', 'PNG']:
                        for img_path in FACES_DIR.glob(f"**/*.{ext}"):
                            # Get person name from parent directory
                            person_name = img_path.parent.name
                            
                            # Check if this is a new image
                            if person_name in self.faces:
                                if img_path not in self.faces[person_name].image_paths:
                                    reload_needed = True
                                    logger.info(f"Detected new image: {img_path}")
                                    break
                        if reload_needed:
                            break
                
                # Reload the database if changes detected
                if reload_needed:
                    logger.info("Changes detected in faces directory, reloading database...")
                    self.load_faces()
                
            except Exception as e:
                logger.error(f"Error in face database watcher thread: {e}")
    
    def stop_watch_thread(self) -> None:
        """Stop the background watcher thread."""
        self._watching = False
        if self._watcher_thread and self._watcher_thread.is_alive():
            self._watcher_thread.join(timeout=1.0)
            logger.info("Face database watcher thread stopped")
    
    def get_all_encodings(self) -> Dict[str, List[np.ndarray]]:
        """
        Get all face encodings in the database.
        
        Returns:
            Dictionary mapping person names to lists of face encodings
        """
        with self.lock:
            return {name: face_data.encodings.copy() for name, face_data in self.faces.items()}
    
    def count(self) -> int:
        """
        Get the number of people in the database.
        
        Returns:
            The number of people with face encodings
        """
        with self.lock:
            return len(self.faces)


class FaceRecognizer:
    """
    Performs real-time face detection and recognition on video frames.
    
    Features:
    - Process frames from camera feed
    - Detect and recognize faces
    - Draw bounding boxes and labels
    - Optimize for performance
    """
    
    def __init__(self, face_db: FaceDatabase = None, config: Dict = None):
        """
        Initialize the face recognizer.
        
        Args:
            face_db: FaceDatabase instance. If None, a new one is created.
            config: Face recognition configuration. If None, loads from default config.
        """
        # Load configuration
        if config is None:
            self.config = load_config().get('face_recognition', {})
        else:
            self.config = config
        
        # Extract configuration
        self.detection_method = self.config.get('method', 'hog')
        self.tolerance = self.config.get('tolerance', 0.6)
        self.min_face_size = self.config.get('min_face_size', 0.05)
        self.downscale_factor = self.config.get('downscale_factor', 2)
        self.show_boxes = self.config.get('show_bounding_boxes', True)
        self.show_names = self.config.get('show_names', True)
        self.box_color = tuple(self.config.get('box_color', [0, 255, 0]))
        self.text_color = tuple(self.config.get('text_color', [255, 255, 255]))
        self.unknown_label = self.config.get('unknown_face_label', 'Unknown')
        self.log_unknown = self.config.get('log_unknown_faces', True)
        
        # Initialize face database
        self.face_db = face_db if face_db else FaceDatabase(self.config)
        
        # Start database watcher thread
        self.face_db.start_watch_thread()
        
        logger.info(f"FaceRecognizer initialized with {self.face_db.count()} people")
    
    def process_frame(
        self, 
        frame: np.ndarray, 
        draw: bool = True
    ) -> Tuple[List[Tuple[str, Tuple[int, int, int, int], float]], Optional[np.ndarray]]:
        """
        Process a video frame to detect and recognize faces.
        
        Args:
            frame: The video frame to process
            draw: Whether to draw bounding boxes and labels on the frame
            
        Returns:
            Tuple containing:
                List of recognized faces: (name, face_location, confidence)
                Annotated frame if draw=True, otherwise None
        """
        # Start timing for performance monitoring
        start_time = time.time()
        
        # Make a copy if we're going to draw on it
        output_frame = frame.copy() if draw else None
        
        # Downscale image for faster processing
        if self.downscale_factor > 1:
            h, w = frame.shape[:2]
            small_frame = cv2.resize(
                frame, 
                (w // self.downscale_factor, h // self.downscale_factor)
            )
        else:
            small_frame = frame
        
        # Convert from BGR (OpenCV) to RGB (face_recognition)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        # Find face locations in the frame
        face_locations = face_recognition.face_locations(
            rgb_small_frame,
            model=self.detection_method
        )
        
        # No faces found, return early
        if not face_locations:
            processing_time = time.time() - start_time
            logger.debug(f"No faces detected (took {processing_time*1000:.1f}ms)")
            return [], output_frame
        
        # Get face encodings
        face_encodings = face_recognition.face_encodings(
            rgb_small_frame,
            face_locations
        )
        
        # Get all known face encodings
        known_face_encodings_dict = self.face_db.get_all_encodings()
        
        # List to store recognition results
        recognized_faces = []
        
        # Process each detected face
        for i, (face_encoding, face_location) in enumerate(zip(face_encodings, face_locations)):
            # Scale back the face location if we downscaled
            if self.downscale_factor > 1:
                top, right, bottom, left = face_location
                face_location = (
                    top * self.downscale_factor,
                    right * self.downscale_factor,
                    bottom * self.downscale_factor,
                    left * self.downscale_factor
                )
            
            # Check if face is large enough (skip tiny faces that might be false positives)
            top, right, bottom, left = face_location
            face_height = bottom - top
            image_height = frame.shape[0]
            if face_height / image_height < self.min_face_size:
                logger.debug(f"Skipping small face: {face_height/image_height:.3f} of frame height")
                continue
            
            # Try to match with known faces
            best_match = None
            best_confidence = 0.0
            
            for person_name, encodings in known_face_encodings_dict.items():
                # Compare against all encodings for this person
                for ref_encoding in encodings:
                    # Calculate face distance (lower = more similar)
                    face_distance = face_recognition.face_distance([ref_encoding], face_encoding)[0]
                    
                    # Convert distance to a confidence score (0-1, higher is better)
                    confidence = 1.0 - min(1.0, face_distance)
                    
                    # Update best match if this is better
                    if confidence > best_confidence and confidence >= (1.0 - self.tolerance):
                        best_match = person_name
                        best_confidence = confidence
            
            # Use unknown label if no match found
            if best_match is None:
                if self.log_unknown:
                    recognized_faces.append((self.unknown_label, face_location, 0.0))
            else:
                recognized_faces.append((best_match, face_location, best_confidence))
            
            # Draw on output frame if requested
            if draw and output_frame is not None:
                self.draw_face_annotation(
                    output_frame, 
                    face_location, 
                    best_match or self.unknown_label,
                    best_confidence
                )
        
        # Log performance
        processing_time = time.time() - start_time
        logger.debug(
            f"Processed {len(face_locations)} faces in {processing_time*1000:.1f}ms "
            f"({len(recognized_faces)} recognized)"
        )
        
        return recognized_faces, output_frame
    
    def draw_face_annotation(
        self,
        frame: np.ndarray,
        face_location: Tuple[int, int, int, int],
        name: str,
        confidence: float
    ) -> None:
        """
        Draw bounding box and name label for a recognized face.
        
        Args:
            frame: The frame to draw on
            face_location: (top, right, bottom, left) coordinates
            name: Person name to display
            confidence: Recognition confidence (0-1)
        """
        if not self.show_boxes and not self.show_names:
            return
            
        top, right, bottom, left = face_location
        
        # Draw bounding box
        if self.show_boxes:
            cv2.rectangle(frame, (left, top), (right, bottom), self.box_color, 2)
        
        # Draw name label
        if self.show_names:
            # Format label with confidence if it's not the unknown label
            if name != self.unknown_label:
                label = f"{name} ({confidence:.1%})"
            else:
                label = name
                
            # Draw label background
            label_size, baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            y = top - 10 if top - 10 > 10 else top + 10
            cv2.rectangle(
                frame,
                (left, y - label_size[1]),
                (left + label_size[0], y + baseline),
                self.box_color,
                cv2.FILLED
            )
            
            # Draw text
            cv2.putText(
                frame,
                label,
                (left, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                self.text_color,
                1
            )
    
    def close(self) -> None:
        """Release resources and stop background threads."""
        self.face_db.stop_watch_thread()
        logger.info("FaceRecognizer resources released")


# Example usage
if __name__ == "__main__":
    import time
    from src.camera_handler import RTSPCamera
    
    # Initialize camera and face recognizer
    camera = RTSPCamera()
    recognizer = FaceRecognizer()
    
    try:
        if camera.open():
            # Process video feed for 30 seconds
            start_time = time.time()
            for _, frame in camera.frames():
                # Process frame for face recognition
                faces, annotated_frame = recognizer.process_frame(frame)
                
                # Print recognized faces
                if faces:
                    for name, _, confidence in faces:
                        print(f"Recognized: {name} ({confidence:.1%})")
                
                # Display the annotated frame
                cv2.imshow("Face Recognition", annotated_frame)
                
                # Break on 'q' key or after 30 seconds
                if cv2.waitKey(1) & 0xFF == ord('q') or time.time() - start_time > 30:
                    break
    finally:
        camera.close()
        recognizer.close()
        cv2.destroyAllWindows()


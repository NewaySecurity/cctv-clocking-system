"""
Audio manager module for NEWAY SECURITY CCTV CLOCKING SYSTEM.

This module provides text-to-speech functionality for greeting recognized
employees and visitors with configurable voice settings.
"""

import os
import time
import tempfile
import threading
import queue
from typing import Dict, Optional, Callable, Any
from pathlib import Path

# TTS engines
import pyttsx3
try:
    from gtts import gTTS
    from playsound import playsound
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

from src.utils import get_logger, load_config

# Initialize logger
logger = get_logger(__name__)

class AudioManager:
    """
    Manages text-to-speech and audio playback for the system.
    
    Features:
    - Unified TTS interface (pyttsx3 or gTTS)
    - Configurable voice settings
    - Anti-spam protection for greetings
    - Asynchronous audio processing
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize the audio manager.
        
        Args:
            config: Audio configuration. If None, loads from default config.
        """
        # Load configuration
        if config is None:
            self.config = load_config().get('audio', {})
        else:
            self.config = config
        
        # Extract configuration
        self.engine_type = self.config.get('engine', 'pyttsx3')
        self.volume = float(self.config.get('volume', 1.0))
        self.rate = int(self.config.get('rate', 150))
        self.voice_id = self.config.get('voice_id', 'default')
        self.language = self.config.get('language', 'en')
        self.welcome_template = self.config.get('welcome_message', "Hi {name}, welcome to work")
        self.goodbye_template = self.config.get('goodbye_message', "Goodbye {name}, see you tomorrow")
        self.unknown_message = self.config.get('unknown_message', "Visitor detected. Access restricted.")
        self.greeting_timeout = int(self.config.get('greeting_timeout', 60))
        
        # Anti-spam tracking
        self.last_greetings: Dict[str, float] = {}
        
        # Message queue for async processing
        self.message_queue = queue.Queue()
        self.is_running = False
        self.worker_thread = None
        
        # Temp directory for gTTS files
        self.temp_dir = Path(tempfile.gettempdir()) / "neway_audio"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Initialize TTS engine
        self._init_engine()
        
        # Start worker thread
        self.start_worker()
        
        logger.info(f"AudioManager initialized using {self.engine_type} engine")
    
    def _init_engine(self) -> None:
        """Initialize the appropriate TTS engine based on configuration."""
        if self.engine_type == 'gtts':
            if not GTTS_AVAILABLE:
                logger.warning("gTTS not available, falling back to pyttsx3")
                self.engine_type = 'pyttsx3'
                
            # For gTTS, we don't need to initialize anything here
            self.engine = None
        else:
            # Initialize pyttsx3
            try:
                self.engine = pyttsx3.init()
                
                # Configure voice settings
                self.engine.setProperty('volume', self.volume)
                self.engine.setProperty('rate', self.rate)
                
                # Set voice if specified and available
                if self.voice_id != 'default':
                    voices = self.engine.getProperty('voices')
                    for voice in voices:
                        if self.voice_id in voice.id:
                            self.engine.setProperty('voice', voice.id)
                            break
                
                logger.info("pyttsx3 engine initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize pyttsx3: {e}")
                self.engine = None
    
    def start_worker(self) -> None:
        """Start the background worker thread for async TTS processing."""
        if self.worker_thread and self.worker_thread.is_alive():
            logger.warning("Audio worker thread already running")
            return
            
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        logger.info("Audio worker thread started")
    
    def _process_queue(self) -> None:
        """Background thread that processes the TTS message queue."""
        logger.info("Audio processing thread started")
        
        while self.is_running:
            try:
                # Get message from queue with timeout
                message, callback = self.message_queue.get(timeout=0.5)
                
                # Process the message
                try:
                    if self.engine_type == 'gtts' and GTTS_AVAILABLE:
                        self._speak_gtts(message)
                    else:
                        self._speak_pyttsx3(message)
                    
                    # Call the callback if provided
                    if callback:
                        callback(True)
                except Exception as e:
                    logger.error(f"Error speaking message: {e}")
                    if callback:
                        callback(False)
                
                # Mark task as done
                self.message_queue.task_done()
                
            except queue.Empty:
                # No message in queue, just continue
                pass
            except Exception as e:
                logger.error(f"Error in audio worker thread: {e}")
                time.sleep(1.0)  # Avoid tight loop on persistent errors
    
    def _speak_pyttsx3(self, message: str) -> None:
        """
        Speak a message using pyttsx3.
        
        Args:
            message: The text to speak
        """
        if not self.engine:
            logger.error("pyttsx3 engine not initialized")
            return
            
        try:
            self.engine.say(message)
            self.engine.runAndWait()
            logger.debug(f"Spoke message with pyttsx3: {message}")
        except Exception as e:
            logger.error(f"pyttsx3 speak error: {e}")
    
    def _speak_gtts(self, message: str) -> None:
        """
        Speak a message using Google Text-to-Speech.
        
        Args:
            message: The text to speak
        """
        try:
            # Create a unique temporary filename
            temp_file = self.temp_dir / f"tts_{int(time.time())}_{hash(message) % 10000}.mp3"
            
            # Generate TTS audio file
            tts = gTTS(text=message, lang=self.language, slow=False)
            tts.save(str(temp_file))
            
            # Play the audio file
            playsound(str(temp_file))
            logger.debug(f"Spoke message with gTTS: {message}")
            
            # Clean up the temporary file
            try:
                os.remove(temp_file)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {temp_file}: {e}")
                
        except Exception as e:
            logger.error(f"gTTS speak error: {e}")
    
    def speak(self, message: str, callback: Optional[Callable[[bool], Any]] = None) -> None:
        """
        Queue a message to be spoken asynchronously.
        
        Args:
            message: The text to speak
            callback: Optional callback function to call when speech completes
        """
        self.message_queue.put((message, callback))
        logger.debug(f"Queued message: {message}")
    
    def greet(self, name: str, is_leaving: bool = False) -> bool:
        """
        Greet a recognized person (with anti-spam protection).
        
        Args:
            name: Person's name
            is_leaving: True for goodbye message, False for welcome
            
        Returns:
            True if greeting was queued, False if skipped due to anti-spam
        """
        # Skip if this is an unknown person and we have a blank message
        if name == "Unknown" and not self.unknown_message:
            return False
            
        # Check if this person was recently greeted
        current_time = time.time()
        if name in self.last_greetings:
            time_since_last = current_time - self.last_greetings[name]
            if time_since_last < self.greeting_timeout:
                logger.debug(
                    f"Skipping greeting for {name}, "
                    f"last greeted {time_since_last:.1f}s ago "
                    f"(timeout: {self.greeting_timeout}s)"
                )
                return False
        
        # Select appropriate message template
        if name == "Unknown":
            message = self.unknown_message
        elif is_leaving:
            message = self.goodbye_template.format(name=name)
        else:
            message = self.welcome_template.format(name=name)
        
        # Queue the greeting
        self.speak(message)
        
        # Update anti-spam tracking
        self.last_greetings[name] = current_time
        logger.info(f"Greeting queued for {name}: '{message}'")
        
        return True
    
    def close(self) -> None:
        """Clean up resources and stop the worker thread."""
        self.is_running = False
        
        # Wait for worker thread to finish
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
        
        # Clean up pyttsx3 engine if used
        if self.engine_type == 'pyttsx3' and self.engine:
            # No explicit cleanup needed for pyttsx3
            self.engine = None
        
        # Clean up temp directory for gTTS
        if self.engine_type == 'gtts':
            try:
                for file in self.temp_dir.glob("tts_*.mp3"):
                    try:
                        os.remove(file)
                    except:
                        pass
            except Exception as e:
                logger.warning(f"Error cleaning up temp files: {e}")
        
        logger.info("AudioManager resources released")


# Example usage
if __name__ == "__main__":
    import time
    
    # Initialize audio manager
    audio = AudioManager()
    
    try:
        # Test greeting messages
        audio.greet("Thabiso", is_leaving=False)
        time.sleep(3)  # Wait for first greeting to complete
        
        # This should be blocked by anti-spam
        blocked = not audio.greet("Thabiso", is_leaving=False)
        print(f"Second greeting blocked by anti-spam: {blocked}")
        
        # Test goodbye message
        audio.greet("Sihle", is_leaving=True)
        time.sleep(3)
        
        # Test unknown visitor
        audio.greet("Unknown")
        time.sleep(3)
        
        # Test direct speak
        audio.speak("Testing the speech system.")
        time.sleep(3)
        
    finally:
        # Allow time for queued messages to complete
        print("Waiting for queued messages to complete...")
        time.sleep(2)
        
        # Clean up
        audio.close()


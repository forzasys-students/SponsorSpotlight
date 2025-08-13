from enum import Enum
import threading
import time

class ProgressStage(Enum):
    IDLE = 0
    UPLOAD_COMPLETE = 1
    MODEL_LOADING = 2
    MODEL_READY = 3
    INFERENCE_START = 4
    INFERENCE_PROGRESS = 5
    POST_PROCESSING = 6
    COMPLETE = 7
    ERROR = 8

class ProgressManager:
    """
    Manages and tracks the progress of file processing operations.
    Thread-safe singleton to be accessed from multiple parts of the application.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ProgressManager, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        """Initialize the progress manager with default values"""
        self.stage = ProgressStage.IDLE
        self.message = "Ready"
        self.current_frame = None
        self.total_frames = None
        self.progress_percentage = 0
        self.start_time = None
        self.update_time = None
        self._lock = threading.Lock()
    
    def update_progress(self, stage, message=None, frame=None, total_frames=None, progress_percentage=None):
        """Update the progress information in a thread-safe manner"""
        with self._lock:
            self.stage = stage
            
            if message is not None:
                self.message = message
                
            if frame is not None:
                self.current_frame = frame
                
            if total_frames is not None:
                self.total_frames = total_frames
                
            if progress_percentage is not None:
                self.progress_percentage = progress_percentage
            
            # If this is the first update, set the start time
            if self.start_time is None and stage != ProgressStage.IDLE:
                self.start_time = time.time()
                
            self.update_time = time.time()
    
    def get_progress(self):
        """Get the current progress information"""
        with self._lock:
            elapsed_time = None
            if self.start_time is not None:
                elapsed_time = time.time() - self.start_time
                
            return {
                'stage': self.stage.name,
                'message': self.message,
                'current_frame': self.current_frame,
                'total_frames': self.total_frames,
                'progress_percentage': self.progress_percentage,
                'elapsed_time': elapsed_time
            }
    
    def reset(self):
        """Reset the progress information"""
        with self._lock:
            self._initialize()
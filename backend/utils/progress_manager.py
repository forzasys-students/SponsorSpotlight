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
        # Legacy overall timers (kept for compatibility if needed)
        self.start_time = None
        self.update_time = None
        # Detection-only timing (AI inference period only)
        self._detection_start_time = None
        self._detection_elapsed = None
        # GPU peak memory observed during detection (in MB)
        self.gpu_peak_mb = None
        self._lock = threading.Lock()
    
    def update_progress(self, stage, message=None, frame=None, total_frames=None, progress_percentage=None, gpu_peak_mb=None):
        """Update the progress information in a thread-safe manner"""
        with self._lock:
            previous_stage = self.stage
            self.stage = stage
            
            if message is not None:
                self.message = message
                
            if frame is not None:
                self.current_frame = frame
                
            if total_frames is not None:
                self.total_frames = total_frames
                
            if progress_percentage is not None:
                # Ensure monotonic progress to avoid regressions from duplicate updates/threads
                try:
                    self.progress_percentage = max(self.progress_percentage, float(progress_percentage))
                except Exception:
                    self.progress_percentage = progress_percentage

            # Track peak GPU memory if provided
            if gpu_peak_mb is not None:
                try:
                    new_val = float(gpu_peak_mb)
                    self.gpu_peak_mb = new_val if self.gpu_peak_mb is None else max(self.gpu_peak_mb, new_val)
                except Exception:
                    self.gpu_peak_mb = gpu_peak_mb
            
            # Legacy: overall start time (first non-idle)
            if self.start_time is None and stage != ProgressStage.IDLE:
                self.start_time = time.time()

            # Detection-only timer
            # Start when we first enter INFERENCE_PROGRESS
            if self._detection_start_time is None and stage == ProgressStage.INFERENCE_PROGRESS:
                self._detection_start_time = time.time()
            # Freeze when leaving inference into post-processing/complete/error
            if (
                self._detection_start_time is not None
                and self._detection_elapsed is None
                and stage in (ProgressStage.POST_PROCESSING, ProgressStage.COMPLETE, ProgressStage.ERROR)
            ):
                self._detection_elapsed = time.time() - self._detection_start_time
                
            self.update_time = time.time()
    
    def get_progress(self):
        """Get the current progress information"""
        with self._lock:
            # Report detection-only elapsed time
            elapsed_time = None
            if self._detection_start_time is not None and self._detection_elapsed is None:
                elapsed_time = time.time() - self._detection_start_time
            elif self._detection_elapsed is not None:
                elapsed_time = self._detection_elapsed
                
            return {
                'stage': self.stage.name,
                'message': self.message,
                'current_frame': self.current_frame,
                'total_frames': self.total_frames,
                'progress_percentage': self.progress_percentage,
                'elapsed_time': elapsed_time,
                'gpu_peak_mb': self.gpu_peak_mb
            }
    
    def reset(self):
        """Reset the progress information"""
        with self._lock:
            self._initialize()
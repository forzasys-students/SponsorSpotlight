from typing import Dict, Optional, Callable, Any, Set
from enum import Enum

class ProgressStage(Enum):
    RECEIVING_MEDIA = 0
    CHECKING_CACHE = 1
    MODEL_READY = 2
    INFERENCE_START = 3
    INFERENCE_PROGRESS = 4
    POST_PROCESSING = 5
    COMPLETE = 6
    ERROR = -1

class ProgressManager:
    _instance = None
    _callbacks: Set[Callable[[Dict[str, Any]], None]] 

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._callbacks = set()
            cls.is_callback_registered = False
            cls._instance._current_stage = ProgressStage.RECEIVING_MEDIA
            cls._instance._message = "Receiving file"
            cls._instance._progress = 0.0
        return cls._instance
    
    # Register callback to recieve progress updates
    def register_callback(self, callback: Callable[[Dict[str, Any]], None]):
        if not self.is_callback_registered:
            self._callbacks.add(callback)
            self.is_callback_registered = True
        else:
            print("[REGISTER_CALLBACK] Callback already registered, skipping.")
    
    # Update progress (from anywhere in the application)
    def update_progress(
            self,
            stage: ProgressStage,
            message: Optional[str] = None,
            progress: Optional[float] = None,
            frame: Optional[int] = None,
            total_frames: Optional[int] = None,
            progress_percentage: Optional[int] = None
    ):
        self._current_stage = stage
        self._message = message or stage.name.replace("_"," ").title()
        if progress is not None:
            self._progress = max(0.0, min(1.0, progress))
        
        self._frame = frame
        self._total_frames = total_frames
        self._progress_percentage = progress_percentage
        
        self._notify()
    
    # Notify all registered callbacks
    def _notify(self):
        progress_data = {
            "stage": self._current_stage.value,
            "stage_name": self._current_stage.name,
            "message": self._message,
            "progress": self._progress,
            "frame": self._frame,
            "total_frames": self._total_frames,
            "progress_percentage": self._progress_percentage
        }
        for callback in self._callbacks:
            callback(progress_data)
    
    # Get current progress state
    def get_progress(self) -> Dict:
        return {
            "stage": self._current_stage.value,
            "stage_name": self._current_stage.name,
            "message": self._message,
            "progress": self._progress,
            "frame": self._frame,
            "total_frames": self._total_frames,
            "progress_percentage": self._progress_percentage
        }
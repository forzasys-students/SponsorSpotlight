import os
import sys
import threading
import cv2
import torch
import numpy as np
import json
from collections import defaultdict, Counter
import time
from ultralytics import YOLO

from backend.utils.progress_manager import ProgressManager, ProgressStage

class InferenceManager:
    """
    Manages the inference process for logo detection in images and videos.
    Handles model loading, processing, and result generation.
    """
    
    def __init__(self, progress_manager=None):
        """Initialize the inference manager with optional progress tracking"""
        self.progress = progress_manager or ProgressManager()
        self.model = None
        
        # Get base directory
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Set up paths
        self.model_path = os.path.join(self.base_dir, 'train-result', 'yolov11-m-finetuned', 'weights', 'best.pt')
        self.classes_path = os.path.join(self.base_dir, 'inference', 'classes.txt')
        self.output_dir = os.path.join(self.base_dir, 'frontend', 'static', 'results')
        
        # Print paths for debugging
        print(f"Model path: {self.model_path}")
        print(f"Classes path: {self.classes_path}")
        print(f"Output directory: {self.output_dir}")
        
        # Load logo groups mapping
        self.logo_groups = self._load_logo_groups()
        
        # Load class names
        self.class_names = self._load_class_names()
        
        # Define color palette for visualization
        self.color_palette = [
            (31, 119, 180), (255, 127, 14), (44, 160, 44),
            (214, 39, 40), (148, 103, 189), (140, 86, 75),
            (227, 119, 194), (127, 127, 127), (188, 189, 34),
            (23, 190, 207)
        ]
        
        # Setup output directories
        os.makedirs(self.output_dir, exist_ok=True)
    
    def _load_logo_groups(self):
        """Load logo groups mapping from the existing project"""
        try:
            # Try to import from the existing project
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
            from inference.logo_groups import LOGO_GROUPS
            return LOGO_GROUPS
        except ImportError:
            # Fallback to an empty dictionary if import fails
            return {}
    
    def _load_class_names(self):
        """Load class names from the classes.txt file"""
        try:
            with open(self.classes_path, 'r') as f:
                return f.read().splitlines()
        except FileNotFoundError:
            self.progress.update_progress(
                ProgressStage.ERROR,
                f"Classes file not found at {self.classes_path}"
            )
            return []
    
    def _load_model(self):
        """Load the YOLO model"""
        try:
            self.progress.update_progress(
                ProgressStage.MODEL_LOADING,
                "Loading model"
            )
            
            # Get the best available device
            device = self._get_device()
            
            # Load the model
            self.model = YOLO(self.model_path).to(device)
            
            self.progress.update_progress(
                ProgressStage.MODEL_READY,
                f"Model loaded on {device}"
            )
            
            return True
        except Exception as e:
            self.progress.update_progress(
                ProgressStage.ERROR,
                f"Failed to load model: {str(e)}"
            )
            return False
    
    def _get_device(self):
        """Determine the best available device for inference"""
        if torch.cuda.is_available():
            return 'cuda'
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return 'mps'
        else:
            return 'cpu'
    
    def start_inference(self, mode, input_path, file_hash):
        """Start the inference process in a separate thread"""
        thread = threading.Thread(
            target=self._run_inference,
            args=(mode, input_path, file_hash)
        )
        thread.daemon = True
        thread.start()
    
    def _run_inference(self, mode, input_path, file_hash):
        """Run the inference process"""
        try:
            # Reset progress for the new task
            self.progress.reset()
            
            # Start progress update
            self.progress.update_progress(
                ProgressStage.INFERENCE_START,
                "Preparing for inference"
            )
            
            # Load the model if not already loaded
            if self.model is None:
                if not self._load_model():
                    return
            
            # Process based on mode
            if mode == 'image':
                self._process_image(input_path, file_hash)
            elif mode == 'video':
                if self._is_url(input_path):
                    self._process_video_stream(input_path, file_hash)
                else:
                    self._process_video(input_path, file_hash)
            else:
                self.progress.update_progress(
                    ProgressStage.ERROR,
                    f"Invalid mode: {mode}"
                )
        except Exception as e:
            self.progress.update_progress(
                ProgressStage.ERROR,
                f"Inference failed: {str(e)}"
            )
    
    def _annotate_frame(self, frame, results):
        """Annotate a frame with detection results"""
        if results is None:
            return frame
        
        for result in results:
            obb = result.obb
            if obb is None:
                continue
            
            frame = frame.copy()
            for i in range(len(obb.conf)):
                conf = float(obb.conf[i])
                cls = int(obb.cls[i])
                class_name = self.class_names[cls]
                label = f'{class_name}: {conf:.2f}'
                
                if hasattr(obb, 'xyxyxyxy'):
                    polygon = obb.xyxyxyxy[i]
                    if hasattr(polygon, 'cpu'):
                        polygon = polygon.cpu().numpy()
                    
                    points = polygon.reshape(4, 2)
                    is_normalized = np.all(points <= 1.0)
                    
                    if is_normalized:
                        points[:, 0] *= frame.shape[1]
                        points[:, 1] *= frame.shape[0]
                    else:
                        if np.max(points) > max(frame.shape):
                            scale_factor = min(frame.shape[1] / np.max(points[:, 0]), 
                                              frame.shape[0] / np.max(points[:, 1]))
                            points = points * scale_factor
                    
                    points = points.astype(np.int32)
                    x_center = int(points[:, 0].mean())
                    y_center = int(points[:, 1].mean())
                    color = self.color_palette[cls % len(self.color_palette)]
                    
                    cv2.drawContours(frame, [points], 0, color, 2)
                    
                    (text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                    text_x = max(0, x_center - text_width // 2)
                    text_y = max(0, y_center - text_height - baseline - 5)
                    
                    overlay = frame.copy()
                    cv2.rectangle(overlay, (text_x, text_y), (text_x + text_width, text_y + text_height + baseline), color, thickness=cv2.FILLED)
                    alpha = 0.6
                    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
                    cv2.putText(frame, label, (text_x, text_y + text_height), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        return frame
    
    def _process_image(self, image_path, file_hash):
        """Process an image for logo detection"""
        # Create a dedicated directory for the results
        result_dir = os.path.join(self.output_dir, file_hash)
        os.makedirs(result_dir, exist_ok=True)

        # Generate output paths within the new directory
        output_path = os.path.join(result_dir, 'output.jpg')
        stats_file = os.path.join(result_dir, 'stats.json')
        
        # Load and process the image
        image = cv2.imread(image_path)
        results = self.model(image)
        
        logo_count = Counter()
        
        self.progress.update_progress(
            ProgressStage.INFERENCE_PROGRESS,
            "Processing image",
            frame=1,
            total_frames=1,
            progress_percentage=100
        )
        
        # Count logo detections
        for result in results:
            obb = result.obb
            if obb is None:
                continue
            
            for i in range(len(obb.conf)):
                cls = int(obb.cls[i])
                class_name = self.class_names[cls]
                logo_count[class_name] += 1
        
        # Annotate the image
        annotated_image = self._annotate_frame(image, results)
        cv2.imwrite(output_path, annotated_image)
        
        # Aggregate statistics
        self.progress.update_progress(
            ProgressStage.POST_PROCESSING,
            "Aggregating statistics"
        )
        
        aggregated_stats = defaultdict(lambda: {"detections": 0})
        
        for logo, count in logo_count.items():
            if count > 0:
                main_logo = self.logo_groups.get(logo, logo)
                aggregated_stats[main_logo]["detections"] += count
        
        aggregated_stats = dict(aggregated_stats)
        
        # Save statistics
        with open(stats_file, "w") as f:
            json.dump(aggregated_stats, f, indent=4)
        
        # Update progress
        self.progress.update_progress(
            ProgressStage.COMPLETE,
            "Processing complete"
        )
    
    def _process_video(self, video_path, file_hash):
        """Process a video for logo detection"""
        # Create a dedicated directory for the results
        result_dir = os.path.join(self.output_dir, file_hash)
        os.makedirs(result_dir, exist_ok=True)
        
        # Generate output paths within the new directory
        output_path = os.path.join(result_dir, 'output.mp4')
        stats_file = os.path.join(result_dir, 'stats.json')
        
        # Open the video
        cap = cv2.VideoCapture(video_path)
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(output_path, fourcc, cap.get(cv2.CAP_PROP_FPS), 
                             (int(cap.get(3)), int(cap.get(4))))
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_time = 1 / fps
        frame_count = 0
        total_video_time = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Initialize statistics tracking
        logo_stats = defaultdict(lambda: {"frames": 0, "time": 0.0, "detections": 0})
        
        self.progress.update_progress(
            ProgressStage.INFERENCE_PROGRESS,
            "Processing video",
            frame=frame_count,
            total_frames=total_frames,
            progress_percentage=0
        )
        
        # Process each frame
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            results = self.model(frame)
            
            logo_count = Counter()
            seen_main_logos = set()
            
            # Count logo detections in the frame
            for result in results:
                obb = result.obb
                if obb is None:
                    continue
                
                for i in range(len(obb.conf)):
                    cls = int(obb.cls[i])
                    class_name = self.class_names[cls]
                    logo_count[class_name] += 1
            
            # Update statistics
            for logo, count in logo_count.items():
                if count > 0:
                    main_logo = self.logo_groups.get(logo, logo)
                    logo_stats[logo]["detections"] += count
                    
                    if main_logo not in seen_main_logos:
                        logo_stats[logo]["frames"] += 1
                        logo_stats[logo]["time"] += frame_time
                        seen_main_logos.add(main_logo)
            
            # Annotate and write the frame
            annotated_frame = self._annotate_frame(frame, results)
            out.write(annotated_frame)
            
            # Update progress
            progress_percentage = (frame_count / total_frames) * 100
            self.progress.update_progress(
                ProgressStage.INFERENCE_PROGRESS,
                f"Processing frame {frame_count}/{total_frames} ({round(progress_percentage)}%)",
                frame=frame_count,
                total_frames=total_frames,
                progress_percentage=progress_percentage
            )
        
        # Clean up
        cap.release()
        out.release()
        
        # Aggregate statistics
        self.progress.update_progress(
            ProgressStage.POST_PROCESSING,
            "Aggregating statistics"
        )
        
        aggregated_stats = self._aggregate_stats(logo_stats)
        
        # Calculate percentages and round values
        for logo, stats in aggregated_stats.items():
            time_value = round(stats["time"], 2)
            if time_value > total_video_time:
                time_value = total_video_time
            
            stats["time"] = time_value
            stats["percentage"] = round((time_value / total_video_time * 100) if total_video_time > 0 else 0, 2)
        
        # Save statistics
        with open(stats_file, "w") as f:
            json.dump(aggregated_stats, f, indent=4)
        
        # Update progress
        self.progress.update_progress(
            ProgressStage.COMPLETE,
            "Processing complete"
        )
    
    def _is_url(self, path):
        """Check if a path is a URL"""
        return path.startswith('http://') or path.startswith('https://')
    
    def _process_video_stream(self, url, file_hash):
        """Process a video stream for logo detection"""
        # This would be similar to _process_video but adapted for streams
        # For simplicity, we'll just call _process_video here
        # For a real implementation, you would adapt the logic below
        
        # Create a dedicated directory for the results
        result_dir = os.path.join(self.output_dir, file_hash)
        os.makedirs(result_dir, exist_ok=True)
        
        # Generate output paths within the new directory
        output_path = os.path.join(result_dir, 'output.mp4')
        stats_file = os.path.join(result_dir, 'stats.json')
        
        # The rest of the stream processing logic would go here...
        # For now, we'll just log and finish
        
        # For this example, we'll just call the main video processor
        self._process_video(url, file_hash)
    
    def _aggregate_stats(self, logo_stats):
        """Aggregate logo statistics"""
        aggregated = defaultdict(lambda: {"frames": 0, "time": 0.0, "detections": 0, "percentage": 0.0})
        
        for logo, stats in logo_stats.items():
            # Get the main logo name or use the original if not in mapping
            main_logo = self.logo_groups.get(logo, logo)
            
            aggregated[main_logo]["frames"] += stats["frames"]
            aggregated[main_logo]["time"] += stats["time"]
            aggregated[main_logo]["detections"] += stats["detections"]
        
        return dict(aggregated)
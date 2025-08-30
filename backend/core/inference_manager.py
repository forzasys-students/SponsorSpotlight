import os
import sys
import threading
import cv2
import torch
import numpy as np
import json
import subprocess
import requests
import math
import glob
import shutil
from urllib.parse import urljoin
from collections import defaultdict, Counter
import time
from queue import Queue
from ultralytics import YOLO

from backend.utils.progress_manager import ProgressManager, ProgressStage
from backend.utils.gpu_manager import GPUManager
from backend.utils.annotator import FrameAnnotator
from backend.utils.stats_calculator import StatisticsCalculator
from backend.utils.video_utils import generate_thumbnails, create_thumbnail_sprite
import logging

class InferenceManager:
    """
    Manages the inference process for logo detection in images and videos.
    Handles model loading, processing, and result generation.
    """
    
    def __init__(self, progress_manager=None):
        """Initialize the inference manager with optional progress tracking"""
        self.progress = progress_manager or ProgressManager()
        self.model = None
        
        self.gpu_manager = GPUManager()
        
        # Track running jobs to avoid duplicates (guarded by a lock)
        self._job_lock = threading.Lock()
        self._active_job_key = None  # tuple: (mode, input_path, file_hash)
        
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
        
        self.annotator = FrameAnnotator(self.class_names, self.color_palette)
        
        # Setup output directories
        os.makedirs(self.output_dir, exist_ok=True)

        # Pipeline config: toggle video generation and H.264 conversion
        self.generate_videos = True
        self.convert_h264 = True
        self.batch_size = 1
        self.precision = "fp32"  # Default to FP32 for compatibility
        try:
            with open(os.path.join(self.base_dir, 'pipeline_config.json'), 'r') as f:
                cfg = json.load(f) or {}
                self.generate_videos = bool(cfg.get('generate_videos', True))
                self.convert_h264 = bool(cfg.get('convert_h264', True))
                # Optional batch size for batched inference (>=1)
                try:
                    self.batch_size = max(1, int(cfg.get('batch_size', 1)))
                except Exception:
                    self.batch_size = 1
                # Model precision: fp16 for speed, fp32 for compatibility
                self.precision = str(cfg.get('precision', 'fp32')).lower()
        except Exception:
            # Defaults remain True if config missing/unreadable
            pass
    
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
            
            device = self.gpu_manager.device
            
            # Load the model
            self.model = YOLO(self.model_path).to(device)
            
            # Apply precision optimization if specified
            if self.precision == "fp16":
                try:
                    self.model.model.half()  # Convert to FP16
                    print(f"Model loaded on {device} with FP16 precision")
                    self.progress.update_progress(
                        ProgressStage.MODEL_READY,
                        f"Model loaded on {device} with FP16 precision"
                    )
                except Exception as e:
                    print(f"Warning: Failed to convert to FP16: {e}, falling back to FP32")
                    self.progress.update_progress(
                        ProgressStage.MODEL_READY,
                        f"Model loaded on {device} with FP32 precision (FP16 failed)"
                    )
            else:
                self.progress.update_progress(
                    ProgressStage.MODEL_READY,
                    f"Model loaded on {device} with {self.precision.upper()} precision"
                )
            return True
        except Exception as e:
            self.progress.update_progress(
                ProgressStage.ERROR,
                f"Failed to load model: {str(e)}"
            )
            return False

    def _infer_batch(self, frames):
        """Run inference on a list of frames with graceful OOM fallback.
        Returns a list of Results objects, one per frame.
        """
        if not isinstance(frames, (list, tuple)) or len(frames) == 0:
            return []
        try:
            results = self.model(frames)
            # Ultralytics returns a list of Results objects (len == len(frames))
            return results
        except torch.cuda.OutOfMemoryError:
            try:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            # Fallback to per-frame inference
            results_per_frame = []
            for fr in frames:
                res_single = self.model(fr)
                # res_single is typically a list with one Results element
                if isinstance(res_single, list) and len(res_single) > 0:
                    results_per_frame.append(res_single[0])
                else:
                    results_per_frame.append(res_single)
            return results_per_frame
    
    def start_inference(self, mode, input_path, file_hash):
        """Start the inference process in a separate thread"""
        job_key = (mode, input_path, file_hash)
        with self._job_lock:
            # If same job is already active, don't start another
            if self._active_job_key == job_key:
                return
            # Mark active and start
            self._active_job_key = job_key
        def _runner():
            try:
                self._run_inference(mode, input_path, file_hash)
            finally:
                with self._job_lock:
                    self._active_job_key = None
        thread = threading.Thread(target=_runner)
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
    
    def _process_image(self, image_path, file_hash):
        """Process an image for logo detection"""
        start_time = time.time()
        self.gpu_manager.reset_peak_memory_stats()

        # Create a dedicated directory for the results
        result_dir = os.path.join(self.output_dir, file_hash)
        os.makedirs(result_dir, exist_ok=True)

        # Generate output paths within the new directory
        output_path = os.path.join(result_dir, 'output.jpg')
        stats_file = os.path.join(result_dir, 'stats.json')
        
        # Load and process the image
        image = cv2.imread(image_path)
        # Start detection-only timers and GPU util sampling
        detection_start = time.time()
        self.gpu_manager.start_sampling()
        results = self.model(image)
        detection_end = time.time()
        self.gpu_manager.stop_sampling()
        
        logo_count = Counter()
        
        peak_mb = self.gpu_manager.get_peak_memory_allocated_mb()
        self.progress.update_progress(
            ProgressStage.INFERENCE_PROGRESS,
            "Processing image",
            frame=1,
            total_frames=1,
            progress_percentage=100,
            gpu_peak_mb=peak_mb
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
        annotated_image = self.annotator.annotate_frame(image, results)
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
        
        # Save statistics (keep legacy format for images), plus write processing meta alongside
        try:
            processing_info = {
                "device": self.gpu_manager.device,
                "device_name": self.gpu_manager.device_name,
                "gpu_total_vram_mb": int(self.gpu_manager.gpu_total_mem_bytes / (1024**2)) if self.gpu_manager.gpu_total_mem_bytes else None,
                "gpu_peak_allocated_mb": self.gpu_manager.get_peak_memory_allocated_mb(),
                "gpu_peak_utilization_pct": int(self.gpu_manager.gpu_peak_util_pct) if self.gpu_manager.gpu_peak_util_pct is not None else None,
                "start_time": int(start_time),
                "end_time": int(time.time()),
                "duration_sec": round(max(0.0, time.time() - start_time), 2),
                "detection_duration_sec": round(max(0.0, detection_end - detection_start), 2)
            }
        except Exception:
            processing_info = {
                "device": self.gpu_manager.device,
                "device_name": self.gpu_manager.device_name,
                "gpu_total_vram_mb": int(self.gpu_manager.gpu_total_mem_bytes / (1024**2)) if self.gpu_manager.gpu_total_mem_bytes else None,
                "gpu_peak_allocated_mb": None,
                "gpu_peak_utilization_pct": int(self.gpu_manager.gpu_peak_util_pct) if self.gpu_manager.gpu_peak_util_pct is not None else None,
                "start_time": int(start_time),
                "end_time": int(time.time()),
                "duration_sec": round(max(0.0, time.time() - start_time), 2),
                "detection_duration_sec": round(max(0.0, detection_end - detection_start), 2)
            }

        # For backward compatibility, write aggregated_stats as before, and also a sidecar meta file
        with open(stats_file, "w") as f:
            json.dump(aggregated_stats, f, indent=4)
        try:
            with open(os.path.join(result_dir, 'processing_meta.json'), 'w') as f:
                json.dump({"processing_info": processing_info}, f, indent=4)
        except Exception:
            pass
        
        # Update progress
        self.progress.update_progress(
            ProgressStage.COMPLETE,
            "Processing complete"
        )
    
    def _check_ffmpeg(self):
        """Check if ffmpeg is installed and available in the system PATH."""
        try:
            # Use subprocess.run to check for ffmpeg, hiding output
            subprocess.run(['ffmpeg', '-version'], check=True, capture_output=True, text=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    def _extract_frames(self, video_path, output_dir):
        """Extract all frames from a video file or stream using ffmpeg."""
        is_url = self._is_url(video_path)
        stage_message = "Extracting video frames from stream..." if is_url else "Extracting video frames..."
        self.progress.update_progress(ProgressStage.PRE_PROCESSING, stage_message)

        # Use a padded 8-digit pattern for frame filenames
        frame_pattern = os.path.join(output_dir, 'frame_%08d.jpg')

        ffmpeg_cmd = [
            'ffmpeg', '-i', video_path,
            '-qscale:v', '16',  # High-quality JPEG
            '-f', 'image2', frame_pattern
        ]

        print(f"--> _extract_frames: Running command: {' '.join(ffmpeg_cmd)}", file=sys.stderr)
        result = subprocess.run(ffmpeg_cmd, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            source_name = "stream" if is_url else os.path.basename(video_path)
            error_msg = f"FFmpeg frame extraction error for {source_name}:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            print(error_msg)
            raise RuntimeError(f"Failed to extract frames from video. FFmpeg stderr: {result.stderr}")

        extracted_frames = sorted(glob.glob(os.path.join(output_dir, 'frame_*.jpg')))
        if not extracted_frames:
            raise RuntimeError("Frame extraction produced no files. Check video path and format.")

        return extracted_frames

    def _assemble_video(self, frames_pattern, fps, output_path):
        """Assemble a video from a sequence of frames using a web-friendly ffmpeg command."""
        self.progress.update_progress(ProgressStage.POST_PROCESSING, f"Assembling video: {os.path.basename(output_path)}")
        
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-framerate', str(fps), 
            '-i', frames_pattern,
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-level', '4.1',
            '-movflags', '+faststart',
            output_path
        ]
        
        result = subprocess.run(ffmpeg_cmd, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg video assembly error for {os.path.basename(output_path)}:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
            # Do not raise an error, as this is a final, non-critical step
    
    def _inference_worker(self, inference_queue, post_proc_queue):
        """Worker thread that runs model inference on batches of frames."""
        while True:
            batch_data = inference_queue.get()
            if batch_data is None:
                post_proc_queue.put(None)
                break
            
            frame_paths, indices = batch_data
            
            # Read frames from disk
            frames = [cv2.imread(p) for p in frame_paths]
            
            results = self._infer_batch(frames)
            post_proc_queue.put((frames, indices, results))

    def _post_processing_worker(self, post_proc_queue, stats_calculator, annotated_frames_dir, total_frames):
        """Worker thread that processes inference results and saves annotated frames."""
        while True:
            proc_data = post_proc_queue.get()
            if proc_data is None:
                break

            frames_buffer, indices_buffer, results_batch = proc_data
            
            for buf_idx, (frm, frm_idx) in enumerate(zip(frames_buffer, indices_buffer)):
                per_frame_results = [results_batch[buf_idx]] if isinstance(results_batch, list) else results_batch
                stats_calculator.process_frame(frm_idx, frm, per_frame_results)
                
                # If video generation is enabled, write the annotated frame to its own directory
                if self.generate_videos and annotated_frames_dir:
                    annotated_frame = self.annotator.annotate_frame(frm, per_frame_results)
                    frame_filename = f"frame_{frm_idx:08d}.jpg"
                    output_path = os.path.join(annotated_frames_dir, frame_filename)
                    cv2.imwrite(output_path, annotated_frame)
                
                progress_percentage = (frm_idx / total_frames) * 100 if total_frames > 0 else 0
                self.progress.update_progress(
                    ProgressStage.INFERENCE_PROGRESS,
                    f"Processing frame {frm_idx}/{total_frames} ({round(progress_percentage)}%)",
                    frame=frm_idx,
                    total_frames=total_frames,
                    progress_percentage=progress_percentage,
                    gpu_peak_mb=self.gpu_manager.get_peak_memory_allocated_mb()
                )

    def _process_frames_in_parallel(self, file_hash, frame_files, total_frames, fps, width_cap, height_cap, start_time):
        """Orchestrates the parallel processing of extracted video frames."""
        result_dir = os.path.join(self.output_dir, file_hash)
        stats_file = os.path.join(result_dir, 'stats.json')

        # Directory for annotated frames, only created if needed
        annotated_frames_dir = None
        if self.generate_videos:
            annotated_frames_dir = os.path.join(result_dir, 'frames_annotated')
            os.makedirs(annotated_frames_dir, exist_ok=True)

        # Create timeline database path
        timeline_db_path = os.path.join(result_dir, 'timeline.db')
        stats_calculator = StatisticsCalculator(self.class_names, self.logo_groups, total_frames, fps, db_path=timeline_db_path)

        self.progress.update_progress(
            ProgressStage.INFERENCE_PROGRESS,
            "Processing video frames",
            frame=0,
            total_frames=total_frames,
            progress_percentage=0
        )

        detection_start = time.time()
        self.gpu_manager.start_sampling()

        # --- Parallel Processing Setup ---
        inference_queue = Queue(maxsize=self.batch_size * 2)
        post_proc_queue = Queue(maxsize=self.batch_size * 2)

        inference_thread = threading.Thread(target=self._inference_worker, args=(inference_queue, post_proc_queue))
        post_proc_thread = threading.Thread(target=self._post_processing_worker, args=(post_proc_queue, stats_calculator, annotated_frames_dir, total_frames))

        inference_thread.start()
        post_proc_thread.start()

        # --- Main thread: Feed frame paths to the pipeline ---
        frame_paths_buffer = []
        indices_buffer = []

        for i, frame_path in enumerate(frame_files):
            frame_idx = i + 1
            frame_paths_buffer.append(frame_path)
            indices_buffer.append(frame_idx)

            if len(frame_paths_buffer) >= self.batch_size:
                inference_queue.put((list(frame_paths_buffer), list(indices_buffer)))
                frame_paths_buffer.clear()
                indices_buffer.clear()

        if frame_paths_buffer:
            inference_queue.put((frame_paths_buffer, indices_buffer))

        # Signal end of frames to workers
        inference_queue.put(None)

        # Wait for threads to finish
        inference_thread.join()
        post_proc_thread.join()

        # --- End of Parallel Processing ---
        detection_end = time.time()
        self.gpu_manager.stop_sampling()

        raw_frames_dir = os.path.dirname(frame_files[0]) if frame_files else None

        # Assemble videos from frames using ffmpeg
        if self.generate_videos:
            # Assemble annotated video
            annotated_output_path = os.path.join(result_dir, 'output.mp4')
            annotated_frames_pattern = os.path.join(annotated_frames_dir, 'frame_%08d.jpg')
            self._assemble_video(annotated_frames_pattern, fps, annotated_output_path)
            
            # Assemble raw video from original frames
            if raw_frames_dir:
                raw_output_path = os.path.join(result_dir, 'raw.mp4')
                raw_frames_pattern = os.path.join(raw_frames_dir, 'frame_%08d.jpg')
                self._assemble_video(raw_frames_pattern, fps, raw_output_path)

        # Clean up frame directories
        try:
            if raw_frames_dir:
                shutil.rmtree(raw_frames_dir)
            if annotated_frames_dir:
                shutil.rmtree(annotated_frames_dir)
        except OSError as e:
            print(f"Error cleaning up frame directories: {e}")

        # Finalize statistics
        self.progress.update_progress(ProgressStage.POST_PROCESSING, "Aggregating statistics")

        final_stats, _, _, _ = stats_calculator.finalize_stats()

        # Prepare final JSON output with metadata
        processing_info = {
            "device": self.gpu_manager.device,
            "device_name": self.gpu_manager.device_name,
            "gpu_total_vram_mb": int(self.gpu_manager.gpu_total_mem_bytes / (1024**2)) if self.gpu_manager.gpu_total_mem_bytes else None,
            "gpu_peak_allocated_mb": self.gpu_manager.get_peak_memory_allocated_mb(),
            "gpu_peak_utilization_pct": int(self.gpu_manager.gpu_peak_util_pct) if self.gpu_manager.gpu_peak_util_pct is not None else None,
            "start_time": int(start_time),
            "end_time": int(time.time()),
            "duration_sec": round(max(0.0, time.time() - start_time), 2),
            "detection_duration_sec": round(max(0.0, detection_end - detection_start), 2)
        }

        output_data = {
            "video_metadata": {
                "duration": round(stats_calculator.total_video_time, 2),
                "fps": round(fps, 2),
                "total_frames": total_frames,
                "width": width_cap,
                "height": height_cap
            },
            "logo_stats": final_stats,
            "processing_info": processing_info
        }

        # Save aggregated statistics to stats.json
        with open(stats_file, "w") as f:
            json.dump(output_data, f, indent=4)

        # After processing, generate thumbnails for the output video
        # Prioritize raw.mp4 as it's essential for the on-demand overlay viewer
        raw_video_path = os.path.join(result_dir, 'raw.mp4')
        output_video_path = os.path.join(result_dir, 'output.mp4')
        
        thumbnail_source_video = None
        if os.path.exists(raw_video_path):
            thumbnail_source_video = raw_video_path
        elif os.path.exists(output_video_path):
            thumbnail_source_video = output_video_path

        if thumbnail_source_video:
            thumbnail_dir = os.path.join(result_dir, 'thumbnails')
            generate_thumbnails(thumbnail_source_video, thumbnail_dir)
            create_thumbnail_sprite(thumbnail_dir, result_dir)

        self.progress.update_progress(ProgressStage.COMPLETE, "Processing complete")

    def _process_video(self, video_path, file_hash):
        """Process a video from a local file for logo detection."""
        start_time = time.time()
        self.gpu_manager.reset_peak_memory_stats()

        result_dir = os.path.join(self.output_dir, file_hash)
        os.makedirs(result_dir, exist_ok=True)
        
        if not self._check_ffmpeg():
            error_msg = "ffmpeg command not found. Please ensure ffmpeg is installed and in your system's PATH."
            self.progress.update_progress(ProgressStage.ERROR, error_msg)
            print(error_msg)
            return

        raw_frames_dir = os.path.join(result_dir, 'frames_raw')
        os.makedirs(raw_frames_dir, exist_ok=True)
        
        try:
            frame_files = self._extract_frames(video_path, raw_frames_dir)
            total_frames = len(frame_files)
        except Exception as e:
            error_details = str(e)
            if "FFmpeg stderr:" in error_details:
                error_details = error_details.split("FFmpeg stderr:")[1].strip()
            error_msg = f"Failed during frame extraction: {error_details}"
            self.progress.update_progress(ProgressStage.ERROR, error_msg)
            print(f"Error in _process_video during frame extraction: {type(e).__name__}: {e}", file=sys.stderr)
            return
            
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            width_cap = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height_cap = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
        except Exception as e:
            self.progress.update_progress(ProgressStage.ERROR, f"Could not read video properties: {e}")
            fps, width_cap, height_cap = 25, 1920, 1080

        # Call the shared processing logic
        self._process_frames_in_parallel(file_hash, frame_files, total_frames, fps, width_cap, height_cap, start_time)

    def _save_timeseries_data(self, result_dir, filename, total_frames, data):
        try:
            output_data = {
                "frames_total": total_frames,
                "per_logo": {lg: [round(float(v), 4) for v in series] for lg, series in data.items()}
            }
            with open(os.path.join(result_dir, filename), 'w') as f:
                json.dump(output_data, f, indent=2)
        except Exception as e:
            print(f"Failed to write {filename}: {e}")

    def _is_url(self, path):
        """Check if a path is a URL"""
        return path.startswith('http://') or path.startswith('https://')
    
    def _process_video_stream(self, url, file_hash):
        """Process a video from a URL for logo detection using a frame-based workflow."""
        start_time = time.time()
        self.gpu_manager.reset_peak_memory_stats()

        url = self._resolve_hls_highest_variant(url)
        result_dir = os.path.join(self.output_dir, file_hash)
        os.makedirs(result_dir, exist_ok=True)
        
        if not self._check_ffmpeg():
            error_msg = "ffmpeg command not found. Please ensure ffmpeg is installed and in your system's PATH."
            self.progress.update_progress(ProgressStage.ERROR, error_msg)
            print(error_msg)
            return

        # Probe stream to get properties
        try:
            probe = subprocess.run([
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,r_frame_rate',
                '-of', 'json', url
            ], capture_output=True, text=True, timeout=10)
            info = json.loads(probe.stdout or '{}')
            width = int(info.get('streams', [{}])[0].get('width', 1280))
            height = int(info.get('streams', [{}])[0].get('height', 720))
            r_frame_rate = info.get('streams', [{}])[0].get('r_frame_rate', '25/1')
            num, den = (r_frame_rate.split('/') + ['1'])[:2]
            fps = float(num) / float(den) if float(den) != 0 else 25.0
        except Exception:
            width, height, fps = 1280, 720, 25.0

        raw_frames_dir = os.path.join(result_dir, 'frames_raw')
        os.makedirs(raw_frames_dir, exist_ok=True)

        try:
            frame_files = self._extract_frames(url, raw_frames_dir)
            total_frames = len(frame_files)
        except Exception as e:
            error_details = str(e)
            if "FFmpeg stderr:" in error_details:
                error_details = error_details.split("FFmpeg stderr:")[1].strip()
            error_msg = f"Failed during frame extraction from stream: {error_details}"
            self.progress.update_progress(ProgressStage.ERROR, error_msg)
            print(f"Error in _process_video_stream during frame extraction: {type(e).__name__}: {e}", file=sys.stderr)
            return

        # Call the shared processing logic
        self._process_frames_in_parallel(file_hash, frame_files, total_frames, fps, width, height, start_time)

    def _run_ffmpeg_reencode(self, input_path):
        """Helper to run ffmpeg for re-encoding a video file."""
        if not os.path.exists(input_path): return

        output_path = input_path.replace('.mp4', '_web.mp4')
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-level', '4.1',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            output_path
        ]
        result = subprocess.run(ffmpeg_cmd, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg error for {os.path.basename(input_path)}:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

    def _resolve_hls_highest_variant(self, url: str) -> str:
        """If URL is a master m3u8, select the highest-resolution (or bandwidth) variant."""
        try:
            resp = requests.get(url, timeout=10)
            text = resp.text
            if '#EXT-X-STREAM-INF' not in text:
                return url  # likely already a media playlist

            best_uri, best_pixels, best_bw = None, -1, -1
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if line.startswith('#EXT-X-STREAM-INF'):
                    attrs = line.split(':', 1)[1] if ':' in line else ''
                    bandwidth, width, height = -1, -1, -1
                    if 'BANDWIDTH' in attrs:
                        try: bandwidth = int(attrs.split('BANDWIDTH=')[1].split(',')[0])
                        except: pass
                    if 'RESOLUTION' in attrs:
                        try:
                            res = attrs.split('RESOLUTION=')[1].split(',')[0]
                            w, h = res.lower().split('x')
                            width, height = int(w), int(h)
                        except: pass
                    
                    j = i + 1
                    while j < len(lines) and (lines[j].startswith('#') or not lines[j].strip()):
                        j += 1
                    
                    if j < len(lines):
                        uri = lines[j].strip()
                        candidate = urljoin(url, uri)
                        pixels = width * height if width > 0 and height > 0 else -1
                        
                        if pixels > best_pixels or (pixels == -1 and best_pixels == -1 and bandwidth > best_bw):
                            best_pixels, best_bw, best_uri = pixels, bandwidth, candidate
            return best_uri or url
        except Exception:
            return url
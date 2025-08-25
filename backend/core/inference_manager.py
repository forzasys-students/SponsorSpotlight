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
from urllib.parse import urljoin
from collections import defaultdict, Counter
import time
from ultralytics import YOLO

from backend.utils.progress_manager import ProgressManager, ProgressStage
from backend.utils.gpu_manager import GPUManager
from backend.utils.annotator import FrameAnnotator
from backend.utils.stats_calculator import StatisticsCalculator

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
        try:
            with open(os.path.join(self.base_dir, 'pipeline_config.json'), 'r') as f:
                cfg = json.load(f) or {}
                self.generate_videos = bool(cfg.get('generate_videos', True))
                self.convert_h264 = bool(cfg.get('convert_h264', True))
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
    
    def _process_video(self, video_path, file_hash):
        """Process a video for logo detection"""
        start_time = time.time()
        self.gpu_manager.reset_peak_memory_stats()

        # Create a dedicated directory for the results
        result_dir = os.path.join(self.output_dir, file_hash)
        os.makedirs(result_dir, exist_ok=True)
        
        # Generate output paths within the new directory
        output_path = os.path.join(result_dir, 'output.mp4')
        raw_path = os.path.join(result_dir, 'raw.mp4')
        stats_file = os.path.join(result_dir, 'stats.json')
        timeline_stats_file = os.path.join(result_dir, 'timeline_stats.json')
        
        # Open the video
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        width_cap = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height_cap = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Conditionally create video writers
        out, raw_out = None, None
        if self.generate_videos:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width_cap, height_cap))
            raw_out = cv2.VideoWriter(raw_path, fourcc, fps, (width_cap, height_cap))
            if not out.isOpened() or not raw_out.isOpened():
                raise RuntimeError("Failed to create video writers")

        # Get video properties
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        stats_calculator = StatisticsCalculator(self.class_names, self.logo_groups, total_frames, fps)
        
        self.progress.update_progress(
            ProgressStage.INFERENCE_PROGRESS,
            "Processing video",
            frame=0,
            total_frames=total_frames,
            progress_percentage=0
        )
        
        # Prepare per-frame detections JSONL writer
        detections_jsonl_path = os.path.join(result_dir, 'frame_detections.jsonl')
        with open(detections_jsonl_path, 'w') as detections_writer:
            # Process each frame
            detection_start = time.time()
            self.gpu_manager.start_sampling()
            
            frame_count = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_count += 1
                results = self.model(frame)
                
                per_frame_detections = stats_calculator.process_frame(frame_count, frame, results)

                # Write per-frame detections line (time in seconds)
                detections_writer.write(json.dumps({
                    "frame": frame_count,
                    "time": round(frame_count * stats_calculator.frame_time, 3),
                    "detections": per_frame_detections
                }) + "\n")

                # Write raw frame then annotated frame (optional)
                if raw_out is not None:
                    raw_out.write(frame)
                if out is not None:
                    annotated_frame = self.annotator.annotate_frame(frame, results)
                    out.write(annotated_frame)
                
                # Update progress
                progress_percentage = (frame_count / total_frames) * 100 if total_frames > 0 else 0
                self.progress.update_progress(
                    ProgressStage.INFERENCE_PROGRESS,
                    f"Processing frame {frame_count}/{total_frames} ({round(progress_percentage)}%)",
                    frame=frame_count,
                    total_frames=total_frames,
                    progress_percentage=progress_percentage,
                    gpu_peak_mb=self.gpu_manager.get_peak_memory_allocated_mb()
                )
        
        # Clean up
        cap.release()
        if out is not None: out.release()
        if raw_out is not None: raw_out.release()
        
        detection_end = time.time()
        self.gpu_manager.stop_sampling()
        
        # Re-encode videos to H.264 using FFmpeg for browser compatibility (optional)
        if self.generate_videos and self.convert_h264:
            self.progress.update_progress(ProgressStage.POST_PROCESSING, "Converting videos to H.264 format")
            try:
                self._run_ffmpeg_reencode(output_path)
                self._run_ffmpeg_reencode(raw_path)
            except Exception as e:
                print(f"Error during video re-encoding: {e}")
        
        # Finalize statistics
        self.progress.update_progress(ProgressStage.POST_PROCESSING, "Aggregating statistics")
        
        final_stats, frame_by_frame_detections, coverage_per_frame, prominence_per_frame = stats_calculator.finalize_stats()
        
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

        # Save aggregated statistics
        with open(stats_file, "w") as f:
            json.dump(output_data, f, indent=4)

        # Save frame-by-frame statistics
        with open(timeline_stats_file, "w") as f:
            json.dump(frame_by_frame_detections, f)

        # Save coverage and prominence data
        self._save_timeseries_data(result_dir, 'coverage_per_frame.json', total_frames, coverage_per_frame)
        self._save_timeseries_data(result_dir, 'prominence_per_frame.json', total_frames, prominence_per_frame)
        
        # Update progress
        self.progress.update_progress(ProgressStage.COMPLETE, "Processing complete")

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
        # This method has a lot of duplicated logic with _process_video.
        # For this refactoring, I will leave it as is, but it's a candidate for a future cleanup
        # to merge the common logic. The main difference is reading frames from ffmpeg pipe vs. cv2.VideoCapture.
        
        start_time = time.time()
        self.gpu_manager.reset_peak_memory_stats()
        
        # Resolve to highest-quality variant if this is a master HLS playlist
        url = self._resolve_hls_highest_variant(url)
        # Create a dedicated directory for the results
        result_dir = os.path.join(self.output_dir, file_hash)
        os.makedirs(result_dir, exist_ok=True)
        
        # Generate output paths within the new directory
        output_path = os.path.join(result_dir, 'output.mp4')
        raw_path = os.path.join(result_dir, 'raw.mp4')
        stats_file = os.path.join(result_dir, 'stats.json')
        timeline_stats_file = os.path.join(result_dir, 'timeline_stats.json')

        # Probe stream
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

        # Try to estimate total duration from media playlist if available (for better progress)
        estimated_total_frames = None
        try:
            pl = requests.get(url, timeout=10).text
            if '#EXTINF' in pl:
                total_sec = sum(float(line.split(':', 1)[1].split(',')[0]) for line in pl.splitlines() if line.startswith('#EXTINF:'))
                if total_sec > 0 and fps > 0:
                    estimated_total_frames = int(total_sec * fps)
        except Exception:
            pass

        # Start ffmpeg pipe
        ffmpeg_cmd = [
            'ffmpeg', '-i', url, '-f', 'image2pipe', '-pix_fmt', 'bgr24', '-vcodec', 'rawvideo', '-'
        ]
        pipe = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)

        # Conditionally create video writers
        out, raw_out = None, None
        if self.generate_videos:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            raw_out = cv2.VideoWriter(raw_path, fourcc, fps, (width, height))
            if not out.isOpened() or not raw_out.isOpened():
                raise RuntimeError("Failed to create video writers")

        # The frame processing loop for streams is very similar to file-based videos.
        # This is a good candidate for future refactoring to reduce duplication.
        # For now, we keep it separate to ensure no functionality is broken.
        
        frame_count = 0
        stats_calculator = StatisticsCalculator(self.class_names, self.logo_groups, estimated_total_frames or 0, fps)
        
        self.progress.update_progress(
            ProgressStage.INFERENCE_PROGRESS, "Processing stream",
            frame=frame_count, total_frames=estimated_total_frames, progress_percentage=0
        )
        
        detections_jsonl_path = os.path.join(result_dir, 'frame_detections.jsonl')
        with open(detections_jsonl_path, 'w') as detections_writer:
            detection_start = time.time()
            self.gpu_manager.start_sampling()

            while True:
                raw = pipe.stdout.read(width * height * 3)
                if not raw:
                    break
                frame = np.frombuffer(raw, dtype='uint8').reshape((height, width, 3))
                frame_count += 1

                results = self.model(frame)
                
                per_frame_detections = stats_calculator.process_frame(frame_count, frame, results)

                detections_writer.write(json.dumps({
                    "frame": frame_count,
                    "time": round(frame_count * stats_calculator.frame_time, 3),
                    "detections": per_frame_detections
                }) + "\n")

                if raw_out is not None:
                    raw_out.write(frame)
                if out is not None:
                    annotated_frame = self.annotator.annotate_frame(frame, results)
                    out.write(annotated_frame)

                progress_pct = (frame_count / estimated_total_frames * 100) if estimated_total_frames else 0
                progress_pct = min(100, max(0, progress_pct))
                
                self.progress.update_progress(
                    ProgressStage.INFERENCE_PROGRESS,
                    f"Processing frame {frame_count}{f' (~{round(progress_pct)}%)' if estimated_total_frames else ''}",
                    frame=frame_count,
                    total_frames=estimated_total_frames,
                    progress_percentage=progress_pct,
                    gpu_peak_mb=self.gpu_manager.get_peak_memory_allocated_mb()
                )

            pipe.stdout.close()
            pipe.wait()
        
        if out: out.release()
        if raw_out: raw_out.release()
        
        detection_end = time.time()
        self.gpu_manager.stop_sampling()
        
        if self.generate_videos and self.convert_h264:
            self.progress.update_progress(ProgressStage.POST_PROCESSING, "Re-encoding video for web playback")
            try:
                self._run_ffmpeg_reencode(output_path)
                self._run_ffmpeg_reencode(raw_path)
            except Exception as e:
                print(f"Error during video re-encoding: {e}")

        # Finalize statistics, now using the actual frame count
        stats_calculator.total_frames = frame_count
        stats_calculator.total_video_time = frame_count * stats_calculator.frame_time
        final_stats, frame_by_frame_detections, coverage_per_frame, prominence_per_frame = stats_calculator.finalize_stats()
        
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
                "total_frames": frame_count,
                "width": width,
                "height": height
            },
            "logo_stats": final_stats,
            "processing_info": processing_info
        }
        with open(stats_file, "w") as f:
            json.dump(output_data, f, indent=4)
        with open(timeline_stats_file, "w") as f:
            json.dump(frame_by_frame_detections, f)

        self._save_timeseries_data(result_dir, 'coverage_per_frame.json', frame_count, coverage_per_frame)
        self._save_timeseries_data(result_dir, 'prominence_per_frame.json', frame_count, prominence_per_frame)
        
        self.progress.update_progress(ProgressStage.COMPLETE, "Processing complete")

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
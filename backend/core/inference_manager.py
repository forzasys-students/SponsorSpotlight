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
        raw_path = os.path.join(result_dir, 'raw.mp4')
        stats_file = os.path.join(result_dir, 'stats.json')
        timeline_stats_file = os.path.join(result_dir, 'timeline_stats.json')
        
        # Open the video
        cap = cv2.VideoCapture(video_path)
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        fps = cap.get(cv2.CAP_PROP_FPS)
        width_cap = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height_cap = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out = cv2.VideoWriter(output_path, fourcc, fps, (width_cap, height_cap))
        raw_out = cv2.VideoWriter(raw_path, fourcc, fps, (width_cap, height_cap))
        
        # Get video properties
        frame_time = 1 / fps if fps > 0 else 0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        total_video_time = total_frames / fps if fps > 0 else 0
        frame_count = 0
        
        # Initialize statistics tracking
        # sum_coverage_present accumulates per-frame coverage only for frames where the logo is present
        # max_coverage tracks the maximum single-frame coverage observed
        aggregated_stats = defaultdict(lambda: {
            "frames": 0,
            "time": 0.0,
            "detections": 0,
            "sum_coverage_present": 0.0,
            "max_coverage": 0.0,
            "sum_area_present_px": 0.0,
            # Prominence accumulators (MVP)
            "sum_prominence_present": 0.0,
            "max_prominence": 0.0,
            "high_prominence_time": 0.0,
            # Share of Voice accumulators
            "sum_share_of_voice_present": 0.0,
            "solo_time": 0.0
        })
        frame_by_frame_detections = defaultdict(list)
        # Per-frame coverage series: percentage per frame for each logo (0 when absent)
        coverage_per_frame = defaultdict(list)
        
        self.progress.update_progress(
            ProgressStage.INFERENCE_PROGRESS,
            "Processing video",
            frame=frame_count,
            total_frames=total_frames,
            progress_percentage=0
        )
        
        # Prepare per-frame detections JSONL writer
        detections_jsonl_path = os.path.join(result_dir, 'frame_detections.jsonl')
        detections_writer = open(detections_jsonl_path, 'w')
        
        # Process each frame
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            results = self.model(frame)
            
            logos_in_frame = Counter()
            main_logos_in_frame = set()
            # Accumulate pixel area for each main logo detected in this frame
            logo_area_pixels_in_frame = defaultdict(float)

            # Count logo detections in the frame and compute coverage areas
            per_frame_detections = []
            # Per-frame per-brand prominence (max over detections of that brand)
            per_brand_prominence_frame = defaultdict(float)
            # Track unique brands per frame for Share of Voice calculation
            unique_brands_in_frame = set()
            
            for result in results:
                if result.obb is None:
                    continue
                
                obb = result.obb
                for i in range(len(obb.conf)):
                    cls = int(obb.cls[i])
                    class_name = self.class_names[cls]
                    logos_in_frame[class_name] += 1
                    # Track unique brands for Share of Voice
                    unique_brands_in_frame.add(self.logo_groups.get(class_name, class_name))

                    # Compute oriented bounding box area in pixels
                    if hasattr(obb, 'xyxyxyxy'):
                        polygon = obb.xyxyxyxy[i]
                        if hasattr(polygon, 'cpu'):
                            polygon = polygon.cpu().numpy()
                        points = polygon.reshape(4, 2).astype(np.float32)

                        # Scale normalized coordinates to pixel coordinates if needed
                        is_normalized = np.all(points <= 1.0)
                        if is_normalized:
                            points[:, 0] *= frame.shape[1]
                            points[:, 1] *= frame.shape[0]

                        # Clamp to frame bounds just in case
                        points[:, 0] = np.clip(points[:, 0], 0, frame.shape[1])
                        points[:, 1] = np.clip(points[:, 1], 0, frame.shape[0])

                        area_px = float(cv2.contourArea(points)) if points.shape == (4, 2) else 0.0
                        if area_px > 0:
                            main_logo_for_area = self.logo_groups.get(class_name, class_name)
                            logo_area_pixels_in_frame[main_logo_for_area] += area_px

                            # Compute MVP prominence score for this detection (center proximity + size)
                            try:
                                W = float(frame.shape[1])
                                H = float(frame.shape[0])
                                cx = float(points[:, 0].mean())
                                cy = float(points[:, 1].mean())
                                area_ratio = max(0.0, min(1.0, area_px / (W * H) if (W > 0 and H > 0) else 0.0))
                                sigma_x = 0.3 * W
                                sigma_y = 0.3 * H
                                if sigma_x <= 0 or sigma_y <= 0:
                                    p_center = 0.0
                                else:
                                    p_center = math.exp(-(((cx - (W / 2.0)) ** 2) / (2.0 * (sigma_x ** 2)) + ((cy - (H / 2.0)) ** 2) / (2.0 * (sigma_y ** 2))))
                                p_size = math.sqrt(area_ratio)
                                prominence_score = 0.6 * p_center + 0.4 * p_size
                                if prominence_score > per_brand_prominence_frame[main_logo_for_area]:
                                    per_brand_prominence_frame[main_logo_for_area] = prominence_score
                            except Exception:
                                pass

                        # Collect detection polygon/bbox for advanced overlays
                        polygon_list = points.tolist()
                        xs = [p[0] for p in polygon_list]
                        ys = [p[1] for p in polygon_list]
                        bbox = [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]
                        per_frame_detections.append({
                            "class": self.logo_groups.get(class_name, class_name),
                            "polygon": polygon_list,
                            "bbox": bbox
                        })

            # Aggregate stats for the current frame
            for logo, count in logos_in_frame.items():
                main_logo = self.logo_groups.get(logo, logo)
                aggregated_stats[main_logo]["detections"] += count
                main_logos_in_frame.add(main_logo)
            
            # Update frame-based stats for unique main logos in the frame
            # Update frame/time counts and coverage-based metrics for logos present in this frame
            frame_area = float(frame.shape[0] * frame.shape[1]) if frame is not None else 0.0
            # Prepare to record per-frame coverage series
            present_logos_this_frame = set()
            prominence_high_threshold = 0.6
            for main_logo in main_logos_in_frame:
                aggregated_stats[main_logo]["frames"] += 1
                aggregated_stats[main_logo]["time"] += frame_time
                frame_by_frame_detections[main_logo].append(frame_count)

                # Compute coverage ratio for this main logo in the frame (sum of all instances, capped at 1.0)
                if frame_area > 0:
                    logo_area = logo_area_pixels_in_frame.get(main_logo, 0.0)
                    coverage_ratio = min(1.0, logo_area / frame_area)
                    aggregated_stats[main_logo]["sum_coverage_present"] += coverage_ratio
                    aggregated_stats[main_logo]["sum_area_present_px"] += logo_area
                    if coverage_ratio > aggregated_stats[main_logo]["max_coverage"]:
                        aggregated_stats[main_logo]["max_coverage"] = coverage_ratio
                    # Ensure backfill for new logos
                    while len(coverage_per_frame[main_logo]) < (frame_count - 1):
                        coverage_per_frame[main_logo].append(0.0)
                    coverage_per_frame[main_logo].append(round(coverage_ratio * 100.0, 4))
                    present_logos_this_frame.add(main_logo)

                # Accumulate prominence for this brand in this frame if computed
                if main_logo in per_brand_prominence_frame:
                    s = float(per_brand_prominence_frame.get(main_logo, 0.0))
                    aggregated_stats[main_logo]["sum_prominence_present"] += s
                    if s > aggregated_stats[main_logo]["max_prominence"]:
                        aggregated_stats[main_logo]["max_prominence"] = s
                    if s >= prominence_high_threshold:
                        aggregated_stats[main_logo]["high_prominence_time"] += frame_time

                # Calculate Share of Voice for this brand in this frame
                if main_logo in unique_brands_in_frame:
                    # Count other unique brands in this frame (excluding current brand)
                    other_brands_count = len(unique_brands_in_frame - {main_logo})
                    # Share of Voice = 1 / (1 + number_of_competitors)
                    share_of_voice = 1.0 / (1.0 + other_brands_count)
                    aggregated_stats[main_logo]["sum_share_of_voice_present"] += share_of_voice
                    
                    # Track solo time (when brand appears alone)
                    if other_brands_count == 0:
                        aggregated_stats[main_logo]["solo_time"] += frame_time

            # For logos not present in this frame, append 0 to keep series aligned
            for lg in list(coverage_per_frame.keys()):
                if lg not in present_logos_this_frame:
                    while len(coverage_per_frame[lg]) < (frame_count - 1):
                        coverage_per_frame[lg].append(0.0)
                    coverage_per_frame[lg].append(0.0)

            # Periodic debug logging per 25 frames
            if frame_count % 25 == 0 and frame_area > 0 and logo_area_pixels_in_frame:
                debug_msg_parts = [f"Frame {frame_count} coverage:"]
                for lg, area_px in logo_area_pixels_in_frame.items():
                    cov_pct = (area_px / frame_area) * 100.0
                    debug_msg_parts.append(f"{lg}={cov_pct:.3f}% ({int(area_px)}px of {int(frame_area)}px)")
                print(" | ".join(debug_msg_parts))

            # Write per-frame detections line (time in seconds)
            try:
                detections_writer.write(json.dumps({
                    "frame": frame_count,
                    "time": round(frame_count * frame_time, 3),
                    "detections": per_frame_detections
                }) + "\n")
            except Exception:
                pass

            # Write raw frame then annotated frame
            raw_out.write(frame)
            annotated_frame = self._annotate_frame(frame, results)
            out.write(annotated_frame)
            
            # Update progress
            progress_percentage = (frame_count / total_frames) * 100 if total_frames > 0 else 0
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
        raw_out.release()
        try:
            detections_writer.close()
        except Exception:
            pass
        
        # Finalize statistics
        self.progress.update_progress(
            ProgressStage.POST_PROCESSING,
            "Aggregating statistics"
        )
        
        # Calculate percentages and coverage metrics, then round values
        final_stats = {}
        for logo, stats in aggregated_stats.items():
            time_value = round(stats["time"], 2)
            frames_present = stats["frames"]
            sum_cov_present = stats.get("sum_coverage_present", 0.0)
            max_cov = stats.get("max_coverage", 0.0)
            sum_prom_present = stats.get("sum_prominence_present", 0.0)
            max_prom = stats.get("max_prominence", 0.0)
            high_prom_time = stats.get("high_prominence_time", 0.0)

            percentage_time = (time_value / total_video_time * 100) if total_video_time > 0 else 0
            avg_cov_present = (sum_cov_present / frames_present * 100) if frames_present > 0 else 0.0
            avg_cov_overall = (sum_cov_present / total_frames * 100) if total_frames > 0 else 0.0
            avg_prom_present = (sum_prom_present / frames_present * 100) if frames_present > 0 else 0.0

            # Filter out brands with less than 30 detections to reduce false positives
            if stats["detections"] >= 30:
                final_stats[logo] = {
                    "frames": frames_present,
                    "time": min(time_value, total_video_time),
                    "detections": stats["detections"],
                    "percentage": round(percentage_time, 2),
                    "coverage_avg_present": round(avg_cov_present, 2),
                    "coverage_avg_overall": round(avg_cov_overall, 2),
                    "coverage_max": round(max_cov * 100, 2),
                    "prominence_avg_present": round(avg_prom_present, 2),
                    "prominence_max": round(max_prom * 100, 2),
                    "prominence_high_time": round(high_prom_time, 2)
                }

        # Prepare final JSON output with metadata
        output_data = {
            "video_metadata": {
                "duration": round(total_video_time, 2),
                "fps": round(fps, 2),
                "total_frames": total_frames,
                "width": width_cap,
                "height": height_cap
            },
            "logo_stats": final_stats
        }

        # Save aggregated statistics
        with open(stats_file, "w") as f:
            json.dump(output_data, f, indent=4)

        # Save frame-by-frame statistics
        with open(timeline_stats_file, "w") as f:
            json.dump(frame_by_frame_detections, f)

        # Save coverage debug information for validation
        try:
            coverage_debug = {
                "resolution": {
                    "width": output_data["video_metadata"]["width"],
                    "height": output_data["video_metadata"]["height"],
                    "frame_area": output_data["video_metadata"]["width"] * output_data["video_metadata"]["height"]
                },
                "frames_total": total_frames,
                "per_logo": {}
            }
            frame_area_dbg = float(coverage_debug["resolution"]["frame_area"]) if coverage_debug["resolution"]["frame_area"] else 0.0
            for logo, stats in aggregated_stats.items():
                frames_present = stats["frames"]
                sum_area_px = stats.get("sum_area_present_px", 0.0)
                sum_cov = stats.get("sum_coverage_present", 0.0)
                max_cov = stats.get("max_coverage", 0.0)
                coverage_debug["per_logo"][logo] = {
                    "frames_present": frames_present,
                    "sum_area_present_px": round(float(sum_area_px), 2),
                    "avg_area_present_px": round(float(sum_area_px / frames_present), 2) if frames_present > 0 else 0.0,
                    "avg_coverage_present_pct": round(float((sum_cov / frames_present) * 100.0), 3) if frames_present > 0 else 0.0,
                    "avg_coverage_overall_pct": round(float((sum_cov / total_frames) * 100.0), 3) if total_frames > 0 else 0.0,
                    "max_coverage_pct": round(float(max_cov * 100.0), 3),
                    "frame_area_px": int(frame_area_dbg)
                }
            coverage_debug_file = os.path.join(result_dir, 'coverage_debug.json')
            with open(coverage_debug_file, 'w') as f:
                json.dump(coverage_debug, f, indent=2)

            # Save per-frame coverage series (percentages per frame, 0 when absent)
            for lg, series in coverage_per_frame.items():
                # Backfill series to total_frames if needed
                while len(series) < total_frames:
                    series.append(0.0)
            coverage_series = {
                "frames_total": total_frames,
                "per_logo": {lg: [round(float(v), 4) for v in series] for lg, series in coverage_per_frame.items()}
            }
            coverage_series_file = os.path.join(result_dir, 'coverage_per_frame.json')
            with open(coverage_series_file, 'w') as f:
                json.dump(coverage_series, f, indent=2)
        except Exception as e:
            print(f"Failed to write coverage_debug.json: {e}")
        
        # Update progress
        self.progress.update_progress(
            ProgressStage.COMPLETE,
            "Processing complete"
        )
    
    def _is_url(self, path):
        """Check if a path is a URL"""
        return path.startswith('http://') or path.startswith('https://')
    
    def _process_video_stream(self, url, file_hash):
        """Process a video stream (e.g., m3u8) by piping frames via ffmpeg."""
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
                total_sec = 0.0
                for line in pl.splitlines():
                    line = line.strip()
                    if line.startswith('#EXTINF:'):
                        try:
                            dur = float(line.split(':', 1)[1].split(',')[0])
                            total_sec += dur
                        except Exception:
                            pass
                if total_sec > 0 and fps > 0:
                    estimated_total_frames = int(total_sec * fps)
        except Exception:
            pass

        # Start ffmpeg pipe
        ffmpeg_cmd = [
            'ffmpeg', '-i', url, '-f', 'image2pipe', '-pix_fmt', 'bgr24', '-vcodec', 'rawvideo', '-'
        ]
        pipe = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)

        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        raw_out = cv2.VideoWriter(raw_path, fourcc, fps, (width, height))

        frame_time = 1 / fps
        frame_count = 0

        # Stats with coverage fields (mirror file video processing)
        aggregated_stats = defaultdict(lambda: {
            "frames": 0,
            "time": 0.0,
            "detections": 0,
            "sum_coverage_present": 0.0,
            "max_coverage": 0.0,
            "sum_area_present_px": 0.0,
            # Prominence accumulators (MVP)
            "sum_prominence_present": 0.0,
            "max_prominence": 0.0,
            "high_prominence_time": 0.0,
            # Share of Voice accumulators
            "sum_share_of_voice_present": 0.0,
            "solo_time": 0.0
        })
        frame_by_frame_detections = defaultdict(list)
        coverage_per_frame = defaultdict(list)

        self.progress.update_progress(
            ProgressStage.INFERENCE_PROGRESS,
            "Processing stream",
            frame=frame_count,
            total_frames=estimated_total_frames,
            progress_percentage=0
        )

        # Prepare per-frame detections JSONL
        detections_jsonl_path = os.path.join(result_dir, 'frame_detections.jsonl')
        try:
            detections_writer = open(detections_jsonl_path, 'w')
        except Exception:
            detections_writer = None

        while True:
            raw = pipe.stdout.read(width * height * 3)
            if not raw:
                break
            frame = np.frombuffer(raw, dtype='uint8').reshape((height, width, 3))
            frame_count += 1

            results = self.model(frame)

            logos_in_frame = Counter()
            main_logos_in_frame = set()
            logo_area_pixels_in_frame = defaultdict(float)
            per_frame_detections = []
            # Per-frame per-brand prominence (max over detections of that brand)
            per_brand_prominence_frame = defaultdict(float)
            # Track unique brands per frame for Share of Voice calculation
            unique_brands_in_frame = set()

            for result in results:
                if result.obb is None:
                    continue
                obb = result.obb
                for i in range(len(obb.conf)):
                    cls = int(obb.cls[i])
                    class_name = self.class_names[cls]
                    logos_in_frame[class_name] += 1
                    # Track unique brands for Share of Voice
                    unique_brands_in_frame.add(self.logo_groups.get(class_name, class_name))
                    if hasattr(obb, 'xyxyxyxy'):
                        polygon = obb.xyxyxyxy[i]
                        if hasattr(polygon, 'cpu'):
                            polygon = polygon.cpu().numpy()
                        points = polygon.reshape(4, 2).astype(np.float32)
                        is_normalized = np.all(points <= 1.0)
                        if is_normalized:
                            points[:, 0] *= frame.shape[1]
                            points[:, 1] *= frame.shape[0]
                        points[:, 0] = np.clip(points[:, 0], 0, frame.shape[1])
                        points[:, 1] = np.clip(points[:, 1], 0, frame.shape[0])
                        area_px = float(cv2.contourArea(points)) if points.shape == (4, 2) else 0.0
                        if area_px > 0:
                            main_logo_for_area = self.logo_groups.get(class_name, class_name)
                            logo_area_pixels_in_frame[main_logo_for_area] += area_px
                            # Compute MVP prominence score for this detection
                            try:
                                W = float(frame.shape[1])
                                H = float(frame.shape[0])
                                cx = float(points[:, 0].mean())
                                cy = float(points[:, 1].mean())
                                area_ratio = max(0.0, min(1.0, area_px / (W * H) if (W > 0 and H > 0) else 0.0))
                                sigma_x = 0.3 * W
                                sigma_y = 0.3 * H
                                if sigma_x <= 0 or sigma_y <= 0:
                                    p_center = 0.0
                                else:
                                    p_center = math.exp(-(((cx - (W / 2.0)) ** 2) / (2.0 * (sigma_x ** 2)) + ((cy - (H / 2.0)) ** 2) / (2.0 * (sigma_y ** 2))))
                                p_size = math.sqrt(area_ratio)
                                prominence_score = 0.6 * p_center + 0.4 * p_size
                                if prominence_score > per_brand_prominence_frame[main_logo_for_area]:
                                    per_brand_prominence_frame[main_logo_for_area] = prominence_score
                            except Exception:
                                pass
                        # Collect polygon/bbox for overlays
                        try:
                            poly_list = points.tolist()
                            xs = [p[0] for p in poly_list]
                            ys = [p[1] for p in poly_list]
                            bbox = [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]
                            per_frame_detections.append({
                                "class": self.logo_groups.get(class_name, class_name),
                                "polygon": poly_list,
                                "bbox": bbox
                            })
                        except Exception:
                            pass

            for logo, count in logos_in_frame.items():
                main_logo = self.logo_groups.get(logo, logo)
                aggregated_stats[main_logo]["detections"] += count
                main_logos_in_frame.add(main_logo)

            frame_area = float(frame.shape[0] * frame.shape[1]) if frame is not None else 0.0
            present_logos_this_frame = set()
            prominence_high_threshold = 0.6
            for main_logo in main_logos_in_frame:
                aggregated_stats[main_logo]["frames"] += 1
                aggregated_stats[main_logo]["time"] += frame_time
                frame_by_frame_detections[main_logo].append(frame_count)
                if frame_area > 0:
                    logo_area = logo_area_pixels_in_frame.get(main_logo, 0.0)
                    coverage_ratio = min(1.0, logo_area / frame_area)
                    aggregated_stats[main_logo]["sum_coverage_present"] += coverage_ratio
                    aggregated_stats[main_logo]["sum_area_present_px"] += logo_area
                    if coverage_ratio > aggregated_stats[main_logo]["max_coverage"]:
                        aggregated_stats[main_logo]["max_coverage"] = coverage_ratio
                    while len(coverage_per_frame[main_logo]) < (frame_count - 1):
                        coverage_per_frame[main_logo].append(0.0)
                    coverage_per_frame[main_logo].append(round(coverage_ratio * 100.0, 4))
                    present_logos_this_frame.add(main_logo)

                # Accumulate prominence per frame for this brand if available
                if main_logo in per_brand_prominence_frame:
                    s = float(per_brand_prominence_frame.get(main_logo, 0.0))
                    aggregated_stats[main_logo]["sum_prominence_present"] += s
                    if s > aggregated_stats[main_logo]["max_prominence"]:
                        aggregated_stats[main_logo]["max_prominence"] = s
                    if s >= prominence_high_threshold:
                        aggregated_stats[main_logo]["high_prominence_time"] += frame_time

                # Calculate Share of Voice for this brand in this frame
                if main_logo in unique_brands_in_frame:
                    # Count other unique brands in this frame (excluding current brand)
                    other_brands_count = len(unique_brands_in_frame - {main_logo})
                    # Share of Voice = 1 / (1 + number_of_competitors)
                    share_of_voice = 1.0 / (1.0 + other_brands_count)
                    aggregated_stats[main_logo]["sum_share_of_voice_present"] += share_of_voice
                    
                    # Track solo time (when brand appears alone)
                    if other_brands_count == 0:
                        aggregated_stats[main_logo]["solo_time"] += frame_time

            for lg in list(coverage_per_frame.keys()):
                if lg not in present_logos_this_frame:
                    while len(coverage_per_frame[lg]) < (frame_count - 1):
                        coverage_per_frame[lg].append(0.0)
                    coverage_per_frame[lg].append(0.0)

            # Write raw frame and annotated frame
            raw_out.write(frame)
            # Write per-frame detections JSONL
            if detections_writer is not None:
                try:
                    detections_writer.write(json.dumps({
                        "frame": frame_count,
                        "time": round(frame_count * frame_time, 3),
                        "detections": per_frame_detections
                    }) + "\n")
                except Exception:
                    pass

            annotated_frame = self._annotate_frame(frame, results)
            out.write(annotated_frame)

            # Update progress percentage if we know estimated_total_frames
            progress_pct = (frame_count / estimated_total_frames * 100) if estimated_total_frames else 0
            # Clamp to [0, 100]
            if progress_pct < 0:
                progress_pct = 0
            elif progress_pct > 100:
                progress_pct = 100
            msg_suffix = f" (~{round(progress_pct)}%)" if estimated_total_frames else ""
            self.progress.update_progress(
                ProgressStage.INFERENCE_PROGRESS,
                f"Processing frame {frame_count}{msg_suffix}",
                frame=frame_count,
                total_frames=estimated_total_frames,
                progress_percentage=progress_pct
            )

        pipe.stdout.close()
        pipe.wait()
        out.release()
        raw_out.release()
        try:
            if detections_writer is not None:
                detections_writer.close()
        except Exception:
            pass

        total_frames = frame_count
        total_video_time = total_frames * frame_time

        self.progress.update_progress(
            ProgressStage.POST_PROCESSING,
            "Aggregating statistics"
        )

        final_stats = {}
        for logo, stats in aggregated_stats.items():
            time_value = round(stats["time"], 2)
            frames_present = stats["frames"]
            sum_cov_present = stats.get("sum_coverage_present", 0.0)
            max_cov = stats.get("max_coverage", 0.0)
            sum_prom_present = stats.get("sum_prominence_present", 0.0)
            max_prom = stats.get("max_prominence", 0.0)
            high_prom_time = stats.get("high_prominence_time", 0.0)
            sum_sov_present = stats.get("sum_share_of_voice_present", 0.0)
            solo_time = stats.get("solo_time", 0.0)
            percentage_time = (time_value / total_video_time * 100) if total_video_time > 0 else 0
            avg_cov_present = (sum_cov_present / frames_present * 100) if frames_present > 0 else 0.0
            avg_cov_overall = (sum_cov_present / total_frames * 100) if total_frames > 0 else 0.0
            avg_prom_present = (sum_prom_present / frames_present * 100) if frames_present > 0 else 0.0
            avg_sov_present = (sum_sov_present / frames_present * 100) if frames_present > 0 else 0.0
            solo_percentage = (solo_time / time_value * 100) if time_value > 0 else 0.0

            # Filter out brands with less than 20 detections to reduce false positives
            if stats["detections"] >= 20:
                final_stats[logo] = {
                    "frames": frames_present,
                    "time": min(time_value, total_video_time),
                    "detections": stats["detections"],
                    "percentage": round(percentage_time, 2),
                    "coverage_avg_present": round(avg_cov_present, 2),
                    "coverage_avg_overall": round(avg_cov_overall, 2),
                    "coverage_max": round(max_cov * 100, 2),
                    "prominence_avg_present": round(avg_prom_present, 2),
                    "prominence_max": round(max_prom * 100, 2),
                    "prominence_high_time": round(high_prom_time, 2),
                    "share_of_voice_avg_present": round(avg_sov_present, 2),
                    "share_of_voice_solo_time": round(solo_time, 2),
                    "share_of_voice_solo_percentage": round(solo_percentage, 2)
                }

        output_data = {
            "video_metadata": {
                "duration": round(total_video_time, 2),
                "fps": round(fps, 2),
                "total_frames": total_frames,
                "width": width,
                "height": height
            },
            "logo_stats": final_stats
        }

        with open(stats_file, "w") as f:
            json.dump(output_data, f, indent=4)

        with open(timeline_stats_file, "w") as f:
            json.dump(frame_by_frame_detections, f)

        # Write coverage debug artifacts
        try:
            coverage_debug = {"resolution": {"width": width, "height": height, "frame_area": width * height}, "frames_total": total_frames, "per_logo": {}}
            frame_area_dbg = float(width * height)
            for logo, stats in aggregated_stats.items():
                frames_present = stats["frames"]
                sum_area_px = stats.get("sum_area_present_px", 0.0)
                sum_cov = stats.get("sum_coverage_present", 0.0)
                max_cov = stats.get("max_coverage", 0.0)
                coverage_debug["per_logo"][logo] = {
                    "frames_present": frames_present,
                    "sum_area_present_px": round(float(sum_area_px), 2),
                    "avg_area_present_px": round(float(sum_area_px / frames_present), 2) if frames_present > 0 else 0.0,
                    "avg_coverage_present_pct": round(float((sum_cov / frames_present) * 100.0), 3) if frames_present > 0 else 0.0,
                    "avg_coverage_overall_pct": round(float((sum_cov / total_frames) * 100.0), 3) if total_frames > 0 else 0.0,
                    "max_coverage_pct": round(float(max_cov * 100.0), 3),
                    "frame_area_px": int(frame_area_dbg)
                }
            with open(os.path.join(result_dir, 'coverage_debug.json'), 'w') as f:
                json.dump(coverage_debug, f, indent=2)
            for lg, series in coverage_per_frame.items():
                while len(series) < total_frames:
                    series.append(0.0)
            coverage_series = {"frames_total": total_frames, "per_logo": {lg: [round(float(v), 4) for v in series] for lg, series in coverage_per_frame.items()}}
            with open(os.path.join(result_dir, 'coverage_per_frame.json'), 'w') as f:
                json.dump(coverage_series, f, indent=2)
        except Exception as e:
            print(f"Failed to write coverage debug (stream): {e}")

        self.progress.update_progress(
            ProgressStage.COMPLETE,
            "Processing complete"
        )

    def _resolve_hls_highest_variant(self, url: str) -> str:
        """If URL is a master m3u8, select the highest-resolution (or bandwidth) variant."""
        try:
            resp = requests.get(url, timeout=10)
            text = resp.text
            if '#EXT-X-STREAM-INF' not in text:
                return url  # likely already a media playlist

            best_uri = None
            best_pixels = -1
            best_bw = -1
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if line.startswith('#EXT-X-STREAM-INF'):
                    attrs = line.split(':', 1)[1] if ':' in line else ''
                    bandwidth = -1
                    width = height = -1
                    for part in attrs.split(','):
                        if 'BANDWIDTH' in part:
                            try:
                                bandwidth = int(part.split('=')[1])
                            except Exception:
                                pass
                        if 'RESOLUTION' in part:
                            try:
                                res = part.split('=')[1]
                                w, h = res.lower().split('x')
                                width, height = int(w), int(h)
                            except Exception:
                                pass
                    # Next non-comment line should be the URI
                    j = i + 1
                    while j < len(lines) and lines[j].startswith('#'):
                        j += 1
                    if j < len(lines):
                        uri = lines[j].strip()
                        candidate = urljoin(url, uri)
                        pixels = (width * height) if width > 0 and height > 0 else -1
                        better = False
                        if pixels > best_pixels:
                            better = True
                        elif pixels == -1 and best_pixels == -1 and bandwidth > best_bw:
                            better = True
                        if better:
                            best_pixels = pixels
                            best_bw = bandwidth
                            best_uri = candidate
            return best_uri or url
        except Exception:
            return url
    
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
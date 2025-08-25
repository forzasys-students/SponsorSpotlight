import cv2
import numpy as np
import math
from collections import defaultdict, Counter

class StatisticsCalculator:
    def __init__(self, class_names, logo_groups, total_frames, fps):
        self.class_names = class_names
        self.logo_groups = logo_groups
        self.total_frames = total_frames
        self.fps = fps
        self.frame_time = 1 / fps if fps > 0 else 0
        self.total_video_time = total_frames / fps if fps > 0 else 0

        self.aggregated_stats = defaultdict(lambda: {
            "frames": 0, "time": 0.0, "detections": 0,
            "sum_coverage_present": 0.0, "max_coverage": 0.0, "sum_area_present_px": 0.0,
            "sum_prominence_present": 0.0, "max_prominence": 0.0, "high_prominence_time": 0.0,
            "sum_share_of_voice_present": 0.0, "solo_time": 0.0
        })
        self.frame_by_frame_detections = defaultdict(list)
        self.coverage_per_frame = defaultdict(list)
        self.prominence_per_frame = defaultdict(list)

    def process_frame(self, frame_count, frame, results):
        logos_in_frame = Counter()
        main_logos_in_frame = set()
        logo_area_pixels_in_frame = defaultdict(float)
        per_frame_detections = []
        per_brand_prominence_frame = defaultdict(float)
        unique_brands_in_frame = set()

        for result in results:
            if result.obb is None:
                continue
            
            obb = result.obb
            for i in range(len(obb.conf)):
                cls = int(obb.cls[i])
                class_name = self.class_names[cls]
                logos_in_frame[class_name] += 1
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

                        try:
                            W, H = float(frame.shape[1]), float(frame.shape[0])
                            cx, cy = float(points[:, 0].mean()), float(points[:, 1].mean())
                            area_ratio = max(0.0, min(1.0, area_px / (W * H) if (W > 0 and H > 0) else 0.0))
                            sigma_x, sigma_y = 0.3 * W, 0.3 * H
                            
                            p_center = 0.0
                            if sigma_x > 0 and sigma_y > 0:
                                p_center = math.exp(-(((cx - (W / 2.0)) ** 2) / (2.0 * (sigma_x ** 2)) + ((cy - (H / 2.0)) ** 2) / (2.0 * (sigma_y ** 2))))
                            
                            p_size = math.sqrt(area_ratio)
                            prominence_score = 0.6 * p_center + 0.4 * p_size
                            if prominence_score > per_brand_prominence_frame[main_logo_for_area]:
                                per_brand_prominence_frame[main_logo_for_area] = prominence_score
                        except Exception:
                            pass

                    polygon_list = points.tolist()
                    xs, ys = [p[0] for p in polygon_list], [p[1] for p in polygon_list]
                    bbox = [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]
                    per_frame_detections.append({
                        "class": self.logo_groups.get(class_name, class_name),
                        "polygon": polygon_list,
                        "bbox": bbox
                    })

        for logo, count in logos_in_frame.items():
            main_logo = self.logo_groups.get(logo, logo)
            self.aggregated_stats[main_logo]["detections"] += count
            main_logos_in_frame.add(main_logo)
        
        frame_area = float(frame.shape[0] * frame.shape[1]) if frame is not None else 0.0
        present_logos_this_frame = set()
        prominence_high_threshold = 0.6

        for main_logo in main_logos_in_frame:
            self.aggregated_stats[main_logo]["frames"] += 1
            self.aggregated_stats[main_logo]["time"] += self.frame_time
            self.frame_by_frame_detections[main_logo].append(frame_count)

            if frame_area > 0:
                logo_area = logo_area_pixels_in_frame.get(main_logo, 0.0)
                coverage_ratio = min(1.0, logo_area / frame_area)
                self.aggregated_stats[main_logo]["sum_coverage_present"] += coverage_ratio
                self.aggregated_stats[main_logo]["sum_area_present_px"] += logo_area
                if coverage_ratio > self.aggregated_stats[main_logo]["max_coverage"]:
                    self.aggregated_stats[main_logo]["max_coverage"] = coverage_ratio
                
                self._backfill_series(self.coverage_per_frame[main_logo], frame_count)
                self.coverage_per_frame[main_logo].append(round(coverage_ratio * 100.0, 4))
                present_logos_this_frame.add(main_logo)

            if main_logo in per_brand_prominence_frame:
                s = float(per_brand_prominence_frame.get(main_logo, 0.0))
                self.aggregated_stats[main_logo]["sum_prominence_present"] += s
                if s > self.aggregated_stats[main_logo]["max_prominence"]:
                    self.aggregated_stats[main_logo]["max_prominence"] = s
                if s >= prominence_high_threshold:
                    self.aggregated_stats[main_logo]["high_prominence_time"] += self.frame_time
                
                self._backfill_series(self.prominence_per_frame[main_logo], frame_count)
                self.prominence_per_frame[main_logo].append(round(s * 100.0, 2))

            if main_logo in unique_brands_in_frame:
                other_brands_count = len(unique_brands_in_frame - {main_logo})
                share_of_voice = 1.0 / (1.0 + other_brands_count)
                self.aggregated_stats[main_logo]["sum_share_of_voice_present"] += share_of_voice
                
                if other_brands_count == 0:
                    self.aggregated_stats[main_logo]["solo_time"] += self.frame_time

        for lg in list(self.coverage_per_frame.keys()):
            if lg not in present_logos_this_frame:
                self._backfill_series(self.coverage_per_frame[lg], frame_count)
                self.coverage_per_frame[lg].append(0.0)

        for lg in list(self.prominence_per_frame.keys()):
            if lg not in per_brand_prominence_frame:
                self._backfill_series(self.prominence_per_frame[lg], frame_count)
                self.prominence_per_frame[lg].append(0.0)
        
        return per_frame_detections

    def _backfill_series(self, series, frame_count):
        while len(series) < (frame_count - 1):
            series.append(0.0)

    def finalize_stats(self):
        final_stats = {}
        for logo, stats in self.aggregated_stats.items():
            time_value = round(stats["time"], 2)
            frames_present = stats["frames"]
            sum_cov_present = stats.get("sum_coverage_present", 0.0)
            max_cov = stats.get("max_coverage", 0.0)
            sum_prom_present = stats.get("sum_prominence_present", 0.0)
            max_prom = stats.get("max_prominence", 0.0)
            high_prom_time = stats.get("high_prominence_time", 0.0)

            percentage_time = (time_value / self.total_video_time * 100) if self.total_video_time > 0 else 0
            avg_cov_present = (sum_cov_present / frames_present * 100) if frames_present > 0 else 0.0
            avg_cov_overall = (sum_cov_present / self.total_frames * 100) if self.total_frames > 0 else 0.0
            avg_prom_present = (sum_prom_present / frames_present * 100) if frames_present > 0 else 0.0

            if stats["detections"] >= 50:
                final_stats[logo] = {
                    "frames": frames_present,
                    "time": min(time_value, self.total_video_time),
                    "detections": stats["detections"],
                    "percentage": round(percentage_time, 2),
                    "coverage_avg_present": round(avg_cov_present, 2),
                    "coverage_avg_overall": round(avg_cov_overall, 2),
                    "coverage_max": round(max_cov * 100, 2),
                    "prominence_avg_present": round(avg_prom_present, 2),
                    "prominence_max": round(max_prom * 100, 2),
                    "prominence_high_time": round(high_prom_time, 2)
                }
        
        for lg, series in self.coverage_per_frame.items():
            while len(series) < self.total_frames:
                series.append(0.0)
        
        for lg, series in self.prominence_per_frame.items():
            while len(series) < self.total_frames:
                series.append(0.0)

        return final_stats, self.frame_by_frame_detections, self.coverage_per_frame, self.prominence_per_frame

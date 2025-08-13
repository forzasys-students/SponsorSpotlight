from langchain_core.tools import tool
import os
import json
import cv2
import math
import numpy as np

# Reuse overlay utilities from the brand-specific clip tool
from backend.agent.tools.create_brand_clip_tool import (
    _normalize_brand,
    _load_detections_map,
    _draw_brand_overlays,
)


def _find_best_windows(coverage_series, fps: float, desired_total_sec: float, segment_sec: float = 1.0) -> list:
    """
    Pick top non-overlapping windows by average coverage.
    Returns list of (start_time, end_time) in seconds, sorted by start.
    """
    if not coverage_series or fps <= 0:
        return []
    window = max(1, int(round(segment_sec * fps)))
    values = coverage_series  # list of percentages per frame
    n = len(values)
    # compute moving average efficiently
    prefix = [0.0]
    for v in values:
        prefix.append(prefix[-1] + float(v))
    window_scores = []
    for i in range(0, max(1, n - window + 1)):
        s = prefix[i + window] - prefix[i]
        avg = s / window
        window_scores.append((avg, i, i + window))  # (score, start_idx, end_idx)
    # sort by score desc
    window_scores.sort(key=lambda x: x[0], reverse=True)

    needed_windows = max(1, int(math.ceil(desired_total_sec / segment_sec)))
    selected = []
    taken = np.zeros(n, dtype=bool)
    for score, si, ei in window_scores:
        if len(selected) >= needed_windows:
            break
        # check overlap
        if taken[si:ei].any():
            continue
        selected.append((si, ei))
        taken[si:ei] = True

    # sort chronologically and convert to seconds
    selected.sort(key=lambda x: x[0])
    times = []
    for si, ei in selected:
        st = si / fps
        et = ei / fps
        times.append((st, et))
    return times


@tool
def create_brand_highlight_montage(brand_name: str, file_info: dict, desired_total_duration: float = 5.0, segment_seconds: float = 1.0) -> str:
    """
    Create a highlight montage for a brand by stitching together multiple
    high-coverage subclips from the RAW video, annotated ONLY for that brand.

    - Uses coverage_per_frame.json to score frames
    - Selects top non-overlapping windows of length `segment_seconds`
      until reaching ~`desired_total_duration`
    - Annotates only that brand via saved frame_detections.jsonl

    Returns the output clip path or an error message.
    """
    brand_norm = _normalize_brand(brand_name)
    raw_video = (
        file_info.get('raw_video_path')
        or (file_info.get('video_path') or '').replace('output.mp4', 'raw.mp4')
    )
    coverage_path = file_info.get('coverage_per_frame_path')
    detections_path = file_info.get('frame_detections_path')
    video_meta = file_info.get('video_metadata') or {}
    fps = float(video_meta.get('fps') or 25.0)

    if not raw_video or not os.path.exists(raw_video):
        return "Error: raw video not found."
    if not coverage_path or not os.path.exists(coverage_path):
        return "Error: coverage_per_frame.json not found."
    if not detections_path or not os.path.exists(detections_path):
        return "Error: frame detections file not found."

    try:
        with open(coverage_path, 'r') as f:
            coverage_data = json.load(f)
        per_logo = coverage_data.get('per_logo') or {}
    except Exception as e:
        return f"Error reading coverage data: {e}"

    # Case-insensitive match for brand key
    brand_key = None
    for k in per_logo.keys():
        if _normalize_brand(k) == brand_norm:
            brand_key = k
            break
    if brand_key is None:
        return f"Error: No coverage series found for brand '{brand_name}'."

    series = per_logo.get(brand_key) or []
    if not series:
        return f"Error: Empty coverage series for brand '{brand_name}'."

    windows = _find_best_windows(series, fps, desired_total_duration, segment_seconds)
    if not windows:
        return f"Error: Could not find highlight windows for '{brand_name}'."

    # Prepare IO
    cap = cv2.VideoCapture(raw_video)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    codec = cv2.VideoWriter_fourcc(*'avc1')
    out_dir = os.path.dirname(file_info.get('video_path') or raw_video)
    brand_sanitized = ''.join(c for c in brand_name if c.isalnum() or c in ('-', '_')) or 'brand'
    out_path = os.path.join(out_dir, f"highlight_{brand_sanitized}_{int(desired_total_duration)}s.mp4")
    writer = cv2.VideoWriter(out_path, codec, fps, (width, height))

    # Load detections
    frame_map = _load_detections_map(detections_path)

    # Write windows sequentially; insert short black spacer between segments for visible transition
    spacer_frames = int(max(2, fps * 0.12))  # ~120ms spacer
    black = np.zeros((height, width, 3), dtype=np.uint8)

    try:
        for idx, (st, et) in enumerate(windows):
            start_frame = max(0, int(round(st * fps)))
            end_frame = max(start_frame + 1, int(round(et * fps)))
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            current = start_frame
            while current < end_frame:
                ret, frame = cap.read()
                if not ret:
                    break
                frame_num_jsonl = current + 1
                dets = frame_map.get(frame_num_jsonl, [])
                annotated = _draw_brand_overlays(frame, dets, brand_norm)
                writer.write(annotated)
                current += 1
            # spacer except after last segment
            if idx < len(windows) - 1:
                for _ in range(spacer_frames):
                    writer.write(black)
    finally:
        cap.release()
        writer.release()

    if os.path.exists(out_path):
        return out_path
    return "Error: failed to create highlight montage."



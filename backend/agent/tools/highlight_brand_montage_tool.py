from langchain_core.tools import tool
import os
import json
import cv2
import math
import numpy as np
from backend.utils.timeline_db import TimelineDatabase

# Reuse overlay utilities from the brand-specific clip tool
from backend.agent.tools.create_brand_clip_tool import (
    _normalize_brand,
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

    - Uses timeline.db to score frames by coverage
    - Selects top non-overlapping windows of length `segment_seconds`
      until reaching ~`desired_total_duration`
    - Annotates only that brand via timeline.db

    Returns the output clip path or an error message.
    """
    brand_norm = _normalize_brand(brand_name)
    raw_video = (
        file_info.get('raw_video_path')
        or (file_info.get('video_path') or '').replace('output.mp4', 'raw.mp4')
    )
    db_path = file_info.get('timeline_db_path')
    video_meta = file_info.get('video_metadata') or {}
    fps = float(video_meta.get('fps') or 25.0)

    if not raw_video or not os.path.exists(raw_video):
        return "Error: raw video not found."
    if not db_path or not os.path.exists(db_path):
        return "Error: timeline database not found."

    out_path = "" # Define here for use in finally block
    try:
        with TimelineDatabase(db_path) as db:
            # Case-insensitive match for brand key
            brand_key = None
            logos_in_db = db.get_all_logos()
            for k in logos_in_db:
                if _normalize_brand(k) == brand_norm:
                    brand_key = k
                    break
            if brand_key is None:
                return f"Error: No coverage series found for brand '{brand_name}'."

            series = db.get_coverage_series(brand_key)
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

            # Write windows sequentially; insert short black spacer between segments
            spacer_frames = int(max(2, fps * 0.12))
            black = np.zeros((height, width, 3), dtype=np.uint8)

            prev_end_frame = None
            for idx, (st, et) in enumerate(windows):
                start_frame = max(0, int(round(st * fps)))
                end_frame = max(start_frame + 1, int(round(et * fps)))

                if prev_end_frame is not None:
                    if start_frame <= prev_end_frame:
                        start_frame = prev_end_frame
                    else:
                        for _ in range(spacer_frames):
                            writer.write(black)

                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                current = start_frame
                while current < end_frame:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    # Database frames are 1-based
                    frame_num_for_db = current + 1
                    dets = db.get_frame_detections(frame_num_for_db)
                    annotated = _draw_brand_overlays(frame, dets, brand_norm)
                    writer.write(annotated)
                    current += 1

                prev_end_frame = end_frame
    except Exception as e:
        return f"An unexpected error occurred during montage creation: {e}"
    finally:
        if 'cap' in locals() and cap.isOpened():
            cap.release()
        if 'writer' in locals() and writer.isOpened():
            writer.release()

    if os.path.exists(out_path):
        return out_path
    return "Error: failed to create highlight montage."



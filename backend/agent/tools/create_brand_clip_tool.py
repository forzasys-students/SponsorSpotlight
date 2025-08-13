from langchain_core.tools import tool
import os
import json
import cv2
import numpy as np


def _normalize_brand(name: str) -> str:
	return (name or "").strip().lower()


def _load_detections_map(jsonl_path: str):
	"""Load frame->detections list map from JSONL file."""
	frame_to_dets = {}
	if not os.path.exists(jsonl_path):
		return frame_to_dets
	with open(jsonl_path, 'r') as f:
		for line in f:
			line = line.strip()
			if not line:
				continue
			try:
				obj = json.loads(line)
				frm = int(obj.get('frame', 0))
				dets = obj.get('detections', []) or []
				frame_to_dets[frm] = dets
			except Exception:
				continue
	return frame_to_dets


def _compute_color(brand: str) -> tuple:
    """Deterministic vibrant BGR color from brand name."""
    palette = [
        (36, 170, 255),   # orange
        (80, 180, 60),    # green
        (240, 120, 70),   # blue-ish
        (200, 90, 240),   # purple
        (60, 220, 220),   # yellow-ish
        (90, 100, 255),   # red
        (255, 160, 60),   # teal-ish
    ]
    h = abs(hash(brand))
    return palette[h % len(palette)]


def _draw_brand_overlays(frame: np.ndarray, detections: list, target_brand_norm: str) -> np.ndarray:
    """Spotlight the target brand: dim background, highlight only its polygons/bboxes, add label."""
    if not detections:
        return frame

    H, W = frame.shape[:2]
    brand_mask = np.zeros((H, W), dtype=np.uint8)
    outlines = []  # store polygons/bboxes for label placement
    color = (0, 165, 255)  # default; updated per detection brand

    for det in detections:
        brand = det.get('class', '')
        if _normalize_brand(brand) != target_brand_norm:
            continue
        color = _compute_color(brand)
        polygon = det.get('polygon') or []
        bbox = det.get('bbox') or []
        if polygon and isinstance(polygon, list) and len(polygon) == 4:
            pts = np.array(polygon, dtype=np.int32)
            pts[:, 0] = np.clip(pts[:, 0], 0, W - 1)
            pts[:, 1] = np.clip(pts[:, 1], 0, H - 1)
            cv2.fillConvexPoly(brand_mask, pts, 255)
            outlines.append((brand, 'poly', pts))
        elif bbox and len(bbox) == 4:
            x1, y1, x2, y2 = map(int, bbox)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(W - 1, x2), min(H - 1, y2)
            cv2.rectangle(brand_mask, (x1, y1), (x2, y2), 255, thickness=-1)
            outlines.append((brand, 'bbox', (x1, y1, x2, y2)))

    if brand_mask.max() == 0:
        return frame

    # Create spotlight effect: dim background, keep brand region bright (lighter dim for more transparency)
    dimmed = (frame * 0.6).astype(frame.dtype)
    spotlight = frame.copy()
    spotlight[brand_mask == 0] = dimmed[brand_mask == 0]

    # Glow: create edge of mask then dilate and draw colored outline
    edges = cv2.Canny(brand_mask, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    glow = cv2.dilate(edges, kernel, iterations=1)
    glow_bgr = np.zeros_like(frame)
    glow_bgr[glow > 0] = color
    # blend glow softly
    spotlight = cv2.addWeighted(spotlight, 1.0, glow_bgr, 0.35, 0)

    # Solid outline on exact edges for crispness
    ys, xs = np.where(edges > 0)
    spotlight[ys, xs] = color

    # Labels
    for brand, kind, shape in outlines:
        label = str(brand)
        if kind == 'poly':
            pts = shape
            x, y = int(pts[:, 0].min()), int(pts[:, 1].min())
        else:
            x1, y1, x2, y2 = shape
            x, y = x1, y1
        # Label background box
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.6
        thickness = 2
        (tw, th), _ = cv2.getTextSize(label, font, scale, thickness)
        pad = 6
        bx1, by1 = x, max(0, y - th - 2 * pad)
        bx2, by2 = min(W - 1, x + tw + 2 * pad), min(H - 1, by1 + th + 2 * pad)
        cv2.rectangle(spotlight, (bx1, by1), (bx2, by2), (0, 0, 0), thickness=-1)
        cv2.putText(spotlight, label, (bx1 + pad, by2 - pad - 2), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)

    return spotlight


@tool
def create_brand_specific_clip(brand_name: str, start_time: float, end_time: float, file_info: dict) -> str:
	"""
	Create a brand-specific annotated clip from the RAW video:
	- Trims raw.mp4 between start_time and end_time
	- Overlays only the requested brand's detections using saved frame_detections.jsonl
	Returns the output clip path, or an error message string.
	"""
	raw_video = (
		file_info.get('raw_video_path')
		or (file_info.get('video_path') or '').replace('output.mp4', 'raw.mp4')
	)
	jsonl_path = file_info.get('frame_detections_path')
	video_meta = file_info.get('video_metadata') or {}
	fps = float(video_meta.get('fps') or 25.0)

	if not raw_video or not os.path.exists(raw_video):
		return "Error: raw video not found."
	if not jsonl_path or not os.path.exists(jsonl_path):
		return "Error: frame detections file not found."
	if end_time <= start_time:
		return "Error: end_time must be greater than start_time."

	# Load detections
	frame_map = _load_detections_map(jsonl_path)
	brand_norm = _normalize_brand(brand_name)

	# Prepare IO
	cap = cv2.VideoCapture(raw_video)
	width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
	height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
	codec = cv2.VideoWriter_fourcc(*'avc1')

	# Frame range (OpenCV frames start at 0, our jsonl frames start at 1)
	start_frame = max(0, int(round(start_time * fps)))
	end_frame = max(start_frame + 1, int(round(end_time * fps)))
	cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

	# Output path
	result_dir = os.path.dirname(file_info.get('video_path') or raw_video)
	brand_sanitized = ''.join(c for c in brand_name if c.isalnum() or c in ('-', '_')) or 'brand'
	output_path = os.path.join(result_dir, f"clip_{brand_sanitized}_{start_time}_{end_time}.mp4")
	out = cv2.VideoWriter(output_path, codec, fps, (width, height))

	current_frame_idx = start_frame
	try:
		while current_frame_idx < end_frame:
			ret, frame = cap.read()
			if not ret:
				break
			# jsonl frames are 1-based
			frame_num_jsonl = current_frame_idx + 1
			dets = frame_map.get(frame_num_jsonl, [])
			annotated = _draw_brand_overlays(frame, dets, brand_norm)
			out.write(annotated)
			current_frame_idx += 1
	finally:
		cap.release()
		out.release()

	if os.path.exists(output_path):
		return output_path
	return "Error: failed to create brand-specific clip."



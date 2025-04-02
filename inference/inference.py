import cv2
import torch
from ultralytics import YOLO
import os
import subprocess
import numpy as np
import random
import json
from collections import defaultdict, Counter
from logo_groups import LOGO_GROUPS

# Get the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load the model
model_path = os.path.join(script_dir, '../train-result/yolov11-m-finetuned/weights/best.pt')

# Determine the best available device
def get_device():
    if torch.cuda.is_available():
        return 'cuda'
    elif torch.backends.mps.is_available():
        return 'mps'
    else:
        return 'cpu'

# Load the model on the best available device
device = get_device()
model = YOLO(model_path).to(device)

# Load class names
classes_path = os.path.join(script_dir, 'classes.txt')
with open(classes_path, 'r') as f:
    class_names = f.read().splitlines()

# Predefined color palette for better distinction
color_palette = [
    (31, 119, 180), (255, 127, 14), (44, 160, 44),
    (214, 39, 40), (148, 103, 189), (140, 86, 75),
    (227, 119, 194), (127, 127, 127), (188, 189, 34),
    (23, 190, 207)
]

# Function to annotate frame
def annotate_frame(frame, results):
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
            class_name = class_names[cls]
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
                color = color_palette[cls % len(color_palette)]
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

# Function to process image
def process_image(image_path):
    image = cv2.imread(image_path)
    results = model(image)

    logo_count = Counter()
    for result in results:
        obb = result.obb
        if obb is None:
            continue
        for i in range(len(obb.conf)):
            cls = int(obb.cls[i])
            class_name = class_names[cls]
            logo_count[class_name] += 1

    annotated_image = annotate_frame(image, results)
    output_path = 'output.jpg'
    cv2.imwrite(output_path, annotated_image)

    aggregated_stats = defaultdict(lambda: {"detections": 0})

    for logo, count in logo_count.items():
        if count > 0:
            main_logo = LOGO_GROUPS.get(logo, logo)
            aggregated_stats[main_logo]["detections"] += count
    
    aggregated_stats = dict(aggregated_stats)

    stats_path = "logo_stats.json"
    with open(stats_path, "w") as f:
        json.dump(aggregated_stats, f, indent=4)
        
    return aggregated_stats

# Function to process video and track statistics
def process_video(video_path):
    cap = cv2.VideoCapture(video_path)
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter('output.mp4', fourcc, cap.get(cv2.CAP_PROP_FPS), (int(cap.get(3)), int(cap.get(4))))

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_time = 1 / fps
    total_video_time = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps

    logo_stats = defaultdict(lambda: {"frames": 0, "time": 0.0, "detections": 0})

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        results = model(frame)

        logo_count = Counter()

        for result in results:
            obb = result.obb
            if obb is None:
                continue
            for i in range(len(obb.conf)):
                cls = int(obb.cls[i])
                class_name = class_names[cls]
                logo_count[class_name] += 1
        
        for logo, count in logo_count.items():
            if count > 0:
                logo_stats[logo]["frames"] += 1
                logo_stats[logo]["time"] += frame_time
                logo_stats[logo]["detections"] += count

        annotated_frame = annotate_frame(frame, results)
        out.write(annotated_frame)
    cap.release()
    out.release()

    aggregated_stats = aggregate_stats(logo_stats)

    # Round time values to 2 decimal places, and calculating percentages
    for logo, stats in aggregated_stats.items():
        stats["time"] = round(stats["time"], 2)
        stats["percentage"] = round((stats["time"] / total_video_time * 100) if total_video_time > 0 else 0, 2)

    stats_path = "logo_stats.json"
    with open(stats_path, "w") as f:
        json.dump(aggregated_stats, f, indent=4)

    return aggregated_stats
    
# Function to check if a path is a URL
def is_url(path):
    return path.startswith('http://') or path.startswith('https://')

# Function to process video stream from URL
# Use ffmpeg to select the highest quality stream
def process_video_stream(url):
    # Using ffprobe to get video duration
    ffprobe_cmd = [
        'ffprobe', '-v', 'error', '-show_entries',
        'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', url
    ]
    try:
        duration = float(subprocess.check_output(ffprobe_cmd).decode('utf-8').strip())
        total_video_time = round(duration, 2)
    except (subprocess.CalledProcessError, ValueError):
        print("Warning: Could not determine video duration, using fallback calculation")
        total_video_time = 0

    # Use ffmpeg to get the best quality stream
    ffmpeg_command = [
        'ffmpeg', '-i', url, '-f', 'image2pipe', '-pix_fmt', 'bgr24', '-vcodec', 'rawvideo', '-'
    ]
    pipe = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, bufsize=10**8)
    width, height = 1280, 720  # Set the expected width and height of the video
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter('output.mp4', fourcc, 30.0, (width, height))

    fps = 30.0
    frame_time = 1 / fps
    frame_count = 0    

    logo_stats = defaultdict(lambda: {"frames": 0, "time": 0.0, "detections": 0})

    while True:
        raw_image = pipe.stdout.read(width * height * 3)
        if not raw_image:
            break
        frame = np.frombuffer(raw_image, dtype='uint8').reshape((height, width, 3))
        frame_count += 1

        if total_video_time == 0:
            total_video_time = frame_count * frame_time
        
        results = model(frame)

        logo_count = Counter()
        for result in results:
            obb = result.obb
            if obb is None:
                continue
            for i in range(len(obb.conf)):
                cls = int(obb.cls[i])
                class_name = class_names[cls]
                logo_count[class_name] += 1
        
        for logo, count in logo_count.items():
            if count > 0:
                logo_stats[logo]["frames"] += 1
                logo_stats[logo]["time"] += frame_time
                logo_stats[logo]["detections"] += count

        annotated_frame = annotate_frame(frame, results)
        out.write(annotated_frame)

    pipe.stdout.close()
    pipe.wait()
    out.release()

    aggregated_stats = aggregate_stats(logo_stats)

    # Round time values to 2 decimal places, and calculating percentages
    for logo, stats in aggregated_stats.items():
        stats["time"] = round(stats["time"], 2)
        stats["percentage"] = round((stats["time"] / total_video_time * 100) if total_video_time > 0 else 0, 2)

    stats_path = "logo_stats.json"
    with open(stats_path, "w") as f:
        json.dump(aggregated_stats, f, indent=4)

    return aggregated_stats

# Function to aggregate different versions of logos using the logo_groups.py script
def aggregate_stats(logo_stats):
    aggregated = defaultdict(lambda: {"frames": 0, "time": 0.0, "detections": 0, "percentage": 0.0})
    
    for logo, stats in logo_stats.items():
        # Get the main logo name or use the original if not in mapping
        main_logo = LOGO_GROUPS.get(logo, logo)
        
        aggregated[main_logo]["frames"] += stats["frames"]
        aggregated[main_logo]["time"] += stats["time"]
        aggregated[main_logo]["detections"] += stats["detections"]
        # Percentage will be recalculated later
    
    return aggregated

# Main function
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print('Usage: python inference.py <image|video> <path>')
        sys.exit(1)

    mode = sys.argv[1]
    path = sys.argv[2]

    if mode == 'image':
        process_image(path)
    elif mode == 'video':
        if is_url(path):
            process_video_stream(path)
        else:
            process_video(path)
    else:
        print('Invalid mode. Use "image" or "video".')
        sys.exit(1)

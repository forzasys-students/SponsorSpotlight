from langchain_core.tools import tool
import json

@tool
def find_best_clip(brand_name: str, file_info: dict) -> dict:
    """
    Finds the best 10-second clip for a specific brand based on logo detection data.
    Use this tool to identify the most exciting clip for a given brand.
    Returns the start and end time of the best clip in seconds.
    """
    timeline_stats = file_info.get('timeline_stats_data', {})
    video_metadata = file_info.get('video_metadata', {})

    brand_frames = timeline_stats.get(brand_name)
    if not brand_frames:
        return {"error": f"No detections found for brand: {brand_name}"}

    fps = video_metadata.get('fps', 25)
    clip_duration_frames = 10 * fps
    
    max_detections = 0
    best_clip_start_frame = -1

    # This is a simple sliding window approach. More complex logic could be added here.
    for i in range(len(brand_frames)):
        start_frame = brand_frames[i]
        end_frame = start_frame + clip_duration_frames
        
        detections_in_window = sum(1 for frame in brand_frames if start_frame <= frame < end_frame)
        
        if detections_in_window > max_detections:
            max_detections = detections_in_window
            best_clip_start_frame = start_frame

    if best_clip_start_frame == -1:
        return {"error": "Could not determine the best clip."}

    best_clip_start_time = best_clip_start_frame / fps
    best_clip_end_time = best_clip_start_time + 10

    return {
        "start_time": round(best_clip_start_time, 2),
        "end_time": round(best_clip_end_time, 2)
    }

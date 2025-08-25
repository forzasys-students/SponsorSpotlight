#!/usr/bin/env python3
"""
Script to directly process existing video files without going through the web interface.
This bypasses the need to re-upload files that are already on the server.
"""

import os
import sys
import hashlib
import argparse
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.core.inference_manager import InferenceManager
from backend.utils.progress_manager import ProgressManager

def get_file_hash(file_path):
    """Generate a hash for the file to use as a unique identifier"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def process_existing_video(video_path, output_dir=None):
    """Process an existing video file directly"""
    
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        return False
    
    # Generate file hash
    file_hash = get_file_hash(video_path)
    print(f"File hash: {file_hash}")
    
    # Determine file type
    file_extension = video_path.rsplit('.', 1)[1].lower()
    if file_extension not in ['mp4', 'avi', 'mov', 'webm']:
        print(f"Error: Unsupported video format: {file_extension}")
        return False
    
    # Initialize managers
    progress_manager = ProgressManager()
    inference_manager = InferenceManager(progress_manager)
    
    print(f"Starting processing of: {video_path}")
    print(f"File size: {os.path.getsize(video_path) / (1024**3):.2f} GB")
    
    # Start inference
    inference_manager.start_inference('video', video_path, file_hash)
    
    print("Processing started! Check the web interface for progress updates.")
    print(f"Results will be available at: /show_results/{file_hash}")
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Process existing video files directly')
    parser.add_argument('video_path', help='Path to the video file to process')
    parser.add_argument('--output-dir', help='Output directory for results (optional)')
    
    args = parser.parse_args()
    
    # Resolve the video path.
    # First, assume the path is relative to the project root.
    video_path = os.path.join(project_root, args.video_path)
    
    # If that path doesn't exist, assume it's just the filename in the uploads directory
    if not os.path.exists(video_path):
        uploads_dir = os.path.join(project_root, 'frontend', 'static', 'uploads')
        video_path = os.path.join(uploads_dir, os.path.basename(args.video_path))

    success = process_existing_video(video_path, args.output_dir)
    
    if success:
        print("\n✅ Video processing initiated successfully!")
        print("You can monitor progress through the web interface.")
    else:
        print("\n❌ Failed to start video processing.")
        sys.exit(1)

if __name__ == "__main__":
    main()

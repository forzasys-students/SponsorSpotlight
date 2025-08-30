import os
import subprocess
import json

def get_video_duration(video_path):
    """Gets the duration of a video in seconds using ffprobe for efficiency."""
    try:
        ffprobe_cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(ffprobe_cmd, check=True, capture_output=True, text=True)
        return float(result.stdout)
    except FileNotFoundError:
        print("Error: ffprobe is not installed or not in the system's PATH.")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Error getting video duration for {video_path} with ffprobe: {e}")
        print(f"ffprobe stderr: {e.stderr}")
        return 0
    except Exception as e:
        print(f"An unexpected error occurred while getting video duration for {video_path}: {e}")
        return 0

def generate_thumbnails(video_path, output_dir, interval_seconds=30):
    """Generates thumbnails from a video at a given interval."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    duration = get_video_duration(video_path)
    if duration == 0:
        print(f"Cannot generate thumbnails for {video_path} as duration is zero.")
        return

    print(f"Generating thumbnails for {video_path} every {interval_seconds} seconds.")

    ffmpeg_cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vf', f'fps=1/{interval_seconds}',
        '-q:v', '2',
        os.path.join(output_dir, 'thumb_%04d.jpg'),
        '-y'
    ]

    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
        print(f"Successfully generated thumbnails for {video_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error generating thumbnails for {video_path}: {e}")
        print(f"FFmpeg stderr: {e.stderr}")

def create_thumbnail_sprite(thumbnail_dir, output_path, sprite_filename='thumbnail_sprite.jpg', thumbnail_width=160):
    """Creates a sprite sheet from a directory of thumbnails."""
    try:
        from PIL import Image
    except ImportError:
        print("Pillow library not found. Please install it with 'pip install Pillow'")
        return

    thumbnail_files = sorted([f for f in os.listdir(thumbnail_dir) if f.endswith('.jpg')])
    if not thumbnail_files:
        print("No thumbnails found to create a sprite.")
        return

    images = [Image.open(os.path.join(thumbnail_dir, f)) for f in thumbnail_files]
    
    # Assuming all thumbnails have the same size, calculate sprite dimensions
    img_width, img_height = images[0].size
    
    # Scale height based on the fixed width
    aspect_ratio = img_height / img_width
    scaled_height = int(thumbnail_width * aspect_ratio)

    # Resize all images
    resized_images = [img.resize((thumbnail_width, scaled_height)) for img in images]
    
    # For a horizontal sprite:
    total_width = thumbnail_width * len(resized_images)
    sprite_image = Image.new('RGB', (total_width, scaled_height))
    
    x_offset = 0
    for img in resized_images:
        sprite_image.paste(img, (x_offset, 0))
        x_offset += thumbnail_width

    sprite_path = os.path.join(output_path, sprite_filename)
    sprite_image.save(sprite_path)
    print(f"Thumbnail sprite saved to {sprite_path}")

    # Clean up individual thumbnail files
    for f in thumbnail_files:
        os.remove(os.path.join(thumbnail_dir, f))
    print("Cleaned up individual thumbnail files.")

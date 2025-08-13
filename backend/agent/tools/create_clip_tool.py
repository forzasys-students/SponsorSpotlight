from langchain_core.tools import tool
import subprocess
import os

@tool
def create_video_clip(start_time: float, end_time: float, file_info: dict) -> str:
    """
    Creates a video clip from a larger video file using ffmpeg.
    Use this tool to cut a smaller clip from a larger video.
    Returns the path to the newly created clip.
    """
    original_video_path = file_info.get('video_path')
    if not original_video_path or not os.path.exists(original_video_path):
        return "Error: Original video path not found in file_info."

    output_dir = os.path.dirname(original_video_path)

    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        filename = f"clip_{start_time}_{end_time}.mp4"
        output_path = os.path.join(output_dir, filename)
        
        # This command is very fast because it seeks to the start time (-ss)
        # and copies the video and audio streams (-c copy) without re-encoding.
        command = [
            'ffmpeg',
            '-ss', str(start_time),
            '-to', str(end_time),
            '-i', original_video_path,
            '-c', 'copy',
            '-y',  # Overwrite output file if it exists
            output_path
        ]
        
        print(f"Executing ffmpeg command: {' '.join(command)}")
        
        # Execute the command
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        
        print("ffmpeg output:", result.stdout)
        print("ffmpeg errors:", result.stderr)

        if os.path.exists(output_path):
            return output_path
        else:
            return f"Error: ffmpeg command executed but output file was not created. Stderr: {result.stderr}"

    except subprocess.CalledProcessError as e:
        error_message = f"Error creating video clip with ffmpeg. Return code: {e.returncode}. Stderr: {e.stderr}"
        print(error_message)
        return error_message
    except FileNotFoundError:
        error_message = "Error: 'ffmpeg' command not found. Please ensure ffmpeg is installed and in your system's PATH."
        print(error_message)
        return error_message
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        print(error_message)
        return error_message

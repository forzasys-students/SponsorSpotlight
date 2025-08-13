from langchain_core.tools import tool
from backend.services.ftp_uploader import FTPUploader
from backend.services.instagram_publisher import InstagramPublisher
from backend.agent.config import config_manager
import os


def _resolve_local_path(path: str) -> str:
    """Normalize various path formats to a real local filesystem path.
    - Strip quotes/backticks and sandbox: prefix
    - Map /static/... URLs to absolute frontend/static/... on disk
    """
    if not path:
        return path
    p = str(path).strip().strip('`').strip('"').strip("'")
    if p.startswith('sandbox:'):
        p = p[len('sandbox:'):]
    # Map served static URL to actual file on disk
    if p.startswith('/static/'):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        static_dir = os.path.join(base_dir, 'frontend', 'static')
        rel = p[len('/static/'):]
        p = os.path.join(static_dir, rel)
    return p

@tool
def share_on_instagram(video_path: str, caption: str, task_manager=None, task_id=None) -> dict:
    """
    Shares a video on Instagram. Use this tool when the user wants to post
    a video to Instagram. It will upload the video and return a status.
    """
    video_path = _resolve_local_path(video_path)
    if not os.path.exists(video_path):
        return {"status": "error", "message": f"Video file not found at path: {video_path}"}

    # --- FTP Upload ---
    ftp_hostname, ftp_username, ftp_password, ftp_public_url_base = config_manager.get_ftp_credentials()
    ftp_uploader = FTPUploader(ftp_hostname, ftp_username, ftp_password)
    
    video_filename = ftp_uploader.upload_file(video_path, task_manager, task_id)
    if not video_filename:
        error_message = "Failed to upload video to FTP."
        if task_manager:
            task_manager.update_progress(task_id, error_message)
        return {"status": "error", "message": error_message}

    video_url = f"{ftp_public_url_base.rstrip('/')}/{video_filename}"

    # --- Instagram Share ---
    insta_access_token, insta_user_id = config_manager.get_instagram_credentials()
    instagram_publisher = InstagramPublisher(insta_access_token, insta_user_id)
    
    publication_id, permalink = instagram_publisher.publish_video(video_url, caption, task_manager, task_id)

    if publication_id and permalink:
        success_message = f"Video successfully shared! View it here: {permalink}"
        return {"status": "success", "message": success_message, "permalink": permalink}
    else:
        error_message = "Failed to share video on Instagram. The video might not meet Instagram's specifications, or the API returned an error. Check logs for details."
        if task_manager:
            task_manager.update_progress(task_id, error_message)
        return {"status": "error", "message": error_message}

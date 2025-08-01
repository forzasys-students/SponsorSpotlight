from backend.agent.config import config_manager
from backend.services.ftp_uploader import FTPUploader
from backend.services.instagram_publisher import InstagramPublisher

class ShareNode:
    def __init__(self):
        (
            self.ftp_hostname,
            self.ftp_username,
            self.ftp_password,
            self.ftp_public_url_base,
        ) = config_manager.get_ftp_credentials()
        (
            self.instagram_access_token,
            self.instagram_user_id,
        ) = config_manager.get_instagram_credentials()

    def share_video(self, video_path, caption, task_manager, task_id):
        """
        Uploads the video to FTP and shares it on Instagram, reporting progress.
        """
        # Upload to FTP
        ftp_uploader = FTPUploader(
            self.ftp_hostname, self.ftp_username, self.ftp_password
        )
        video_filename = ftp_uploader.upload_file(video_path, task_manager, task_id)
        if not video_filename:
            result = "Failed to upload video to FTP."
            task_manager.complete_task(task_id, result, success=False)
            return

        video_url = f"{self.ftp_public_url_base.rstrip('/')}/{video_filename}"

        # Share on Instagram
        instagram_publisher = InstagramPublisher(
            self.instagram_access_token, self.instagram_user_id
        )
        publication_id, permalink = instagram_publisher.publish_video(video_url, caption, task_manager, task_id)

        if publication_id and permalink:
            result = f"Video successfully shared! View it here: {permalink}"
            task_manager.complete_task(task_id, result, success=True)
        else:
            result = "Failed to share video on Instagram. Check the logs for details."
            task_manager.complete_task(task_id, result, success=False)

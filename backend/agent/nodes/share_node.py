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

    def share_video(self, video_path, caption):
        """
        Uploads the video to FTP and shares it on Instagram.
        """
        # Upload to FTP
        ftp_uploader = FTPUploader(
            self.ftp_hostname, self.ftp_username, self.ftp_password
        )
        video_filename = ftp_uploader.upload_file(video_path)
        if not video_filename:
            return "Failed to upload video to FTP."

        video_url = f"{self.ftp_public_url_base}/{video_filename}"

        # Share on Instagram
        instagram_publisher = InstagramPublisher(
            self.instagram_access_token, self.instagram_user_id
        )
        publication_id = instagram_publisher.publish_video(video_url, caption)

        if publication_id:
            return f"Video successfully shared to Instagram with publication ID: {publication_id}"
        else:
            return "Failed to share video on Instagram."

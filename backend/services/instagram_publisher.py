import requests
import time

class InstagramPublisher:
    def __init__(self, access_token, user_id):
        self.access_token = access_token
        self.user_id = user_id
        self.graph_api_version = 'v18.0'
        self.base_url = f"https://graph.facebook.com/{self.graph_api_version}"

    def publish_video(self, video_url, caption='', task_manager=None, task_id=None):
        """
        Publishes a video to Instagram using the Content Publishing API.
        """
        def report(msg):
            if task_manager and task_id:
                task_manager.update_progress(task_id, msg)

        # Step 1: Create a media container
        report("Creating Instagram media container...")
        container_id = self._create_media_container(video_url, caption)
        if not container_id:
            report("Failed to create Instagram media container.")
            return None, "Failed to create Instagram media container."

        # Step 2: Wait for the container to be ready
        report("Waiting for Instagram to process the video...")
        if not self._wait_for_container_ready(container_id, report_progress=report):
            report("Instagram media processing failed or timed out.")
            return None, "Instagram media processing failed or timed out."

        # Step 3: Publish the media container
        report("Publishing video to Instagram...")
        publication_id = self._publish_media_container(container_id)
        if not publication_id:
            report("Failed to publish video.")
            return None, "Failed to publish video."

        # Step 4: Get the permalink
        report("Fetching post URL...")
        permalink = self._get_media_permalink(publication_id)

        report("Video published successfully!")
        return publication_id, permalink

    def _create_media_container(self, video_url, caption):
        """
        Creates a media container for the video.
        """
        url = f"{self.base_url}/{self.user_id}/media"
        params = {
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption,
            'access_token': self.access_token
        }
        
        try:
            response = requests.post(url, params=params)
            response.raise_for_status()
            return response.json().get('id')
        except requests.exceptions.RequestException as e:
            print(f"Error creating media container: {e}")
            print(f"Response: {e.response.text}")
            return None

    def _wait_for_container_ready(self, container_id, timeout=300, interval=15, report_progress=None):
        """
        Polls the media container status until it's finished or times out.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            url = f"{self.base_url}/{container_id}"
            params = {
                'fields': 'status_code',
                'access_token': self.access_token
            }
            try:
                response = requests.get(url, params=params)
                response.raise_for_status()
                status = response.json().get('status_code')
                
                if report_progress:
                    report_progress(f"Polling Instagram status: {status}...")
                
                if status == 'FINISHED':
                    return True
                elif status == 'ERROR':
                    print("Media container processing failed.")
                    return False
                
                time.sleep(interval)

            except requests.exceptions.RequestException as e:
                print(f"Error checking container status: {e}")
                return False
        
        print("Timeout waiting for media container to be ready.")
        return False

    def _publish_media_container(self, container_id):
        """
        Publishes the media container to Instagram.
        """
        url = f"{self.base_url}/{self.user_id}/media_publish"
        params = {
            'creation_id': container_id,
            'access_token': self.access_token
        }
        
        try:
            response = requests.post(url, params=params)
            response.raise_for_status()
            return response.json().get('id')
        except requests.exceptions.RequestException as e:
            print(f"Error publishing media container: {e}")
            print(f"Response: {e.response.text}")
            return None

    def _get_media_permalink(self, media_id):
        """
        Retrieves the permalink for a published media item.
        """
        url = f"{self.base_url}/{media_id}"
        params = {
            'fields': 'permalink',
            'access_token': self.access_token
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json().get('permalink')
        except requests.exceptions.RequestException as e:
            print(f"Error getting media permalink: {e}")
            return None

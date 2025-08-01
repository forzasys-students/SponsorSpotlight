import requests
import time

class InstagramPublisher:
    def __init__(self, access_token, user_id):
        self.access_token = access_token
        self.user_id = user_id
        self.graph_api_version = 'v18.0'
        self.base_url = f"https://graph.facebook.com/{self.graph_api_version}"

    def publish_video(self, video_url, caption=''):
        """
        Publishes a video to Instagram using the Content Publishing API.
        """
        # Step 1: Create a media container
        container_id = self._create_media_container(video_url, caption)
        if not container_id:
            return None

        # Step 2: Wait for the container to be ready
        if not self._wait_for_container_ready(container_id):
            return None

        # Step 3: Publish the media container
        return self._publish_media_container(container_id)

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

    def _wait_for_container_ready(self, container_id, timeout=300, interval=15):
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
                
                print(f"Polling container status: {status}")
                
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

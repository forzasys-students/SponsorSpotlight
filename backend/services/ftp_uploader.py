import ftplib
import os

class FTPUploader:
    def __init__(self, hostname, username, password, remote_dir='/htdocs/videos'):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.remote_dir = remote_dir

    def upload_file(self, local_file_path):
        """
        Uploads a file to the FTP server and returns its public URL.
        """
        try:
            with ftplib.FTP(self.hostname, self.username, self.password) as ftp:
                ftp.cwd(self.remote_dir)
                
                filename = os.path.basename(local_file_path)
                with open(local_file_path, 'rb') as f:
                    ftp.storbinary(f'STOR {filename}', f)
                
                return f"{filename}"
        except Exception as e:
            print(f"FTP upload failed: {e}")
            return None

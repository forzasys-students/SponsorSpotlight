import ftplib
import os

class FTPUploader:
    def __init__(self, hostname, username, password, remote_dir='/htdocs/videos'):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.remote_dir = remote_dir

    def upload_file(self, local_file_path, task_manager=None, task_id=None):
        """
        Uploads a file to the FTP server and returns its public URL, reporting progress.
        """
        def report(msg):
            if task_manager and task_id:
                task_manager.update_progress(task_id, msg)

        try:
            report("Connecting to FTP server...")
            with ftplib.FTP(self.hostname, self.username, self.password, timeout=30) as ftp:
                report("FTP connection successful. Changing directory...")
                ftp.cwd(self.remote_dir)
                
                filename = os.path.basename(local_file_path)
                report(f"Uploading file '{filename}'...")
                with open(local_file_path, 'rb') as f:
                    ftp.storbinary(f'STOR {filename}', f)
                
                report("File upload complete.")
                return filename
        except Exception as e:
            error_message = f"FTP upload failed: {e}"
            report(error_message)
            print(error_message)
            return None

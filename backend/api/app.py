"""
Main Flask application entry point
Refactored to use modular route organization
"""
from flask import Flask
import os
import hashlib

from backend.core.inference_manager import InferenceManager
from backend.utils.progress_manager import ProgressManager
from backend.utils.agent_task_manager import AgentTaskManager

# Import route modules
from backend.api.routes.main_routes import register_main_routes
from backend.api.routes.file_routes import register_file_routes
from backend.api.routes.api_routes import register_api_routes
from backend.api.routes.agent_routes import register_agent_routes

# Get absolute paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'frontend', 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'frontend', 'static')
UPLOAD_DIR = os.path.join(STATIC_DIR, 'uploads')
RESULTS_DIR = os.path.join(STATIC_DIR, 'results')

# Initialize Flask app
app = Flask(__name__, 
            template_folder=TEMPLATE_DIR,
            static_folder=STATIC_DIR)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_change_in_production')
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
app.config['RESULTS_FOLDER'] = RESULTS_DIR
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'mov', 'webm'}
app.config['MAX_CONTENT_LENGTH'] = 6 * 1024 * 1024 * 1024  # 6GB max upload size

# Create upload and results directories if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

# Print paths for debugging
print(f"Base directory: {BASE_DIR}")
print(f"Template directory: {TEMPLATE_DIR}")
print(f"Static directory: {STATIC_DIR}")
print(f"Upload directory: {UPLOAD_DIR}")
print(f"Results directory: {RESULTS_DIR}")

# Initialize managers
progress_manager = ProgressManager()
inference_manager = InferenceManager(progress_manager)
agent_task_manager = AgentTaskManager()

# Utility functions
def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_file_hash(file_path):
    """Generate a hash for the file to use as a unique identifier"""
    with open(file_path, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()
    return file_hash

def get_url_hash(url: str) -> str:
    """Generate a stable hash for a URL to use as a cache key"""
    return hashlib.md5(url.strip().encode('utf-8')).hexdigest()

# Register all route modules
register_main_routes(app, inference_manager, allowed_file, get_file_hash, get_url_hash)
register_file_routes(app, allowed_file, get_file_hash)
register_api_routes(app)
register_agent_routes(app, agent_task_manager)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5005)

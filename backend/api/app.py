from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import os
import uuid
from werkzeug.utils import secure_filename
import hashlib
import time
import json

from backend.core.inference_manager import InferenceManager
from backend.utils.progress_manager import ProgressManager
from backend.utils.agent_task_manager import AgentTaskManager
import threading

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
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload size

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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_file_hash(file_path):
    """Generate a hash for the file to use as a unique identifier"""
    with open(file_path, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()
    return file_hash

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        # Generate a unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"{str(uuid.uuid4())}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        # Save the uploaded file
        file.save(file_path)
        
        # Generate a hash for the file
        file_hash = get_file_hash(file_path)
        
        # Determine if it's an image or video
        file_extension = filename.rsplit('.', 1)[1].lower()
        if file_extension in ['jpg', 'jpeg', 'png', 'gif']:
            file_type = 'image'
        else:
            file_type = 'video'
        
        # Store file info in session
        session['file_info'] = {
            'path': file_path,
            'type': file_type,
            'hash': file_hash,
            'original_name': filename
        }
        
        # Redirect to processing page
        return redirect(url_for('process_file'))
    
    flash('File type not allowed')
    return redirect(url_for('index'))

@app.route('/process')
def process_file():
    file_info = session.get('file_info')
    if not file_info:
        flash('No file uploaded')
        return redirect(url_for('index'))
    
    # Start processing in a separate thread
    inference_manager.start_inference(
        file_info['type'], 
        file_info['path'], 
        file_info['hash']
    )
    
    return render_template('processing.html', file_type=file_info['type'])

@app.route('/progress')
def get_progress():
    """API endpoint to get the current processing progress"""
    progress_data = progress_manager.get_progress()
    return jsonify(progress_data)

@app.route('/results/<file_hash>')
def show_results(file_hash):
    """Show the results page for a processed file"""
    file_info = session.get('file_info')
    if not file_info or file_info['hash'] != file_hash:
        flash('Invalid file or session expired')
        return redirect(url_for('index'))
    
    # Determine the file extension based on file type
    extension = "jpg" if file_info["type"] == "image" else "mp4"
    
    # Construct the paths to the results
    output_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, f'output.{extension}')
    stats_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'stats.json')
    
    # Check if the result files exist
    if not os.path.exists(output_path) or not os.path.exists(stats_path):
        flash('Results not found. The file may still be processing or an error occurred.')
        return redirect(url_for('index'))
    
    # Create the relative path for the template
    output_rel_path = os.path.join('results', file_hash, f'output.{extension}')
    
    return render_template('results.html', 
                          file_type=file_info['type'],
                          output_path=output_rel_path,
                          file_hash=file_hash,
                          original_name=file_info['original_name'])

@app.route('/dashboard/<file_hash>')
def show_dashboard(file_hash):
    """Show the analytics dashboard for a processed file"""
    file_info = session.get('file_info')
    if not file_info or file_info['hash'] != file_hash:
        flash('Invalid file or session expired')
        return redirect(url_for('index'))
    
    # Construct the path to the stats file
    stats_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'stats.json')
    if not os.path.exists(stats_path):
        flash('Dashboard data not found. The file may still be processing or an error occurred.')
        return redirect(url_for('index'))
    
    return render_template('dashboard.html',
                          file_type=file_info['type'],
                          file_hash=file_hash,
                          original_name=file_info['original_name'])

@app.route('/api/stats/<file_hash>')
def get_stats(file_hash):
    """API endpoint to get the logo statistics for a processed file"""
    stats_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'stats.json')
    
    if not os.path.exists(stats_path):
        return jsonify({'error': 'Statistics not found'}), 404
    
    with open(stats_path, 'r') as f:
        stats = f.read()
    
    return stats, 200, {'Content-Type': 'application/json'}

@app.route('/api/timeline_stats/<file_hash>')
def get_timeline_stats(file_hash):
    """API endpoint to get the frame-by-frame timeline statistics"""
    timeline_stats_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'timeline_stats.json')
    
    if not os.path.exists(timeline_stats_path):
        return jsonify({'error': 'Timeline statistics not found'}), 404
        
    with open(timeline_stats_path, 'r') as f:
        timeline_stats = f.read()
        
    return timeline_stats, 200, {'Content-Type': 'application/json'}

@app.route('/api/agent_query/<file_hash>', methods=['POST'])
def agent_query(file_hash):
    """API endpoint to handle agentic queries"""
    data = request.get_json()
    query = data.get('query')
    
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    
    # Construct the path to the stats file
    stats_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'stats.json')
    if not os.path.exists(stats_path):
        return jsonify({'error': 'Statistics not found for this file'}), 404
        
    # Load the stats data
    with open(stats_path, 'r') as f:
        stats_data = json.load(f)
    
    # Load the timeline stats data
    timeline_stats_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'timeline_stats.json')
    if not os.path.exists(timeline_stats_path):
        return jsonify({'error': 'Timeline statistics not found for this file'}), 404
    
    with open(timeline_stats_path, 'r') as f:
        timeline_stats_data = json.load(f)
        
    # Get the video path for the share node
    video_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'output.mp4')

    # Prepare file info for the agent
    file_info = {
        'stats_data': stats_data,
        'timeline_stats_data': timeline_stats_data,
        'video_path': video_path
    }

    from backend.agent.router import AgentRouter
    router = AgentRouter()

    # Check if this is a share task
    if any(keyword in query.lower() for keyword in ['share', 'post', 'instagram']):
        task_id = agent_task_manager.create_task()
        
        # Run the task in a background thread
        thread = threading.Thread(target=router.route_query, args=(query, file_info, agent_task_manager, task_id))
        thread.daemon = True
        thread.start()
        
        return jsonify({'task_id': task_id})

    else:
        # Handle synchronous tasks like analysis
        result = router.route_query(query, file_info)
        return jsonify({'response': result})

@app.route('/api/agent_task_status/<task_id>')
def agent_task_status(task_id):
    """API endpoint to get the status of an agent task."""
    status = agent_task_manager.get_task_status(task_id)
    return jsonify(status)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5005)
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
import base64
import subprocess

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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_file_hash(file_path):
    """Generate a hash for the file to use as a unique identifier"""
    with open(file_path, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()
    return file_hash

def get_url_hash(url: str) -> str:
    """Generate a stable hash for a URL to use as a cache key"""
    return hashlib.md5(url.strip().encode('utf-8')).hexdigest()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_url', methods=['POST'])
def upload_url():
    data = request.get_json(silent=True) or {}
    url = data.get('url') or request.form.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    file_hash = get_url_hash(url)
    file_type = 'video'
    original_name = url.split('/')[-1] or 'remote_stream'

    # If results already exist, reuse them
    result_dir = os.path.join(app.config['RESULTS_FOLDER'], file_hash)
    output_path = os.path.join(result_dir, 'output.mp4')
    stats_path = os.path.join(result_dir, 'stats.json')
    if os.path.exists(output_path) and os.path.exists(stats_path):
        session['file_info'] = {
            'path': url,
            'type': file_type,
            'hash': file_hash,
            'original_name': original_name
        }
        return jsonify({'redirect': url_for('show_results', file_hash=file_hash)})

    # Otherwise, set session and start processing
    session['file_info'] = {
        'path': url,
        'type': file_type,
        'hash': file_hash,
        'original_name': original_name
    }
    return jsonify({'redirect': url_for('process_file')})

@app.route('/api/preview_frame')
def preview_frame():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    # Use ffmpeg to extract a single frame into memory
    try:
        # Grab the first keyframe quickly; -vframes 1 equivalent via -frames:v
        cmd = [
            'ffmpeg', '-y', '-i', url,
            '-frames:v', '1',
            '-q:v', '2',
            '-f', 'image2pipe', '-vcodec', 'mjpeg', '-'
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        img_bytes, err = proc.communicate(timeout=20)
        if proc.returncode != 0 or not img_bytes:
            return jsonify({'error': 'Failed to extract frame', 'details': err.decode('utf-8')[-500:]}), 500
        b64 = base64.b64encode(img_bytes).decode('utf-8')
        data_url = f'data:image/jpeg;base64,{b64}'
        return jsonify({'image_data': data_url})
    except Exception as e:
        return jsonify({'error': f'Preview failed: {str(e)}'}), 500

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

        # If results already exist, reuse them
        result_dir = os.path.join(app.config['RESULTS_FOLDER'], file_hash)
        out_ext = 'jpg' if file_type == 'image' else 'mp4'
        output_path = os.path.join(result_dir, f'output.{out_ext}')
        stats_path = os.path.join(result_dir, 'stats.json')
        if os.path.exists(output_path) and os.path.exists(stats_path):
            session['file_info'] = {
                'path': file_path,
                'type': file_type,
                'hash': file_hash,
                'original_name': filename
            }
            return redirect(url_for('show_results', file_hash=file_hash))
        
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
    # If results already exist, skip processing and go to results
    result_dir = os.path.join(app.config['RESULTS_FOLDER'], file_info['hash'])
    out_ext = 'jpg' if file_info['type'] == 'image' else 'mp4'
    output_path = os.path.join(result_dir, f'output.{out_ext}')
    stats_path = os.path.join(result_dir, 'stats.json')
    if os.path.exists(output_path) and os.path.exists(stats_path):
        return redirect(url_for('show_results', file_hash=file_info['hash']))
    
    # Start processing in a separate thread
    inference_manager.start_inference(
        file_info['type'], 
        file_info['path'], 
        file_info['hash']
    )
    
    return render_template('processing.html', file_type=file_info['type'])

@app.route('/process_existing/<filename>')
def process_existing_file(filename):
    """Process an existing file that's already in the uploads directory"""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(file_path):
        flash(f'File {filename} not found in uploads directory')
        return redirect(url_for('index'))
    
    if not allowed_file(filename):
        flash('File type not allowed')
        return redirect(url_for('index'))
    
    # Generate a hash for the existing file
    file_hash = get_file_hash(file_path)
    
    # Determine if it's an image or video
    file_extension = filename.rsplit('.', 1)[1].lower()
    if file_extension in ['jpg', 'jpeg', 'png', 'gif']:
        file_type = 'image'
    else:
        file_type = 'video'
    
    # If results already exist, reuse them
    result_dir = os.path.join(app.config['RESULTS_FOLDER'], file_hash)
    out_ext = 'jpg' if file_type == 'image' else 'mp4'
    output_path = os.path.join(result_dir, f'output.{out_ext}')
    stats_path = os.path.join(result_dir, 'stats.json')
    if os.path.exists(output_path) and os.path.exists(stats_path):
        session['file_info'] = {
            'path': file_path,
            'type': file_type,
            'hash': file_hash,
            'original_name': filename
        }
        return redirect(url_for('show_results', file_hash=file_hash))

    # Store file info in session and process
    session['file_info'] = {
        'path': file_path,
        'type': file_type,
        'hash': file_hash,
        'original_name': filename
    }
    return redirect(url_for('process_file'))

@app.route('/list_existing_files')
def list_existing_files():
    """List all existing files in the uploads directory"""
    files = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if allowed_file(filename):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                file_size_mb = round(file_size / (1024 * 1024), 2)
                files.append({
                    'filename': filename,
                    'size_mb': file_size_mb,
                    'type': 'video' if filename.rsplit('.', 1)[1].lower() in ['mp4', 'avi', 'mov', 'webm'] else 'image'
                })
    
    return render_template('existing_files.html', files=files)

@app.route('/progress')
def get_progress():
    """API endpoint to get the current processing progress"""
    progress_data = progress_manager.get_progress()
    return jsonify(progress_data)

@app.route('/results/<file_hash>')
def show_results(file_hash):
    """Show the results page for a processed file, even if session is missing."""
    result_dir = os.path.join(app.config['RESULTS_FOLDER'], file_hash)
    video_out = os.path.join(result_dir, 'output.mp4')
    image_out = os.path.join(result_dir, 'output.jpg')
    stats_path = os.path.join(result_dir, 'stats.json')
    if not os.path.exists(stats_path):
        flash('Results not found. The file may still be processing or an error occurred.')
        return redirect(url_for('index'))

    is_video = os.path.exists(video_out)
    has_media = os.path.exists(video_out) or os.path.exists(image_out)
    extension = 'mp4' if is_video else 'jpg'
    output_rel_path = os.path.join('results', file_hash, f'output.{extension}') if has_media else None
    file_info = session.get('file_info') or {}
    file_type = file_info.get('type') or ('video' if is_video else 'image')
    original_name = file_info.get('original_name') or f'{file_hash}.{extension}'

    return render_template('results.html', 
                          file_type=file_type,
                          output_path=output_rel_path,
                          file_hash=file_hash,
                          original_name=original_name)

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
    # Attempt to load JSON so we can include processing_info if present (or sidecar)
    try:
        with open(stats_path, 'r') as f:
            data = json.load(f)
    except Exception:
        with open(stats_path, 'r') as f:
            raw = f.read()
        return raw, 200, {'Content-Type': 'application/json'}
    if isinstance(data, dict) and 'processing_info' not in data:
        meta_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'processing_meta.json')
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r') as mf:
                    meta = json.load(mf)
                if isinstance(meta, dict) and 'processing_info' in meta:
                    data['processing_info'] = meta['processing_info']
            except Exception:
                pass
    return json.dumps(data), 200, {'Content-Type': 'application/json'}

@app.route('/api/processing_info/<file_hash>')
def get_processing_info(file_hash):
    """Return processing device/time info if available."""
    stats_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'stats.json')
    if os.path.exists(stats_path):
        try:
            with open(stats_path, 'r') as f:
                data = json.load(f)
            if isinstance(data, dict) and 'processing_info' in data:
                return jsonify(data['processing_info'])
        except Exception:
            pass
    meta_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'processing_meta.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            if isinstance(meta, dict) and 'processing_info' in meta:
                return jsonify(meta['processing_info'])
        except Exception:
            pass
    return jsonify({'error': 'Processing info not found'}), 404

@app.route('/api/timeline_stats/<file_hash>')
def get_timeline_stats(file_hash):
    """API endpoint to get the frame-by-frame timeline statistics"""
    timeline_stats_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'timeline_stats.json')
    
    if not os.path.exists(timeline_stats_path):
        return jsonify({'error': 'Timeline statistics not found'}), 404
        
    with open(timeline_stats_path, 'r') as f:
        timeline_stats = f.read()
        
    return timeline_stats, 200, {'Content-Type': 'application/json'}

@app.route('/api/coverage_per_frame/<file_hash>')
def get_coverage_per_frame(file_hash):
    """API endpoint to get per-frame coverage percentages per logo"""
    coverage_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'coverage_per_frame.json')
    if not os.path.exists(coverage_path):
        return jsonify({'error': 'Coverage per frame not found'}), 404
    with open(coverage_path, 'r') as f:
        cov = f.read()
    return cov, 200, {'Content-Type': 'application/json'}

@app.route('/api/prominence_per_frame/<file_hash>')
def get_prominence_per_frame(file_hash):
    """API endpoint to get per-frame prominence scores per logo if available"""
    prom_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'prominence_per_frame.json')
    if not os.path.exists(prom_path):
        return jsonify({'error': 'Prominence per frame not found'}), 404
    with open(prom_path, 'r') as f:
        prom = f.read()
    return prom, 200, {'Content-Type': 'application/json'}

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

    # Prepare file info for the agent (include video metadata for precise FPS)
    video_metadata = stats_data.get('video_metadata') or stats_data.get('video_meta') or {}
    frame_detections_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'frame_detections.jsonl')
    raw_video_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'raw.mp4')
    coverage_per_frame_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'coverage_per_frame.json')
    file_info = {
        'stats_data': stats_data,
        'timeline_stats_data': timeline_stats_data,
        'video_path': video_path,
        'video_metadata': video_metadata,
        'frame_detections_path': frame_detections_path,
        'raw_video_path': raw_video_path,
        'coverage_per_frame_path': coverage_per_frame_path,
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
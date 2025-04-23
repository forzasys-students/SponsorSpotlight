import hashlib
from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import sys
import json
from backend.progress_manager import ProgressManager, ProgressStage
from flask_socketio import SocketIO
from inference.inference import run_from_app
import time
from .timing_logger import timing_logger

progress = ProgressManager()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Getting file hash to check if processed version exists already.
# If not then hash is sent to script to make unique file name.
def get_hashed_filename(input_path):
    if input_path.startswith(('http://', 'https://')):
        return hashlib.md5(input_path.encode()).hexdigest()
    else:
        with open(input_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

# SocketIO callback. Used for tracking progress during process
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

def progress_callback(data):
    socketio.emit('progress_update', data)

progress.register_callback(progress_callback)
progress_instance = progress

@app.route('/progress')
def get_progress():
    return jsonify(progress.get_progress())

@app.route("/outputs/<filename>")
def serve_output(filename):
    return send_from_directory(app.config["OUTPUT_FOLDER"], filename)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/', methods=['POST'])
def predict_file():
    start_total_time_post_to_return = time.perf_counter()
    progress.update_progress(
        ProgressStage.RECEIVING_MEDIA,
        "Media received"
    )

    mode = None
    input_path = None
    file_hash = None
    
    start_check_url_file_type = time.perf_counter()
    if request.content_type == "application/json":
        data = request.get_json()
        video_url = data.get("videoUrl")
        if not video_url:
            return jsonify({"error": "No URL shared"}), 400

        mode = "video"
        input_path = video_url
        end_check_url_file_type = time.perf_counter()
        timing_logger.info(
            f"Checking url / file type and saving path - {end_check_url_file_type - start_check_url_file_type:2f}"
            )
        start_hash_filename = time.perf_counter()
        file_hash = get_hashed_filename(video_url)
        end_hash_filename = time.perf_counter()
        timing_logger.info(f"Hashing filename - {end_hash_filename - start_hash_filename:2f}")
    elif "file" in request.files:
        file = request.files['file']
        file_ext = os.path.splitext(file.filename)[-1].lower()
        mode = 'image' if file_ext in ['.jpg', '.jpeg', '.png'] else 'video'

        input_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(input_path)
        end_check_url_file_type = time.perf_counter()
        timing_logger.info(
            f"Checking url / file type and saving path - {end_check_url_file_type - start_check_url_file_type:2f}"
            )

        start_hash_filename = time.perf_counter()
        file_hash = get_hashed_filename(input_path)
        end_hash_filename = time.perf_counter()
        timing_logger.info(f"Hashing filename - {end_hash_filename - start_hash_filename:2f}")
    else:
        return jsonify({"error": "No valid input provided"}), 400
    
    progress.update_progress(
        ProgressStage.CHECKING_CACHE,
        "Checking for cached results"
    )

    start_check_cache = time.perf_counter()
    output_ext = 'mp4' if mode == 'video' else 'jpg'
    output_filename = f'output_{file_hash}.{output_ext}'
    stats_filename = f'logo_stats_{file_hash}.json'
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)
    stats_path = os.path.join(OUTPUT_FOLDER, stats_filename)

    if os.path.exists(output_path) and os.path.exists(stats_path):
        progress.update_progress(
            ProgressStage.COMPLETE,
            "Cached results found, returning"
        )
        end_check_cache = time.perf_counter()
        timing_logger.info(f"Checking for cached results - {end_check_cache - start_check_cache:2f}")
        end_total_time_post_to_return = time.perf_counter()
        timing_logger.info(f"Total submit to return time - {end_total_time_post_to_return - start_total_time_post_to_return:2f}")
        with open(stats_path, "r") as f:
            stats_data = json.load(f)
        return jsonify({
            "fileUrl": f"/outputs/{output_filename}",
            "stats": stats_data
        })
    end_check_cache = time.perf_counter()
    timing_logger.info(f"Checking for cached results - {end_check_cache - start_check_cache:2f}")

    try:
        result = run_from_app(mode, input_path, file_hash)

        if not os.path.exists(output_path):
            return jsonify({
            "error": "Output file not created",
            "details": result.stderr
            }), 500
        
        # Fetching logo stats
        stats_data = {}
        if os.path.exists(stats_path):
            with open(stats_path, "r") as f:
                stats_data = json.load(f)

        end_total_time_post_to_return = time.perf_counter()
        timing_logger.info(f"Total submit to return time - {end_total_time_post_to_return - start_total_time_post_to_return:2f}")
        return jsonify({
        "fileUrl": f"/outputs/{output_filename}",
        "stats": stats_data
        })
    
    except Exception as e:
        return jsonify({"error": f"Inference failed: {str(e)}"}), 500

if __name__ == '__main__':
    socketio.run(app, debug=True)
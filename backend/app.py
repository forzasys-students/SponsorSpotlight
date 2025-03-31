from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import sys
import subprocess
import json
import shutil 

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route("/outputs/<filename>")
def serve_output(filename):
    return send_from_directory(app.config["OUTPUT_FOLDER"], filename)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/', methods=['POST'])
def predict_file():
    if request.content_type == "application/json":
        data = request.get_json()
        video_url = data.get("videoUrl")
        if not video_url:
            return jsonify({"error": "No URL shared"}), 400

        mode = "video"
        command = [sys.executable, "inference.py", mode, video_url]

    elif "file" in request.files:
        file = request.files['file']
        file_ext = os.path.splitext(file.filename)[-1].lower()
        mode = 'image' if file_ext in ['.jpg', '.jpeg', '.png'] else 'video'

        input_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(input_path)

        command = [sys.executable, "inference.py", mode, input_path]

    else: 
        return jsonify({"error": "No valid input provided"}), 400

    cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'inference'))

    try:
        subprocess.run(command, check=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Inference failed: {str(e)}"}), 500

    # Output file paths
    raw_output = os.path.join(cwd, 'output.jpg' if mode == 'image' else 'output.mp4')
    final_output = os.path.join(OUTPUT_FOLDER, 'output.jpg' if mode == 'image' else 'output.mp4')

    if not os.path.exists(raw_output):
        return jsonify({"error": f"Output file {raw_output} not found!"}), 500


    shutil.move(raw_output, final_output)
    # Fetching logo stats
    stats_path = os.path.join(cwd, 'logo_stats.json')
    stats_data = {}
    if os.path.exists(stats_path):
        with open(stats_path, "r") as f:
            stats_data = json.load(f)

    response_data = {
        "fileUrl": f"/outputs/{os.path.basename(final_output)}",
        "stats": stats_data
    }

    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True)

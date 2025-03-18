from flask import Flask, render_template, request, jsonify, send_file
import os
import sys
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads') 
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

    output_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'inference', 'output.jpg' if mode == 'image' else 'output.mp4'))

    if not os.path.exists(output_file):
        return jsonify({"error": f"Output file {output_file} not found!"}), 500

    if mode == 'video':
        converted_output = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'inference', 'output_converted.mp4'))

        subprocess.run([
            "ffmpeg", "-i", output_file, "-c:v", "libx264",
            "-preset", "slow", "-crf", "23", "-c:a", "aac",
            "-b:a", "128k", converted_output
        ], check=True)

        return send_file(converted_output, as_attachment=True, mimetype='video/mp4')

    return send_file(output_file, as_attachment=True, mimetype='image/jpeg')

if __name__ == '__main__':
    app.run(debug=True)

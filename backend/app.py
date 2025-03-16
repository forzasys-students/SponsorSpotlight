from flask import Flask, render_template, request, jsonify, send_file
import os
import sys
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

app = Flask(__name__)

# Constant folder
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads') 
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

#Endpoint for video uploads
@app.route('/', methods=['POST'])
def predict_file():
    #URL input
    if request.content_type == "application/json":
        data = request.get_json()
        video_url = data.get("videoUrl")
        if not video_url:
            return jsonify({"error": "No URL shared"}), 400

        mode = "video" 
        command = ["python3", "inference.py", mode, video_url]

    elif "file" in request.files:
        file = request.files['file']
        file_ext = os.path.splitext(file.filename)[-1].lower()
        #Checking if file is image or video
        mode = 'image' if file_ext in ['.jpg', '.jpeg', '.png'] else 'video'

        #Creating unique file path
        input_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(input_path)

        command = ['python3', 'inference.py', mode, input_path]
    
    else: 
        return jsonify({"error": "No valid input provided"}), 400
    
    #Running inference.py
    subprocess.run(command, check=True, cwd=os.path.join(os.path.dirname(__file__), '..', 'inference'))


    output_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'inference', 'output.jpg' if mode == 'image' else 'output.mp4'))
    if mode == 'video':
        #Converting output to H.264 format if mode is "video" as mp4v is not supported in all browsers
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
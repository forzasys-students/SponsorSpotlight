from flask import Flask, render_template, request, jsonify, send_file
import os
import sys
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from inference.inference  import *

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
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    file_ext = os.path.splitext(file.filename)[-1].lower()

    #Creating unique file path
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)

    file.save(input_path)

    #Checking if file is image or video
    mode = 'image' if file_ext in ['.jpg', '.jpeg', '.png'] else 'video'

    command = ['python3', 'inference.py', mode, input_path]
    subprocess.run(command, check=True, cwd=os.path.join(os.path.dirname(__file__), '..', 'inference'))
    
    output_file = os.path.join(os.path.dirname(__file__), '..', 'inference', 'output.jpg' if mode == 'image' else 'output.mp4')

    return send_file(output_file, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
from flask import Blueprint, request, Response, send_from_directory
import os
import re

video_bp = Blueprint('video_bp', __name__)

def get_chunk(byte1=None, byte2=None, full_path=None):
    file_size = os.stat(full_path).st_size
    start = 0
    
    if byte1 < file_size:
        start = byte1
    if byte2:
        length = byte2 + 1 - byte1
    else:
        length = file_size - start
    
    with open(full_path, 'rb') as f:
        f.seek(start)
        chunk = f.read(length)
    return chunk, start, length, file_size

@video_bp.route('/stream/<file_hash>/<video_type>')
def stream(file_hash, video_type):
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    if video_type == 'raw':
        video_filename = 'raw.mp4'
    elif video_type == 'output':
        video_filename = 'output.mp4'
    else:
        return "Invalid video type", 400

    video_path = os.path.join(base_dir, 'frontend', 'static', 'results', file_hash, video_filename)

    if not os.path.exists(video_path):
        return "Video not found", 404

    range_header = request.headers.get('Range', None)
    byte1, byte2 = 0, None
    if range_header:
        range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if range_match:
            groups = range_match.groups()
            byte1 = int(groups[0])
            if groups[1]:
                byte2 = int(groups[1])

    chunk, start, length, file_size = get_chunk(byte1, byte2, video_path)
    
    resp = Response(chunk, 206, mimetype='video/mp4', content_type='video/mp4', direct_passthrough=True)
    resp.headers.add('Content-Range', f'bytes {start}-{start + length - 1}/{file_size}')
    resp.headers.add('Accept-Ranges', 'bytes')
    return resp

def register_video_routes(app):
    """Registers the video blueprint with the Flask app."""
    app.register_blueprint(video_bp)

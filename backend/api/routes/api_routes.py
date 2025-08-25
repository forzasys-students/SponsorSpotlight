"""
API routes - stats, timeline, frame data, preview, etc.
"""
from flask import jsonify, request
import os
import json
import base64
import subprocess


def register_api_routes(app):
    """Register API routes"""
    
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

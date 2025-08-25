"""
Main application routes - index, upload, processing
"""
from flask import render_template, request, jsonify, redirect, url_for, flash, session
import os
import uuid
from werkzeug.utils import secure_filename


def register_main_routes(app, inference_manager, allowed_file, get_file_hash, get_url_hash):
    """Register main application routes"""
    
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
        stats_path = os.path.join(result_dir, 'stats.json')
        if os.path.exists(stats_path):
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
            stats_path = os.path.join(result_dir, 'stats.json')
            if os.path.exists(stats_path):
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
        stats_path = os.path.join(result_dir, 'stats.json')
        if os.path.exists(stats_path):
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
        stats_path = os.path.join(result_dir, 'stats.json')
        if os.path.exists(stats_path):
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

    @app.route('/progress')
    def get_progress():
        """API endpoint to get the current processing progress"""
        from backend.utils.progress_manager import ProgressManager
        progress_manager = ProgressManager()
        progress_data = progress_manager.get_progress()
        return jsonify(progress_data)

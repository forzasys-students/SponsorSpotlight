"""
File management routes - listing existing files, viewing results, dashboard
"""
from flask import render_template, redirect, url_for, flash, session
import os
import json


def register_file_routes(app, allowed_file, file_cache):
    """Register file management routes"""
    
    @app.route('/list_existing_files')
    def list_existing_files():
        """List all existing files and URL-based results"""
        files = []
        processed_hashes = set()
        
        # First, scan uploads directory for local files
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if allowed_file(filename):
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                metadata = file_cache.get_file_metadata(file_path)
                if not metadata:
                    continue

                file_hash = metadata['hash']
                file_size_mb = round(metadata['size'] / (1024 * 1024), 2)
                file_extension = filename.rsplit('.', 1)[1].lower()
                file_type = 'video' if file_extension in ['mp4', 'avi', 'mov', 'webm'] else 'image'
                
                # Check if results already exist (only need stats.json)
                result_dir = os.path.join(app.config['RESULTS_FOLDER'], file_hash)
                stats_path = os.path.join(result_dir, 'stats.json')
                is_processed = os.path.exists(stats_path)
                
                if is_processed:
                    processed_hashes.add(file_hash)
                
                files.append({
                    'filename': filename,
                    'size_mb': file_size_mb,
                    'type': file_type,
                    'hash': file_hash,
                    'is_processed': is_processed,
                    'source': 'upload'
                })
        
        # Then, scan results directory for URL-based results that don't have upload files
        for result_hash in os.listdir(app.config['RESULTS_FOLDER']):
            result_dir = os.path.join(app.config['RESULTS_FOLDER'], result_hash)
            stats_path = os.path.join(result_dir, 'stats.json')
            
            # Skip if this hash is already covered by an upload file
            if result_hash in processed_hashes:
                continue
                
            # Skip if no stats file (incomplete processing)
            if not os.path.exists(stats_path):
                continue
                
            # Check if this is a URL-based result by looking for URL info in stats
            try:
                with open(stats_path, 'r') as f:
                    stats_data = json.load(f)
                    # Look for URL-related metadata
                    url_info = stats_data.get('source_url') or stats_data.get('url') or stats_data.get('input_path', '')
                    
                    # If it looks like a URL or we can't determine the source, treat as URL-based
                    if url_info.startswith('http') or '://' in url_info:
                        # Determine file type from stats or assume video
                        file_type = 'video'  # URLs are typically videos
                        
                        files.append({
                            'filename': f"URL: {url_info.split('/')[-1] or 'stream'}",
                            'size_mb': 0,  # Unknown size for URLs
                            'type': file_type,
                            'hash': result_hash,
                            'is_processed': True,
                            'source': 'url',
                            'url': url_info
                        })
                    elif not url_info or url_info == '':
                        # If no source info, assume it's a URL-based result
                        files.append({
                            'filename': f"Remote: {result_hash[:8]}",
                            'size_mb': 0,
                            'type': 'video',
                            'hash': result_hash,
                            'is_processed': True,
                            'source': 'url',
                            'url': ''
                        })
            except (json.JSONDecodeError, IOError):
                # If we can't read the stats, skip this result
                continue
        
        return render_template('existing_files.html', files=files)

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
        # Construct the path to the stats file
        stats_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'stats.json')
        if not os.path.exists(stats_path):
            flash('Dashboard data not found. The file may still be processing or an error occurred.')
            return redirect(url_for('index'))
        
        # Try to get file info from session, but don't require it
        file_info = session.get('file_info', {})
        
        # If session doesn't have the right file or no session, try to determine from uploaded files
        if not file_info or file_info.get('hash') != file_hash:
            # Look for the original file in uploads to get file info
            for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                if allowed_file(filename):
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    # Use the cache to get the hash
                    if os.path.isfile(file_path) and file_cache.get_hash(file_path) == file_hash:
                        file_extension = filename.rsplit('.', 1)[1].lower()
                        file_type = 'video' if file_extension in ['mp4', 'avi', 'mov', 'webm'] else 'image'
                        file_info = {
                            'type': file_type,
                            'hash': file_hash,
                            'original_name': filename
                        }
                        break
            else:
                # Fallback: determine type from stats or assume video
                file_info = {
                    'type': 'video',  # Default assumption
                    'hash': file_hash,
                    'original_name': f'{file_hash[:8]}.mp4'  # Fallback name
                }
        
        return render_template('dashboard.html',
                              file_type=file_info['type'],
                              file_hash=file_hash,
                              original_name=file_info['original_name'])

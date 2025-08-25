"""
Agent/AI routes - handling agentic queries and tasks
"""
from flask import jsonify, request
import os
import json
import threading


def register_agent_routes(app, agent_task_manager):
    """Register agent-related routes"""
    
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
            
        # Get the video path for the share node (use raw video for processing)
        video_path = os.path.join(app.config['RESULTS_FOLDER'], file_hash, 'raw.mp4')

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

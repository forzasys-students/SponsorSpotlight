#!/usr/bin/env python3
"""
Entry point script to run the SponsorSpotlight Flask application.
"""
import os
import sys

# Add the project root to the path so we can import the backend package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.app import app

if __name__ == '__main__':
    # Create necessary directories if they don't exist
    os.makedirs(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'static', 'uploads'), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'static', 'results'), exist_ok=True)
    
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5005)
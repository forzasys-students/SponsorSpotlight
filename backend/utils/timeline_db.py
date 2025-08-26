"""
Timeline Database Manager

Handles SQLite storage and retrieval of per-frame timeline data including:
- Coverage percentages per frame per logo
- Prominence scores per frame per logo  
- Detection bounding boxes per frame per logo

This replaces the large JSON files (coverage_per_frame.json, prominence_per_frame.json, 
frame_detections.jsonl) with efficient database storage.
"""

import sqlite3
import json
import os
from typing import Dict, List, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)


class TimelineDatabase:
    """Manages SQLite database for timeline data storage and retrieval"""
    
    def __init__(self, db_path: str):
        """Initialize database connection and create tables if needed"""
        self.db_path = db_path
        self.conn = None
        self._ensure_connection()
        self._create_tables()
    
    def _ensure_connection(self):
        """Ensure database connection is open"""
        if self.conn is None:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.execute("PRAGMA journal_mode=WAL")  # Better for concurrent access
            self.conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes
    
    def _create_tables(self):
        """Create database tables for timeline data"""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS logos (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS timeseries (
                frame INTEGER NOT NULL,
                logo_id INTEGER NOT NULL,
                coverage REAL DEFAULT 0.0,
                prominence REAL DEFAULT 0.0,
                PRIMARY KEY (frame, logo_id),
                FOREIGN KEY (logo_id) REFERENCES logos(id)
            );
            
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                frame INTEGER NOT NULL,
                logo_id INTEGER NOT NULL,
                bbox_json TEXT NOT NULL,
                polygon_json TEXT,
                FOREIGN KEY (logo_id) REFERENCES logos(id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_timeseries_frame ON timeseries(frame);
            CREATE INDEX IF NOT EXISTS idx_timeseries_logo ON timeseries(logo_id);
            CREATE INDEX IF NOT EXISTS idx_detections_frame ON detections(frame);
            CREATE INDEX IF NOT EXISTS idx_detections_logo ON detections(logo_id);
        """)
        self.conn.commit()
    
    def get_or_create_logo_id(self, logo_name: str) -> int:
        """Get logo ID, creating if it doesn't exist"""
        cursor = self.conn.execute("SELECT id FROM logos WHERE name = ?", (logo_name,))
        result = cursor.fetchone()
        if result:
            return result[0]
        
        cursor = self.conn.execute("INSERT INTO logos (name) VALUES (?)", (logo_name,))
        self.conn.commit()
        return cursor.lastrowid
    
    def add_frame_data(self, frame: int, logo_name: str, coverage: float = 0.0, 
                      prominence: float = 0.0, detections: List[Dict] = None):
        """Add data for a single frame and logo"""
        logo_id = self.get_or_create_logo_id(logo_name)
        
        # Insert or update timeseries data
        self.conn.execute("""
            INSERT OR REPLACE INTO timeseries (frame, logo_id, coverage, prominence)
            VALUES (?, ?, ?, ?)
        """, (frame, logo_id, coverage, prominence))
        
        # Insert detection data if provided
        if detections:
            for detection in detections:
                bbox_json = json.dumps(detection.get('bbox', []))
                polygon_json = json.dumps(detection.get('polygon', []))
                self.conn.execute("""
                    INSERT INTO detections (frame, logo_id, bbox_json, polygon_json)
                    VALUES (?, ?, ?, ?)
                """, (frame, logo_id, bbox_json, polygon_json))
    
    def commit(self):
        """Commit pending transactions"""
        if self.conn:
            self.conn.commit()
    
    def get_coverage_series(self, logo_name: str, start_frame: int = None, 
                           end_frame: int = None, stride: int = 1) -> List[float]:
        """Get coverage series for a logo with optional frame range and stride"""
        logo_id_result = self.conn.execute("SELECT id FROM logos WHERE name = ?", (logo_name,)).fetchone()
        if not logo_id_result:
            return []
        
        logo_id = logo_id_result[0]
        
        query = "SELECT frame, coverage FROM timeseries WHERE logo_id = ?"
        params = [logo_id]
        
        if start_frame is not None:
            query += " AND frame >= ?"
            params.append(start_frame)
        if end_frame is not None:
            query += " AND frame <= ?"
            params.append(end_frame)
        
        query += " ORDER BY frame"
        
        cursor = self.conn.execute(query, params)
        results = cursor.fetchall()
        
        if stride == 1:
            return [row[1] for row in results]
        else:
            # Apply stride
            return [row[1] for i, row in enumerate(results) if i % stride == 0]
    
    def get_prominence_series(self, logo_name: str, start_frame: int = None, 
                             end_frame: int = None, stride: int = 1) -> List[float]:
        """Get prominence series for a logo with optional frame range and stride"""
        logo_id_result = self.conn.execute("SELECT id FROM logos WHERE name = ?", (logo_name,)).fetchone()
        if not logo_id_result:
            return []
        
        logo_id = logo_id_result[0]
        
        query = "SELECT frame, prominence FROM timeseries WHERE logo_id = ?"
        params = [logo_id]
        
        if start_frame is not None:
            query += " AND frame >= ?"
            params.append(start_frame)
        if end_frame is not None:
            query += " AND frame <= ?"
            params.append(end_frame)
        
        query += " ORDER BY frame"
        
        cursor = self.conn.execute(query, params)
        results = cursor.fetchall()
        
        if stride == 1:
            return [row[1] for row in results]
        else:
            # Apply stride
            return [row[1] for i, row in enumerate(results) if i % stride == 0]
    
    def get_frame_detections(self, frame: int) -> List[Dict]:
        """Get all detections for a specific frame"""
        query = """
            SELECT l.name, d.bbox_json, d.polygon_json
            FROM detections d
            JOIN logos l ON d.logo_id = l.id
            WHERE d.frame = ?
        """
        cursor = self.conn.execute(query, (frame,))
        results = cursor.fetchall()
        
        detections = []
        for logo_name, bbox_json, polygon_json in results:
            detection = {
                "class": logo_name,
                "bbox": json.loads(bbox_json) if bbox_json else [],
                "polygon": json.loads(polygon_json) if polygon_json else []
            }
            detections.append(detection)
        
        return detections
    
    def get_timeline_stats(self) -> Dict[str, List[int]]:
        """
        Get frame lists for each logo, compatible with older SQLite versions.
        This function is intentionally compatible with older SQLite versions that
        do not support ORDER BY within GROUP_CONCAT.
        """
        query = """
            SELECT l.name, t.frame
            FROM timeseries t
            JOIN logos l ON t.logo_id = l.id
            WHERE t.coverage > 0 OR t.prominence > 0
            ORDER BY l.name, t.frame
        """
        cursor = self.conn.execute(query)
        results = cursor.fetchall()
        
        timeline_stats = {}
        for logo_name, frame in results:
            if logo_name not in timeline_stats:
                timeline_stats[logo_name] = []
            timeline_stats[logo_name].append(frame)
        
        return timeline_stats
    
    def get_all_logos(self) -> List[str]:
        """Get list of all logo names in database"""
        cursor = self.conn.execute("SELECT name FROM logos ORDER BY name")
        return [row[0] for row in cursor.fetchall()]
    
    def get_max_frame(self) -> int:
        """Get the maximum frame number in the database"""
        cursor = self.conn.execute("SELECT MAX(frame) FROM timeseries")
        result = cursor.fetchone()
        return result[0] if result[0] is not None else 0
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def create_compatible_json_from_db(db_path: str, output_dir: str, total_frames: int):
    """
    Create JSON files compatible with existing frontend from SQLite database
    This is a migration helper to maintain compatibility
    """
    with TimelineDatabase(db_path) as db:
        logos = db.get_all_logos()
        
        # Create coverage_per_frame.json
        coverage_data = {"frames_total": total_frames, "per_logo": {}}
        for logo in logos:
            series = db.get_coverage_series(logo)
            # Pad to total_frames with zeros if needed
            while len(series) < total_frames:
                series.append(0.0)
            coverage_data["per_logo"][logo] = series
        
        coverage_path = os.path.join(output_dir, "coverage_per_frame.json")
        with open(coverage_path, 'w') as f:
            json.dump(coverage_data, f, indent=2)
        
        # Create prominence_per_frame.json
        prominence_data = {"frames_total": total_frames, "per_logo": {}}
        for logo in logos:
            series = db.get_prominence_series(logo)
            # Pad to total_frames with zeros if needed
            while len(series) < total_frames:
                series.append(0.0)
            prominence_data["per_logo"][logo] = series
        
        prominence_path = os.path.join(output_dir, "prominence_per_frame.json")
        with open(prominence_path, 'w') as f:
            json.dump(prominence_data, f, indent=2)
        
        # Create timeline_stats.json
        timeline_stats = db.get_timeline_stats()
        timeline_path = os.path.join(output_dir, "timeline_stats.json")
        with open(timeline_path, 'w') as f:
            json.dump(timeline_stats, f, indent=2)
        
        logger.info(f"Created compatible JSON files in {output_dir}")


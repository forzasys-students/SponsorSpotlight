"""
File Metadata Cache

This utility manages a persistent cache for file metadata (hash, size, modification time)
to avoid expensive re-computation for large files on every request. The cache is stored
as a JSON file.
"""
import os
import hashlib
import json
import time
from typing import Dict, Any

class FileCache:
    """Manages a JSON-based cache for file metadata"""
    
    def __init__(self, cache_path: str):
        """
        Initializes the cache manager.
        
        Args:
            cache_path (str): The path to the JSON file used for caching.
        """
        self.cache_path = cache_path
        self.cache = self._load_cache()
        self.dirty = False

    def _load_cache(self) -> Dict[str, Any]:
        """Loads the cache from the JSON file."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self):
        """Saves the cache to the JSON file if it has changed."""
        if self.dirty:
            try:
                with open(self.cache_path, 'w') as f:
                    json.dump(self.cache, f, indent=4)
                self.dirty = False
            except IOError:
                # Handle potential write errors
                pass

    def _get_file_hash(self, file_path: str) -> str:
        """Computes the MD5 hash of a file."""
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5()
            while chunk := f.read(8192):
                file_hash.update(chunk)
        return file_hash.hexdigest()

    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Retrieves metadata for a file, using the cache if possible.
        
        If the file is not in the cache or has been modified, it re-computes
        the metadata and updates the cache.
        """
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return None

        file_stat = os.stat(file_path)
        file_mtime = file_stat.st_mtime
        file_size = file_stat.st_size
        
        cached_data = self.cache.get(file_path)
        
        if cached_data and cached_data.get('mtime') == file_mtime and cached_data.get('size') == file_size:
            return cached_data
            
        # If not in cache or modified, compute new hash
        file_hash = self._get_file_hash(file_path)
        
        metadata = {
            'hash': file_hash,
            'size': file_size,
            'mtime': file_mtime
        }
        
        self.cache[file_path] = metadata
        self.dirty = True
        self._save_cache()  # Save immediately after modification
        
        return metadata

    def get_hash(self, file_path: str) -> str:
        """Convenience method to get only the hash for a file."""
        metadata = self.get_file_metadata(file_path)
        return metadata['hash'] if metadata else None
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._save_cache()


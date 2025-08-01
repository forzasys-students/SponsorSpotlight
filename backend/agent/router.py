from openai import OpenAI
from backend.agent.config import config_manager
from backend.agent.nodes.analysis_node import AnalysisNode
from backend.agent.nodes.share_node import ShareNode
import re

class AgentRouter:
    """
    The main agentic router. It interprets the user's query and delegates
    the task to the appropriate specialized node.
    """
    def __init__(self):
        self.api_key = config_manager.get_api_key()
        self.model = config_manager.get_model()
        self.client = OpenAI(api_key=self.api_key)
        self.analysis_node = AnalysisNode()
        self.share_node = ShareNode()

    def route_query(self, query, file_info, task_manager=None, task_id=None):
        """
        Routes the user's query to the correct node.
        """
        normalized_query = query.lower()
        
        analysis_keywords = ['analyze', 'analysis', 'insight', 'report', 'review', 'summary']
        share_keywords = ['share', 'post', 'instagram']

        if any(keyword in normalized_query for keyword in analysis_keywords):
            return self.analysis_node.analyze(file_info['stats_data'])
        elif any(keyword in normalized_query for keyword in share_keywords):
            caption = self._extract_caption(query)
            # This is now an async task, so it doesn't return directly
            self.share_node.share_video(file_info['video_path'], caption, task_manager, task_id)
        else:
            return self._handle_unknown_query()

    def _extract_caption(self, query):
        """
        Extracts a caption from the user's query.
        """
        match = re.search(r'caption(?: is|:)?\s*["\'](.*?)["\']', query, re.IGNORECASE)
        if match:
            return match.group(1)
        return "Check out this video analysis from SponsorSpotlight!"

    def _handle_unknown_query(self):
        """
        Handles queries that don't match any known nodes.
        """
        return "I can't handle that request. I can analyze results or share videos to Instagram."

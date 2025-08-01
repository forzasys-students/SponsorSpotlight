from openai import OpenAI
from backend.agent.config import config_manager
from backend.agent.nodes.analysis_node import AnalysisNode

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

    def route_query(self, query, stats_data):
        """
        Routes the user's query to the correct node.

        Args:
            query (str): The user's query.
            stats_data (dict): The statistics data to be used by the nodes.

        Returns:
            str: The result from the selected node.
        """
        # For now, we have a simple routing logic. As more nodes are added,
        # this will become a more sophisticated LLM-based router.
        
        # Normalize the query for simple keyword matching
        normalized_query = query.lower()
        
        # Keywords for analysis
        analysis_keywords = ['analyze', 'analysis', 'insight', 'report', 'review', 'summary']

        if any(keyword in normalized_query for keyword in analysis_keywords):
            # Delegate to the AnalysisNode
            return self.analysis_node.analyze(stats_data)
        else:
            return self._handle_unknown_query()

    def _handle_unknown_query(self):
        """
        Handles queries that don't match any known nodes.
        In the future, this could use an LLM to provide a more helpful response.
        """
        return "I'm sorry, I can't handle that request yet. I can currently only analyze the results. Please try a query like 'analyze the data'."

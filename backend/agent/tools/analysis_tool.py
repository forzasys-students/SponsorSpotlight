from langchain_core.tools import tool
from backend.agent.nodes.analysis_node import AnalysisNode

@tool
def analyze_video(file_info: dict) -> str:
    """
    Analyzes the logo detection data from a sports broadcast to provide
    actionable insights for a brand manager or marketing team.
    Use this tool to get a general analysis of the video's performance.
    """
    stats_data = file_info.get('stats_data', {})
    analysis_node = AnalysisNode()
    return analysis_node.analyze(stats_data)

from openai import OpenAI
from backend.agent.config import config_manager
import json

class AnalysisNode:
    """
    A specialized agent node that analyzes logo detection data using an LLM
    to generate expert-level insights.
    """
    def __init__(self):
        self.api_key = config_manager.get_api_key()
        self.model = config_manager.get_model()
        self.client = OpenAI(api_key=self.api_key)

    def analyze(self, stats_data):
        """
        Analyzes the provided statistics data and returns insights.

        Args:
            stats_data (dict): The logo detection statistics.

        Returns:
            str: The generated analysis as a markdown-formatted string.
        """
        system_prompt = self._create_system_prompt()
        user_prompt = self._create_user_prompt(stats_data)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=600,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return "An error occurred while generating the analysis. Please check your API key and try again."

    def _create_system_prompt(self):
        """Creates the system prompt to set the context for the LLM."""
        return """
        You are a technical expert in sports marketing and sponsorship analytics.
        Your task is to analyze logo detection data from a sports broadcast and provide
        CONCISE, TECHNICAL insights focused on actionable data points.

        Be extremely CONCISE - keep your analysis under 250 words total.

        Focus on:
        - Specific timestamps with highest logo exposure (e.g., "From 5:20 to 7:15, Brand X has 80% visibility")
        - Technical metrics like peak exposure periods, visibility percentages, and detection counts
        - Direct, actionable recommendations with specific timestamps and metrics
        - Highlight the 2-3 most important insights only

        Format your response in short, bullet-point style markdown with clear section headers.
        Avoid lengthy explanations and focus on precise, technical data points.
        """

    def _create_user_prompt(self, stats_data):
        """Creates the user prompt with the data to be analyzed."""
        pretty_json = json.dumps(stats_data, indent=2)
        return f"""
        Here is the logo detection data from a recent broadcast.
        Please provide a detailed analysis based on this data.
        The timestamp is pointing to seconds in the video.

        Data:
        ```json
        {pretty_json}
        ```
        """

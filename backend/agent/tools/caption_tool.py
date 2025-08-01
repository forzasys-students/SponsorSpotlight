from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from backend.agent.config import config_manager

@tool
def generate_share_caption(brand_name: str, clip_start_time: float, clip_end_time: float) -> str:
    """
    Generates an engaging caption for sharing a video clip on social media.
    Use this tool to create a caption for a video clip.
    """
    api_key = config_manager.get_api_key()
    model = config_manager.get_model()
    
    llm = ChatOpenAI(api_key=api_key, model=model, temperature=0.7)
    
    prompt = f"""
    You are a creative social media manager for a sports marketing analytics company.
    Generate a short, engaging caption for a 10-second video clip highlighting the brand '{brand_name}'.
    The clip is from {clip_start_time} to {clip_end_time} seconds of a longer video.
    
    Include relevant hashtags like #SponsorSpotlight, #{brand_name.replace(' ', '')}, #SportsMarketing.
    Keep the caption under 280 characters.
    """
    
    response = llm.invoke(prompt)
    return response.content

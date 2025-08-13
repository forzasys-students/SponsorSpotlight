from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from backend.agent.config import config_manager

@tool
def generate_share_caption(brand_name: str, clip_start_time: float = None, clip_end_time: float = None, clip_url: str = None) -> str:
    """
    Generates an engaging caption for sharing a video clip on social media.
    Use this tool to create a caption for a video clip.
    """
    api_key = config_manager.get_api_key()
    model = config_manager.get_model()
    
    llm = ChatOpenAI(api_key=api_key, model=model, temperature=0.7)
    
    duration_hint = "" if (clip_start_time is None or clip_end_time is None) else f" The clip is from {clip_start_time} to {clip_end_time} seconds."
    prompt = f"""
    You are a creative social media manager for a sports marketing analytics company.
    Generate a short, engaging caption for a video clip highlighting the brand '{brand_name}'.{duration_hint}
    If the exact times are not provided, write a relevant caption without referring to timestamps. DO NOT MAKE HYPE TO IT.
    Include relevant hashtags like #SponsorSpotlight, #{brand_name.replace(' ', '')}, #SportsMarketing.
    Keep the caption under 280 characters.
    """
    
    response = llm.invoke(prompt)
    return response.content

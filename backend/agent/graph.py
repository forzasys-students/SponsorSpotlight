from typing import TypedDict, Annotated, Sequence, Optional, Any
import operator
from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
import inspect
import copy

from backend.agent.tools.analysis_tool import analyze_video
from backend.agent.tools.find_clip_tool import find_best_clip
from backend.agent.tools.create_clip_tool import create_video_clip
from backend.agent.tools.caption_tool import generate_share_caption
from backend.agent.tools.share_tool import share_on_instagram
from backend.agent.tools.metrics_tool import rank_brands
from backend.agent.config import config_manager

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    task_manager: Optional[Any]
    task_id: Optional[str]
    file_info: Optional[dict]

class AgentGraph:
    def __init__(self):
        self.tools = [
            analyze_video,
            find_best_clip,
            create_video_clip,
            generate_share_caption,
            share_on_instagram,
            rank_brands,
        ]
        self.tool_map = {tool.name: tool for tool in self.tools}
        
        api_key = config_manager.get_api_key()
        model_name = config_manager.get_model()
        
        self.model = ChatOpenAI(api_key=api_key, model=model_name, temperature=0, streaming=True)
        self.model = self.model.bind_tools(self.tools)
        
        self.workflow = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", self._call_model)
        workflow.add_node("action", self._execute_tools)
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "continue": "action",
                "end": END,
            },
        )
        workflow.add_edge("action", "agent")
        workflow.set_entry_point("agent")
        return workflow.compile()

    def _should_continue(self, state):
        messages = state["messages"]
        last_message = messages[-1]
        if not last_message.tool_calls:
            return "end"
        else:
            return "continue"

    def _call_model(self, state):
        messages = state["messages"]
        # Build a guiding system prompt that helps the LLM parse user intent
        file_info = state.get("file_info") or {}
        timeline = file_info.get("timeline_stats_data") or {}
        available_brands = list(timeline.keys())

        guidance_lines = [
            "You are an assistant that controls tools to analyze videos and create/share clips.",
            "- Normalize brand names: match case-insensitively and ignore trailing words like 'logo' or 'brand'.",
            "- Prefer selecting a brand from the available list when possible.",
            "- If user specifies a duration in natural language (e.g., 'four seconds'), convert it to seconds.",
            "- For 'create a N-second video with BRAND' requests: (1) find_best_clip for BRAND, (2) create_video_clip with end_time = start_time + N.",
            "- If duration is not provided, default to 10 seconds.",
            "- If the requested brand is not in the available list, ask the user to pick one, suggesting close matches.",
            "- For ranking questions (exposure percentage, detections, frames, time, coverage variants), call rank_brands(file_info, metric='<metric>', top_n=<N>).",
            "- For ambiguous 'coverage' metric, default to 'coverage_avg_present' and note the choice in your response.",
            "- When rank_brands returns structured JSON, present a concise, readable list (do not hallucinate additional brands).",
            "- Also include the raw JSON on a separate line prefixed exactly with 'RANK_JSON: ' so the UI can render a table (e.g., RANK_JSON: { ... }).",
        ]
        if available_brands:
            guidance_lines.append(f"Available brands in this video: {', '.join(available_brands[:100])}")

        system_prompt = "\n".join(guidance_lines)

        messages_with_system = [SystemMessage(content=system_prompt)] + list(messages)
        response = self.model.invoke(messages_with_system)
        return {"messages": [response]}

    def _execute_tools(self, state: AgentState) -> dict:
        messages = state['messages']
        last_message = messages[-1]
        tool_invocations = last_message.tool_calls
        
        tool_outputs = []

        for call in tool_invocations:
            tool_name = call['name']
            if tool_name in self.tool_map:
                tool_to_call = self.tool_map[tool_name]
                
                # Use a copy to avoid modifying the state history
                kwargs = copy.deepcopy(call['args'])

                # Inject state data directly into the tool call
                sig = inspect.signature(tool_to_call.func)
                if 'task_manager' in sig.parameters and state.get('task_manager'):
                    kwargs['task_manager'] = state['task_manager']
                if 'task_id' in sig.parameters and state.get('task_id'):
                    kwargs['task_id'] = state['task_id']
                if 'file_info' in sig.parameters and state.get('file_info'):
                    kwargs['file_info'] = state['file_info']

                try:
                    output = tool_to_call.invoke(kwargs)
                    tool_outputs.append(
                        ToolMessage(content=str(output), tool_call_id=call['id'])
                    )
                except Exception as e:
                    error_message = f"Error executing tool {tool_name}: {e}"
                    print(error_message)
                    tool_outputs.append(
                        ToolMessage(content=error_message, tool_call_id=call['id'])
                    )
            else:
                tool_outputs.append(
                    ToolMessage(content=f"Tool '{tool_name}' not found.", tool_call_id=call['id'])
                )
        
        return {"messages": tool_outputs}

    def run(self, inputs):
        return self.workflow.invoke(inputs)

agent_graph = AgentGraph()

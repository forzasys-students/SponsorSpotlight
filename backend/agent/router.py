from backend.agent.graph import agent_graph
from langchain_core.messages import HumanMessage

class AgentRouter:
    def route_query(self, query, file_info, task_manager=None, task_id=None):
        """
        Routes the user's query to the LangGraph agent.
        """
        try:
            print(f"[AgentRouter] Incoming query: {query}")
        except Exception:
            pass
        # The LLM doesn't need the full data blob, just the query.
        # The tools will access the data from the state.
        inputs = {
            "messages": [HumanMessage(content=query)],
            "file_info": file_info,
            "task_manager": task_manager,
            "task_id": task_id
        }
        
        # This will now run the entire graph, calling tools as needed
        result = agent_graph.run(inputs)
        
        # The final result will be in the last message
        final_response = result['messages'][-1].content
        
        if task_manager and task_id:
            task_manager.complete_task(task_id, final_response, success=True)
            
        return final_response

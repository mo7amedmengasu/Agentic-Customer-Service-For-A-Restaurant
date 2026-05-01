from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import HumanMessage
from app.my_agent.states.state import MainState

from app.my_agent.nodes.menu_agent_nodes import (
    tool_decision_node,
    reflection_node,
    tool_node,
    personalization_node,
    reflection_router,
    should_use_tools,
    capture_tool_result_node,
)

from app.my_agent.states.state import MainState


from langgraph.graph import StateGraph, END

def build_menu_graph(db): # Added db if you need to pass it to tools
    graph = StateGraph(MainState)

    # 1. Register only the actual worker nodes
    graph.add_node("tool_decision", tool_decision_node)
    graph.add_node("tool", tool_node)
    graph.add_node("capture_tool_result", capture_tool_result_node)
    graph.add_node("reflection", reflection_node)
    graph.add_node("personalization", personalization_node)

    # 2. Set the Entry Point
    graph.set_entry_point("tool_decision")

    # 3. Use should_use_tools as the ROUTER (Conditional Edge)
    # This replaces the direct edge to "should_use_tools"
    graph.add_conditional_edges(
        "tool_decision",  # Start here
        should_use_tools, # Run this function to decide where to go
        {
            "tool_node": "tool",
            "personalization_node": "personalization",
        }
    )

    # 4. Standard sequential edges
    graph.add_edge("tool", "capture_tool_result")
    graph.add_edge("capture_tool_result", "reflection")

    # 5. Reflection Router (Correctly implemented)
    graph.add_conditional_edges(
        "reflection",
        reflection_router,
        {
            "tool_decision": "tool_decision",
            "personalization": "personalization",
        }
    )

    graph.add_edge("personalization", END)

    return graph.compile()




def menu_agent(question: str, db):
    state: MainState = {
        "user_message": question,

        "messages": [
            HumanMessage(content=question)
        ],

        "intent": None,
        "response": None,
        "session_id": None,
        "customer_id": None,
        "order_id": None,

        "extracted_order": None,
        "extracted_complaint": None,

        "tool_result": None,
        "next_step": None,

        "order_ready": None,
        "order_confirmed": None,
        "missing_fields": None,
        "invalid_items": None,
        "requires_follow_up": None,
        "needs_human": None,

        "faq": None,

        "reflection_satisfied": None,
        "iteration_count": 0,
        "max_iterations": 3,
    }

    print("fresh menu state:", state)

    graph = build_menu_graph(db)

    result = graph.invoke(state)


    return result
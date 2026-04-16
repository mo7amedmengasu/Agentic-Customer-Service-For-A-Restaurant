from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from app.my_agent.state import AgentState
from app.my_agent.memory import get_checkpointer
from app.my_agent.intent_classifier import classify_intent
from app.my_agent.agents import faq_agent, menu_agent, order_agent, support_agent
from app.my_agent.tools import menu_tools, order_tools, support_tools


#Routing logic

def route_by_intent(state: AgentState) -> str:

    intent = state.get("intent", "faq")
    return intent  # returns "faq", "menu", "order", or "support"


def should_continue_menu(state: AgentState) -> str:

    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "menu_tools"
    return END


def should_continue_order(state: AgentState) -> str:
    
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "order_tools"
    return END


def should_continue_support(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "support_tools"
    return END


#Build the graph 

def build_graph():

    graph = StateGraph(AgentState)

  
    graph.add_node("intent_classifier", classify_intent)
    graph.add_node("faq", faq_agent)
    graph.add_node("menu", menu_agent)
    graph.add_node("order", order_agent)
    graph.add_node("support", support_agent)

 
    graph.add_node("menu_tools", ToolNode(menu_tools))
    graph.add_node("order_tools", ToolNode(order_tools))
    graph.add_node("support_tools", ToolNode(support_tools))

  
    graph.set_entry_point("intent_classifier")


    graph.add_conditional_edges(
        "intent_classifier",
        route_by_intent,
        {
            "faq": "faq",
            "menu": "menu",
            "order": "order",
            "support": "support",
        },
    )

    graph.add_edge("faq", END)

    graph.add_conditional_edges("menu", should_continue_menu, {"menu_tools": "menu_tools", END: END})
    graph.add_edge("menu_tools", "menu")  # after tool execution, re-invoke agent

    graph.add_conditional_edges("order", should_continue_order, {"order_tools": "order_tools", END: END})
    graph.add_edge("order_tools", "order")

 
    graph.add_conditional_edges("support", should_continue_support, {"support_tools": "support_tools", END: END})
    graph.add_edge("support_tools", "support")

    return graph.compile(checkpointer=get_checkpointer())


# Singleton compiled graph
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph

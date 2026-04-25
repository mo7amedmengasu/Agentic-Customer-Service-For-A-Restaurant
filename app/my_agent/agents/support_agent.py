from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.my_agent.nodes.support_agent_nodes import (
	ask_missing_complaint_info_node,
	check_order_context_node,
	create_ticket_node,
	escalate_to_human_node,
	extract_complaint_node,
	support_reasoning_node,
	support_response_node,
	validate_complaint_node,
)
from app.my_agent.states.state import MainState


def route_support_agent(state: MainState) -> str:
	return state.get("next_step", "final_response")


def build_support_agent_graph():
	graph = StateGraph(MainState)

	graph.add_node("support_reasoning", support_reasoning_node)
	graph.add_node("extract_complaint", extract_complaint_node)
	graph.add_node("validate_complaint", validate_complaint_node)
	graph.add_node("ask_missing_info", ask_missing_complaint_info_node)
	graph.add_node("check_order_context", check_order_context_node)
	graph.add_node("create_ticket", create_ticket_node)
	graph.add_node("escalate_to_human", escalate_to_human_node)
	graph.add_node("final_response", support_response_node)

	graph.set_entry_point("support_reasoning")
	graph.add_conditional_edges(
		"support_reasoning",
		route_support_agent,
		{
			"extract_complaint": "extract_complaint",
			"validate_complaint": "validate_complaint",
			"ask_missing_info": "ask_missing_info",
			"check_order_context": "check_order_context",
			"create_ticket": "create_ticket",
			"escalate_to_human": "escalate_to_human",
			"final_response": "final_response",
		},
	)

	graph.add_edge("extract_complaint", "support_reasoning")
	graph.add_edge("validate_complaint", "support_reasoning")
	graph.add_edge("ask_missing_info", "final_response")
	graph.add_edge("check_order_context", "support_reasoning")
	graph.add_edge("create_ticket", "final_response")
	graph.add_edge("escalate_to_human", "final_response")
	graph.add_edge("final_response", END)

	return graph.compile()


support_agent_graph = build_support_agent_graph()

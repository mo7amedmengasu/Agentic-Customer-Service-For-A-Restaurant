from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.my_agent.nodes.order_agent import (
	ask_confirmation_node,
	ask_missing_info_node,
	calculate_summary_node,
	extract_order_node,
	final_response_node,
	modify_order_node,
	order_reasoning_node,
	place_order_node,
	validate_order_node,
)
from app.my_agent.states.state import MainState


def route_order_agent(state: MainState) -> str:
	return state.get("next_step", "final_response")


def build_order_agent_graph():
	graph = StateGraph(MainState)

	graph.add_node("order_reasoning", order_reasoning_node)
	graph.add_node("extract_order", extract_order_node)
	graph.add_node("validate_order", validate_order_node)
	graph.add_node("ask_missing_info", ask_missing_info_node)
	graph.add_node("calculate_summary", calculate_summary_node)
	graph.add_node("ask_confirmation", ask_confirmation_node)
	graph.add_node("modify_order", modify_order_node)
	graph.add_node("place_order", place_order_node)
	graph.add_node("final_response", final_response_node)

	graph.set_entry_point("order_reasoning")
	graph.add_conditional_edges(
		"order_reasoning",
		route_order_agent,
		{
			"extract_order": "extract_order",
			"validate_order": "validate_order",
			"ask_missing_info": "ask_missing_info",
			"calculate_summary": "calculate_summary",
			"ask_confirmation": "ask_confirmation",
			"modify_order": "modify_order",
			"place_order": "place_order",
			"final_response": "final_response",
		},
	)

	graph.add_edge("extract_order", "order_reasoning")
	graph.add_edge("validate_order", "order_reasoning")
	graph.add_edge("ask_missing_info", "final_response")
	graph.add_edge("calculate_summary", "order_reasoning")
	graph.add_edge("ask_confirmation", "final_response")
	graph.add_edge("modify_order", "validate_order")
	graph.add_edge("place_order", "final_response")
	graph.add_edge("final_response", END)

	return graph.compile()


order_agent_graph = build_order_agent_graph()

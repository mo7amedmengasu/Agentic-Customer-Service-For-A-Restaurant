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
	next_step = state.get("next_step", "final_response")
	allowed = {"extract_complaint", "final_response"}
	return next_step if next_step in allowed else "final_response"


def route_after_validate(state: MainState) -> str:
	"""Deterministic routing after validate_complaint — no LLM involved."""
	next_step = state.get("next_step", "create_ticket")
	allowed = {"ask_missing_info", "escalate_to_human", "check_order_context", "create_ticket"}
	return next_step if next_step in allowed else "create_ticket"


def route_after_check_order(state: MainState) -> str:
	"""Deterministic routing after check_order_context."""
	next_step = state.get("next_step", "final_response")
	allowed = {"create_ticket", "final_response"}
	return next_step if next_step in allowed else "final_response"


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

	# support_reasoning only routes to extract_complaint or final_response (ticket-status path)
	graph.add_conditional_edges(
		"support_reasoning",
		route_support_agent,
		{
			"extract_complaint": "extract_complaint",
			"final_response": "final_response",
		},
	)

	# Deterministic: always validate right after extracting
	graph.add_edge("extract_complaint", "validate_complaint")

	# Deterministic: route based on what validate_complaint_node decided
	graph.add_conditional_edges(
		"validate_complaint",
		route_after_validate,
		{
			"ask_missing_info": "ask_missing_info",
			"escalate_to_human": "escalate_to_human",
			"check_order_context": "check_order_context",
			"create_ticket": "create_ticket",
		},
	)

	# Deterministic: route based on what check_order_context_node decided
	graph.add_conditional_edges(
		"check_order_context",
		route_after_check_order,
		{
			"create_ticket": "create_ticket",
			"final_response": "final_response",
		},
	)

	graph.add_edge("ask_missing_info", "final_response")
	graph.add_edge("create_ticket", "final_response")
	graph.add_edge("escalate_to_human", "final_response")
	graph.add_edge("final_response", END)

	return graph.compile()


support_agent_graph = build_support_agent_graph()

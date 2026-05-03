"""
workflow.py
===========
Main entry point for the multi-agent system.

Call `build_main_graph()` to obtain the compiled LangGraph that routes
every incoming user message through the orchestrator to the correct
sub-agent (menu, order, FAQ, or support).
"""

from dotenv import load_dotenv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def build_main_graph():
    """
    Build and return the compiled master orchestrator graph.

    This is the single entry point used by the chat API.  The graph
    classifies the user's intent on every turn and delegates to the
    appropriate sub-agent:

    - menu intent    → menu_agent (food items, prices, recommendations)
    - order intent   → order_agent (place / modify / track orders)
    - faq intent     → faq_agent  (hours, location, policies)
    - support intent → support_agent (complaints, refunds, problems)
    - unclear intent → asks the user a clarifying question

    Args:
        None — sub-agent graphs that need a db session (FAQ, menu) create
        their own sessions internally via SessionLocal().

    Returns:
        A compiled LangGraph CompiledGraph instance ready to `.invoke()`.
    """
    from app.my_agent.agents.intent_classifier import build_orchestrator_graph

    return build_orchestrator_graph()

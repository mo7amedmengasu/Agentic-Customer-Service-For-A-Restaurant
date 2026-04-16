"""
Task Agent Layer — four specialized agents as LangGraph nodes.

Each agent receives the full AgentState, builds a system prompt for its
domain, binds the relevant tools to the LLM, invokes it, and returns
the updated messages.

Architecture position: Task Agent Layer
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from app.core.config import settings
from app.my_agent.state import AgentState
from app.my_agent.tools import menu_tools, order_tools, support_tools


def _get_llm():
    """Shared LLM instance factory (points at Groq via OpenAI-compatible API)."""
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.GROQ_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=0.3,
    )


# ── FAQ Agent ─────────────────────────────────────────────────────────────

_FAQ_PROMPT = """You are a friendly FAQ assistant for a restaurant.
Answer general questions about the restaurant such as opening hours,
location, reservation policies, and other common queries.

If you don't know something specific, politely say so and suggest the
customer contact support. Keep answers concise and helpful.

Restaurant info:
- Open daily 10 AM – 11 PM
- Location: 123 Main Street
- Reservations accepted via phone or website
- Free parking available"""


def faq_agent(state: AgentState) -> dict:
    """Handles general restaurant questions."""
    llm = _get_llm()
    messages = [SystemMessage(content=_FAQ_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


# ── Menu Agent ────────────────────────────────────────────────────────────

_MENU_PROMPT = """You are a menu assistant for a restaurant.
Help customers browse the menu, find dishes, check prices, and get
recommendations. Use the available tools to fetch real menu data from
the database — never make up items or prices.

Always present menu items in a clear, appetizing way."""


def menu_agent(state: AgentState) -> dict:
    """Handles menu browsing. Has access to get_menu and search_menu tools."""
    llm = _get_llm().bind_tools(menu_tools)
    messages = [SystemMessage(content=_MENU_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


# ── Order Agent ───────────────────────────────────────────────────────────

_ORDER_PROMPT = """You are an order assistant for a restaurant.
Help customers place orders, check order status, and view their order history.

When placing an order:
1. Confirm the items and quantities with the customer before placing.
2. You need the customer's ID to place an order. If you don't have it, ask.
3. Use the place_order tool with the correct item details from the menu.

Use the available tools to interact with the order system — never fabricate
order numbers or statuses."""


def order_agent(state: AgentState) -> dict:
    """Handles order placement and status checks."""
    llm = _get_llm().bind_tools(order_tools)
    messages = [SystemMessage(content=_ORDER_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


# ── Support Agent ─────────────────────────────────────────────────────────

_SUPPORT_PROMPT = """You are a customer support agent for a restaurant.
Handle complaints, delivery issues, refund requests, and escalation.

You can track deliveries and check order statuses using the available tools.
If the issue cannot be resolved, let the customer know that a human agent
will follow up and provide them with a reference (the order ID).

Be empathetic and professional."""


def support_agent(state: AgentState) -> dict:
    """Handles support, complaints, and delivery tracking."""
    llm = _get_llm().bind_tools(support_tools)
    messages = [SystemMessage(content=_SUPPORT_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

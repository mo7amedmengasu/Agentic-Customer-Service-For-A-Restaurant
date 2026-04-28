from __future__ import annotations

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.my_agent.states.state import MainState
from app.my_agent.tools.memory_tools import (
    load_facts,
    remember_user_fact_tool,
    render_facts,
)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
    )


def load_user_facts_node(state: MainState, config: RunnableConfig) -> MainState:
    user_id = (
        state.get("customer_id")
        or (config.get("configurable") or {}).get("user_id")
    )
    if not user_id:
        return state

    facts = load_facts(int(user_id))
    if not facts:
        return state

    rendered = render_facts(facts)
    user_message = state.get("user_message") or ""
    state["user_message"] = f"[{rendered}]\n\n{user_message}"
    return state


_EXTRACTOR_PROMPT = """You are a memory extractor. Read the customer's
latest message and decide whether it contains a stable, durable fact about
the customer that should be remembered for future sessions.

Stable facts include: dietary_restriction, allergy, favorite_dish,
favorite_cuisine, delivery_address, name, phone.

Skip transient mentions ("I'd like a pizza tonight" is NOT a favorite).

If a fact is found, call remember_user_fact with the snake_case key and
the value. If multiple facts, call the tool multiple times. If nothing
qualifies, do NOT call any tool and just reply 'noop'."""


def extract_facts_node(state: MainState, config: RunnableConfig) -> MainState:
    user_id = (
        state.get("customer_id")
        or (config.get("configurable") or {}).get("user_id")
    )
    if not user_id:
        return state

    user_message = state.get("user_message") or ""
    if not user_message.strip():
        return state

    llm = _get_llm().bind_tools([remember_user_fact_tool])

    try:
        response = llm.invoke(
            [
                {"role": "system", "content": _EXTRACTOR_PROMPT},
                {"role": "user", "content": user_message},
            ],
            config={"configurable": {"user_id": int(user_id)}},
        )
        for tool_call in getattr(response, "tool_calls", []) or []:
            args = tool_call.get("args") or {}
            key = args.get("key")
            value = args.get("value")
            if key and value:
                remember_user_fact_tool.invoke(
                    {"key": key, "value": value},
                    config={"configurable": {"user_id": int(user_id)}},
                )
    except Exception:
        pass

    return state

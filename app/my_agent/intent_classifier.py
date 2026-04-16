from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from app.core.config import settings
from app.my_agent.state import AgentState

_CLASSIFIER_PROMPT = """You are an intent classifier for a restaurant customer service system.

Classify the customer's message into exactly ONE of these categories:

- "faq": General questions about the restaurant (hours, location, policies, etc.)
- "menu": Questions about the menu, food items, prices, ingredients, or recommendations.
- "order": Placing a new order, modifying an existing order, checking order status, or anything related to ordering food.
- "support": Complaints, delivery issues, refund requests, or requests to speak to a human.

Respond with ONLY the category name, nothing else. For example: menu"""


def classify_intent(state: AgentState) -> dict:
    """LangGraph node: classify the latest user message into an intent.
    """
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.GROQ_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=0,
    )

    # Get the last human message
    last_message = state["messages"][-1]

    response = llm.invoke([
        SystemMessage(content=_CLASSIFIER_PROMPT),
        last_message,
    ])

    # Parse — default to "faq" if the LLM returns something unexpected
    intent = response.content.strip().lower()
    if intent not in ("faq", "menu", "order", "support"):
        intent = "faq"

    return {"intent": intent}

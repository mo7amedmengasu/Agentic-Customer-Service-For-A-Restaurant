from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings


_PROMPT = """You are an intent classifier for a restaurant customer service system.

Classify the customer's latest message into exactly ONE category:

- "order": Anything related to the menu, food items, prices, ingredients,
  recommendations, placing an order, modifying an order, checking order
  status, or order history. (Browsing the menu and ordering both go here
  because the order agent has menu lookup tools.)
- "support": Complaints, delivery issues, refund requests, escalation to
  a human agent, or anything where the customer is upset.
- "faq": General questions about the restaurant (hours, location,
  reservations, payment methods, dress code, parking) — non-transactional.

Respond with ONLY the category name (faq | order | support). Nothing else."""


_VALID = {"faq", "order", "support"}


def classify_intent(user_message: str) -> str:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
        max_tokens=4,
    )
    response = llm.invoke([
        SystemMessage(content=_PROMPT),
        HumanMessage(content=user_message),
    ])
    intent = (response.content or "").strip().lower()
    return intent if intent in _VALID else "faq"

from typing import Annotated, List, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):

    messages: Annotated[List[BaseMessage], add_messages]
    intent: Optional[str]
    order_draft: Optional[List[dict]]
    customer_id: Optional[int]

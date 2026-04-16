import uuid
from langgraph.checkpoint.memory import MemorySaver

# Checkpointer (single instance shared across all sessions)

# Swap this with SqliteSaver or PostgresSaver for persistence across restarts.
_checkpointer = MemorySaver()


def get_checkpointer() -> MemorySaver:
  
    return _checkpointer



# Session ID management


def create_session_id() -> str:
   
    return str(uuid.uuid4())


def build_config(session_id: str) -> dict:

    return {"configurable": {"thread_id": session_id}}

from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from app.my_agent.states.state import MainState
from app.my_agent.tools.menu_agent_tools import create_menu_tools
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import ToolNode
from app.core.config import settings



llm = ChatOpenAI(api_key=settings.OPENAI_API_KEY, model="gpt-4o-mini", temperature=0)

tools = create_menu_tools()
llm_with_tools = llm.bind_tools(tools)




class ReflectionDecision(BaseModel):
    satisfied: bool
    reason: str


def tool_decision_node(state: MainState):
    user_q = state.get("user_message", "")
    history = state.get("messages", [])
    
    # 1. Create a text-based "Memory Bank"
    # We convert objects to strings so we don't trigger the 400 error roles.
    memory_context = ""
    for msg in history:
        if msg.type == "human":
            memory_context += f"Customer: {msg.content}\n"
        elif msg.type == "ai" and msg.content:
            memory_context += f"Assistant: {msg.content}\n"
    
    # 2. Construct a fresh, valid message list for OpenAI
    # This list ONLY contains a SystemMessage and a HumanMessage.
    # This is 100% safe from "role" errors.
    clean_messages = [
        SystemMessage(content=f"""You are a restaurant assistant. 
        PREVIOUS CONVERSATION CONTEXT:
        {memory_context}
        
        If the context above shows the user has a preference (like spicy food), 
        remember it. Use tools only for menu searches."""),
        HumanMessage(content=user_q)
    ]

    # 3. Invoke the LLM
    response = llm_with_tools.invoke(clean_messages)
    
    # 4. CRITICAL: Update the REAL state
    # We append the response so the rest of your graph (ToolNode, etc.) works.
    state["messages"].append(response)
    
    return state

def should_use_tools(state: MainState):
    last_msg = state["messages"][-1]

    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tool_node"

    return "personalization_node"

tool_node = ToolNode(tools)

def capture_tool_result_node(state: MainState):
    # This is now a ToolMessage containing the output of your menu tools
    last_message = state["messages"][-1]
    
    # Store the actual text/data result so the reflection node can see it
    state["tool_result"] = last_message.content
    return state


def reflection_node(state: MainState):
    # 1. Hard Stop: Prevent infinite loops/500 errors
    if state.get("iteration_count", 0) >= state.get("max_iterations", 3):
        state["reflection_satisfied"] = True
        return state

    # 2. Grab data for evaluation
    user_q = state["user_message"]
    tool_out = state.get("tool_result")

    # 3. Short-Circuit: If the tool explicitly said "No items found" or returned an empty list
    # We treat this as a SUCCESSFUL search (factually empty), not a failure.
    if tool_out == [] or (isinstance(tool_out, str) and "No items found" in tool_out):
        state["reflection_satisfied"] = True
        # Optional: Set a flag to help the response node know it's a 'not found' case
        return state

    # 4. Standard Evaluation (only if we actually have data to check)
    eval_messages = [
        SystemMessage(content="""You are a pragmatic quality checker. 
        Your ONLY goal is to verify if the Tool Search Result contains actual menu items.
        - If the tool returned specific dishes, prices, or a 'not found' confirmation, mark satisfied: true.
        - Only mark satisfied: false if the tool returned an error or completely irrelevant data."""),
        HumanMessage(content=f"User Question: {user_q}\nTool Result: {tool_out}")
    ]
    
    decision = llm.with_structured_output(ReflectionDecision).invoke(eval_messages)

    # 5. Update the control flags
    state["reflection_satisfied"] = decision.satisfied
    state["iteration_count"] = state.get("iteration_count", 0) + 1

    # 6. Handle Feedback Loop
    if not decision.satisfied:
        feedback_text = getattr(decision, 'feedback', "The previous result wasn't sufficient.")
        nudge_message = HumanMessage(
            content=f"Reflection Feedback: {feedback_text}. Please try again to answer: {user_q}"
        )
        state["messages"].append(nudge_message)

    return state
def personalization_node(state: MainState):
    history = state.get("messages", [])
    tool_data = state.get("tool_result")
    user_q = state.get("user_message", "")

    # 1. Check if the LLM already answered (like a greeting or "Hi")
    # if there's an AI message in history that ISN'T a tool call, use it!
    for msg in reversed(history):
        if msg.type == "ai" and not msg.tool_calls and msg.content:
            state["response"] = msg.content
            return state

    # 2. If we actually have tool data, then we do the "Safe Prompt" generation
    safe_history = [m for m in history if m.type in ["human", "ai"] and not (m.type == "ai" and m.tool_calls)]
    
    prompt = [
        SystemMessage(content="You are a restaurant assistant. Use the provided menu data."),
        *safe_history[-4:],
        HumanMessage(content=f"Question: {user_q}\n\nMenu Data: {tool_data}")
    ]

    response = llm.invoke(prompt)
    state["response"] = response.content
    return state
def reflection_router(state: MainState):
    if state["reflection_satisfied"]:
        return "personalization"

    if state["iteration_count"] >= state["max_iterations"]:
        return "personalization"

    return "tool_decision"
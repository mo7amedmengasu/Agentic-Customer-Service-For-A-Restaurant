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

print(tools)


class ReflectionDecision(BaseModel):
    satisfied: bool
    reason: str


def tool_decision_node(state: MainState):
    # 1. Clean the history to avoid the 400 error.
    # OpenAI requires a very specific order. If we are looping, 
    # the safest bet is to give it the original question + the 'nudge' feedback.
    
    user_q = state.get("user_message", "")
    
    # We find the last HumanMessage (which is our 'nudge' from reflection_node)
    # or just use the original question.
    messages_to_send = []
    
    # If the last message is the "Reflection Feedback" nudge, 
    # we send the original question + that nudge.
    if state["messages"] and isinstance(state["messages"][-1], HumanMessage) and "Reflection Feedback" in state["messages"][-1].content:
        messages_to_send = [
            HumanMessage(content=user_q),
            state["messages"][-1] # The nudge
        ]
    else:
        # First attempt: just the question
        messages_to_send = [HumanMessage(content=user_q)]

    # 2. Invoke the LLM with the SAFE list
    response = llm_with_tools.invoke(messages_to_send)
    
    # 3. Manually append to the REAL history for the ToolNode to use
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
    # 1. Grab data for evaluation
    user_q = state["user_message"]
    tool_out = state["tool_result"] if state.get("tool_result") else "No tool output available."

    # 2. Build the internal evaluation prompt
    eval_messages = [
    SystemMessage(content="""You are a pragmatic quality checker. 
    Your ONLY goal is to verify if the Tool Search Result contains actual menu items.
    - If the tool returned specific dishes, prices, or a 'not found' confirmation, mark satisfied: true.
    - Only mark satisfied: false if the tool returned an error, an empty list, or completely irrelevant data."""),
    HumanMessage(content=f"User Question: {user_q}\nTool Result: {tool_out}")
    ]
    # 3. Use the LLM to decide
    decision = llm.with_structured_output(ReflectionDecision).invoke(eval_messages)

    # 4. Update the control flags manually
    state["reflection_satisfied"] = decision.satisfied
    state["iteration_count"] = state.get("iteration_count", 0) + 1

    # 5. If NOT satisfied, manually append the feedback to the message list
    if not decision.satisfied:
        # We add the nudge as a HumanMessage. 
        # This is safe because state["messages"] currently ends with the ToolMessage.
        feedback_text = getattr(decision, 'feedback', "The previous result wasn't sufficient.")
        
        nudge_message = HumanMessage(
            content=f"Reflection Feedback: {feedback_text}. Please try again to answer: {user_q}"
        )
        
        # Manually mutating the list
        state["messages"].append(nudge_message)

    return state

def personalization_node(state: MainState):
    # Instead of passing state["messages"] directly, which might be malformed,
    # we create a clean context for the final response.
    user_q = state.get("user_message", "")
    tool_data = state.get("tool_result", "No items found.")
    
    # Construct a clean prompt that doesn't trigger the Role Order check
    prompt = [
        SystemMessage(content="You are a helpful restaurant assistant. Use the provided menu data to answer the customer."),
        HumanMessage(content=f"Question: {user_q}\n\nMenu Data Found: {tool_data}")
    ]

    # Now invoke the LLM with the clean list
    response = llm.invoke(prompt)
    
    # Update state with the final answer
    state["response"] = response.content
    return state


def reflection_router(state: MainState):
    if state["reflection_satisfied"]:
        return "personalization"

    if state["iteration_count"] >= state["max_iterations"]:
        return "personalization"

    return "tool_decision"
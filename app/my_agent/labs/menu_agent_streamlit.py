import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import streamlit as st
from app.my_agent.agents.menu_agent import build_menu_graph
from langchain_core.messages import HumanMessage, AIMessage
from app.core.database import SessionLocal

st.set_page_config(page_title="Menu Assistant", page_icon="🍴")
st.title("🍴 Restaurant Menu Assistant")

# 1. Initialize Graph once
@st.cache_resource
def init_agent():
    db = SessionLocal() 
    return build_menu_graph(db)

graph = init_agent()

# 2. Initialize Session States
if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "user_unique_session_001"

# 3. Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 4. User Input
if prompt := st.chat_input("Ask me about the menu..."):
    # Convert UI history (dicts) into LangChain objects for the graph
    # This is the "Memory Bridge"
    history_objects = []
    for m in st.session_state.messages:
        if m["role"] == "user":
            history_objects.append(HumanMessage(content=m["content"]))
        else:
            history_objects.append(AIMessage(content=m["content"]))

    # Add the current prompt as the latest HumanMessage
    current_human_message = HumanMessage(content=prompt)
    history_objects.append(current_human_message)

    # UI Update (Visual only)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 5. Run the Agent
    with st.chat_message("assistant"):
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        
        initial_input = {
            "messages": history_objects, # Now the graph starts with the full history
            "user_message": prompt,
            "iteration_count": 0,
            "max_iterations": 3
        }
        
        # Invoke the graph
        final_state = graph.invoke(initial_input, config=config)
        response = final_state.get("response", "I'm sorry, I couldn't process that.")
        
        st.markdown(response)
        # System Trace
        with st.expander("System Trace"):
            iters = final_state.get('iteration_count', 0)
            st.write(f"Thread ID: {st.session_state.thread_id}")
            st.write(f"Total Iterations this turn: {iters}")
            st.write(f"Reflection Satisfied: {final_state.get('reflection_satisfied', 'N/A')}")
        # Add this inside your assistant chat block to see the history
        with st.expander("Full Message History"):
            # This retrieves the state directly from the checkpointer
            current_state = graph.get_state(config)
            st.write(current_state.values.get("messages", []))

    # Save to history
    st.session_state.messages.append({"role": "assistant", "content": response})
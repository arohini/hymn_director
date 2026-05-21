# app.py
import streamlit as st
import json
from agent_kaumaran_streaming import SpiritualEngine

st.set_page_config(page_title="Sai Spiritual Guide", layout="centered")
st.title("Sai Talks")


# 1. Instantiate engine via resource cache (Runs once across sessions)
@st.cache_resource
def get_engine():
    return SpiritualEngine()

engine = get_engine()

    
if "thread_id" not in st.session_state:
    st.session_state.thread_id = "sp_user_001"

# ==========================================
# 3. GREETING POPUP
# ==========================================

if 'greeted' not in st.session_state:
    st.balloons()
    st.success("✨ Welcome to the Sai Talks! \n \n"
               "You can ask for guidance regarding any situation. \n \n"
               "As it is belief-based, it is recommended not to follow the \n"
               "recommendations for any result but for the inner transformation. \n \n"
               "Keep your intentions and faith pure !!")
    st.session_state.greeted = True
    
# 2. Synchronize past chat loops seamlessly 
history = engine.get_history(st.session_state.thread_id)
for msg in history:
    role = "user" if msg.type == "human" else "assistant"
    with st.chat_message(role):
        if role == "user":
            st.markdown(msg.content)
        else:
            # Render your structural JSON keys exactly as before
            try:
                response_dict = json.loads(msg.content)
                for key, value in response_dict.items():
                    display_key = key.replace("_", " ").capitalize()
                    
                    if isinstance(value, dict):
                        st.markdown(f"### {display_key}")
                        for sub_key, sub_value in value.items():
                            if str(sub_value).strip():
                                st.markdown(f"**{sub_key.replace('_', ' ').capitalize()}:** {sub_value}")

                    else:
                        if str(value).strip():
                            st.markdown(f"**{display_key}:** {value}")

            except Exception:
                # Fallback rendering if it's raw text
                st.markdown(msg.content)



# ==========================================
# 4. REACTIVE CHAT EXECUTION LOOP
# ==========================================

if prompt := st.chat_input("How do you feel now?"):
    
    # 1. Render User query instantly
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 2. Set up placeholders for our LangGraph stream
    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        response_placeholder = st.empty()
        
        # Open an initial loading status element
        with status_placeholder.status("Connecting to system pipeline...") as status:
            
            # 3. Iterate through graph updates as they run live on your machine
            for update in engine.stream_chat(st.session_state.thread_id, prompt):
                
                if "search" in update:
                    status.update(label="Retrieving...", state="running")
                
                if "guide" in update:
                    status.update(label="✨ Processing guidance text structure...", state="running")
                    
                    # Clear loading widgets before parsing JSON elements
                    status_placeholder.empty()
                    
                    # Extract the structured payload returned by the guidance node
                    structured_output = update["guide"].get("structured_guidance", {})
                    
                    # 4. Streamlit displays the parsed response layout blocks
                    with response_placeholder.container():
                        for key, value in structured_output.items():
                            display_key = key.replace("_", " ").capitalize()
                            
                            if isinstance(value, dict):
                                st.markdown(f"### {display_key}")
                                for sub_key, sub_value in value.items():
                                    if str(sub_value).strip():
                                        st.markdown(f"**{sub_key.replace('_', ' ').capitalize()}:** {sub_value}")
                            else:
                                if str(value).strip():
                                    st.markdown(f"**{display_key}:** {value}")
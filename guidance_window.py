import streamlit as st
from src.components.divine_agents.agent_kaumaran import main
st.title("Sai Talks")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# Check if the user has been greeted yet
if 'greeted' not in st.session_state:
    st.balloons() # Optional visual flair
    st.success("✨ Welcome to the Sai Talks! \n \
        You can ask for guidance regarding any situation. \n \
        As it is belief based it is recommended not to follow the \n \
        recommendations for any result but for the inner transformation. \n \
        Keep you intentions and faith pure !!")
    st.session_state.greeted = True


# React to user input
if prompt := st.chat_input("How do you feel now?"):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    sai_guidance = main(prompt)
    response = sai_guidance
    
    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        for key, value in response.items():
            # Clean up the key for better display (replace underscores with spaces)
            display_key = key.replace("_", " ").capitalize()
            
            # Check if the value is a dictionary (like Qualities or repetition_counts)
            if isinstance(value, dict):
                st.markdown(f"### {display_key}")
                for sub_key, sub_value in value.items():
                    if sub_value.strip(): # Only show if there's content
                        st.markdown(f"**{sub_key.replace('_', ' ').capitalize()}:** {sub_value.strip()}")
            else:
                # Display regular key-value pairs
                if value.strip(): # Only show if there's content
                    st.markdown(f"**{display_key}:** {value.strip()}")
        # st.markdown(response)
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})
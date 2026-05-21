import ollama
from pymongo import MongoClient
from load_dotenv import load_dotenv
import os, json
import voyageai
from kaumaran_sp import system_prompt, story_system_promt, default_response
from models.kaumran_model import Muruganmantra
from langchain.tools import tool
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.mongodb import MongoDBSaver
from typing import Literal, Annotated, TypedDict, Optional
from langsmith import traceable
from langgraph.graph.message import add_messages
from langgraph.types import RetryPolicy
from langchain_core.messages import SystemMessage, HumanMessage, convert_to_openai_messages

load_dotenv()  # Load environment variables from .env file


# Initialize MongoDB
client = MongoClient(os.getenv("atlas_mongodb_uri"))
db = client['spiritual_hymns']
collection = db['lord_muruga']

# This creates collections for 'checkpoints' and 'writes' automatically
checkpointer = MongoDBSaver(client, db_name="agent_memory")

class MantraState(TypedDict):
    # This stores the chat history (Role/Content)
    messages: Annotated[list, add_messages]
    # This stores the metadata for the specific verse found
    verse_metadata: Optional[dict]
    # This stores the final structured JSON from Ollama
    final_output: Optional[dict]
    # Retrieved response from Mongodb Atlas
    suggested_hymn: Optional[dict]
    

@traceable
def call_spiritual_guide(state: MantraState):
    # 1. Search for the most relevant verse in your JSONL data
    # This uses a simple text search on your 'meaning' and 'sentiment' fields
    # query = { "$text": { "$search": user_input } }
    # verse_data = collection.find_one(query)
    
    # user_message = state["messages"][-1].content
    verse_data = state.get("verse_metadata", {})
    chat_history = convert_to_openai_messages(state["messages"])

    # 2. Construct the context from your JSONL fields
    context = f"""
    verse: {verse_data.get('vel_verse','')}
    meaning: {verse_data.get('literal_meaning','')}
    story: {verse_data.get('story','')}
    possible_experience: {verse_data.get('possible_experience','')}
    chanting_guide: {verse_data.get('chanting_time','')}
    repetitions: {verse_data.get('repetition_counts','')}
    qualities: {verse_data.get('Qualities','')}
    audio_link : {verse_data.get('audio_link','')}
    """ if verse_data else "Provide a general spiritual encouragement."
        
    system_message = {
        'role': 'system', 
        'content': f"{system_prompt}\nContext: {context}"
    }
    
    # 3. Combine them simply using list addition
    chat_messages = [system_message] + chat_history
    try:
        # 3. Prompt the local Ollama model
        response = ollama.chat(model='vel-maaral-s1-v4:latest', 
                            messages=chat_messages,
            options={
            'temperature': 0.1,       # Makes it less "robotic"
            'repeat_penalty': 1.2,    # Stops it from saying "I am an AI" repeatedly
            'top_k': 40,              # Limits word pool to keep it coherent
            'top_p': 0.9,
            'num_ctx': 4096# Ensures diverse vocabulary
        },format= Muruganmantra.model_json_schema())
    except Exception as e:
        print(f"Error getting response from LLM")
        
    try:
        # vel_guidance = Velmantra.model_validate_json(response.message.content)    
        content = response['message']['content']
        structured_response = json.loads(content)
        return {
            "messages": [{"role": "assistant", "content": content}],
            "final_output": structured_response
        }
    except Exception as e:
        print(f"Error loading llm response to json {str(e)}")
        # to do: add a generic response
        return {"messages": [{"role": "assistant", "content": "I apologize, but I am unable to process that right now."}]}


@traceable
def get_content_for_llm(state: MantraState):
    
    atlas_result = []
    # 1. Embed user input via Voyage
    try:
        user_message = state["messages"][-1].content
        vo = voyageai.Client(api_key=os.getenv('voyage_api_key'))
        user_vector = vo.multimodal_embed(
        inputs=[[user_message]],
        model="voyage-multimodal-3",
        input_type="query"     # CRITICAL
        )
        user_input_vector= user_vector.embeddings[0]
    except Exception as e:
        print(f"Error embedd vectoring the user input {str(e)}")
        
    
    # 2. Vector Search in MongoDB
    pipeline = [
        {
            "$vectorSearch": {
                "index": "input_f_embeddings_index",
                "path": "input-f-embeddings",
                "queryVector": user_input_vector,
                "numCandidates": 10,
                "limit": 1
            }
        }
    ]
    
    try:
        atlas_result = list(collection.aggregate(pipeline))[0]
        atlas_result.pop("_id", None)
        return {"suggested_hymn": atlas_result}
    except Exception as e:
        print(f"Error getting result from atlas {str(e)}")
        return {"verse_metadata": atlas_result}
    
    # 3. Pass to Ollama (Sarvam-1) with the strict template
    return call_spiritual_guide(atlas_result, user_message)

@traceable
def build_story_with_llm(state: MantraState) -> str:
    try:
        response = ollama.chat(model='llama3.2:3b', messages=[
            {'role': 'system', 'content': story_system_promt}
        ],
            options={
            'temperature': 0.1,       # Makes it less "robotic"
            'repeat_penalty': 1.2,    # Stops it from saying "I am an AI" repeatedly
            'top_k': 40,              # Limits word pool to keep it coherent
            'top_p': 0.9              # Ensures diverse vocabulary
        })
        
        structured_response = response['message']['content']
        return {
                "messages": [{"role": "assistant", "content": structured_response}],
                "final_output": structured_response
            }
    except Exception as e:
        print(f"Error builfing story using LLM {str(e)}")
        return {"messages": [{"role": "assistant", "content":"Dear, Always stay \
            calm, be patient, have faith and do things consistently and surrender \
                to god."}]}

def should_continue(state: MantraState) -> Literal['hymn', 'general']:
    if 1:
        return "hymn"
    else:
        return "general"


workflow = StateGraph(MantraState)

ollama_retry_policy = RetryPolicy(
    max_attempts=3,          # Initial attempt + 2 retries
    initial_interval=1.0,    # Wait 1 second before the first retry
    backoff_factor=2.0,      # Double the wait time each retry (1s -> 2s)
    jitter=True              # Add randomness to prevent timing synchronization issues
)

# Add nodes
workflow.add_node("generate_hymn_response", get_content_for_llm)
workflow.add_node("process_hymn_response", call_spiritual_guide, 
                  retry_policy=ollama_retry_policy)


workflow.add_edge(START, "generate_hymn_response")
workflow.add_edge("generate_hymn_response", "process_hymn_response")
workflow.add_edge("process_hymn_response", END)

# Compile the graph
app = workflow.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "sp_user_001"}}

user_query = {
    "messages": [
        SystemMessage(content = system_prompt),
        HumanMessage(content = "I need strength for my new project.")
    ]
    }

# This single call triggers: Vector Search -> Ollama -> Save to MongoDB -> LangSmith Trace
final_state = app.invoke(user_query, config)

print(final_state["final_output"])


import ollama
from pymongo import MongoClient
from load_dotenv import load_dotenv
import os, json
import voyageai
from .kaumaran_sp import system_prompt, story_system_promt, default_response
from ..models.kaumran_model import *
from langchain.tools import tool
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.checkpoint.mongodb import MongoDBSaver
from typing import Literal, Annotated, TypedDict
from langsmith import traceable
from langgraph.graph.message import add_messages

load_dotenv()  # Load environment variables from .env file


# Initialize MongoDB
client = MongoClient(os.getenv("atlas_mongodb_uri"))
db = client['spiritual_hymns']
collection = db['lord_muruga']

# This creates collections for 'checkpoints' and 'writes' automatically
checkpointer = MongoDBSaver(client, db_name="agent_memory")

class AgentState(TypedDict):
    # This keeps the conversation history
    messages: Annotated[list, add_messages]
    # This stores the latest structured data from your Velmantra schema
    structured_data: dict
    
@tool
def search(query: str):
    """Call to surf the web."""
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."

@traceable
def get_verse_and_chat(verse_data: dict, user_input) -> None:
    # 1. Search for the most relevant verse in your JSONL data
    # This uses a simple text search on your 'meaning' and 'sentiment' fields
    # query = { "$text": { "$search": user_input } }
    # verse_data = collection.find_one(query)
    
    if not verse_data and not isinstance(verse_data, dict):
        # Fallback if no specific verse matches
        context = "Provide a general spiritual encouragement."
    else:
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
        """
    
    # 3. Prompt the local Ollama model
    response = ollama.chat(model='vel-maaral-s1-v4:latest', messages=[
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': f"Context: {context}\n\nUser Question: {user_input}"}
    ],
        options={
        'temperature': 0.1,       # Makes it less "robotic"
        'repeat_penalty': 1.2,    # Stops it from saying "I am an AI" repeatedly
        'top_k': 40,              # Limits word pool to keep it coherent
        'top_p': 0.9,
        'num_ctx': 4096# Ensures diverse vocabulary
    },format= Velmantra.model_json_schema())
    
    # ,format= Velmantra.model_json_schema()
    
    try:
        vel_guidance = Velmantra.model_validate_json(response.message.content)    
        response = json.loads(response['message']['content'])
    except Exception as e:
        print(f"Error loading llm response to json {str(e)}")
        # to do: add a generic response
        return default_response

    return response
    # print(response['message']['content'])

@traceable
def get_content_for_llm(user_input):
    # 1. Embed user input via Voyage
    try:
        
        vo = voyageai.Client(api_key=os.getenv('voyage_api_key'))
        user_vector = vo.multimodal_embed(
        inputs=[[user_input]],
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
    
    atlas_result = list(collection.aggregate(pipeline))[0]
    
    # 3. Pass to Ollama (Sarvam-1) with the strict template
    return get_verse_and_chat(atlas_result, user_input)

# print(get_content_for_llm(user_input=user_input))

@traceable
def build_story_with_llm(hymn_context: json) -> str:
    try:
        response = ollama.chat(model='llama3.2:3b', messages=[
            {'role': 'system', 'content': story_system_promt},
            {'role': 'user', 'content': f"Context: {hymn_context}"}
        ],
            options={
            'temperature': 0.1,       # Makes it less "robotic"
            'repeat_penalty': 1.2,    # Stops it from saying "I am an AI" repeatedly
            'top_k': 40,              # Limits word pool to keep it coherent
            'top_p': 0.9              # Ensures diverse vocabulary
        })
        
        return response['message']['content']
    except Exception as e:
        print(f"Error builfing story using LLM {str(e)}")
        return "Dear, Always stay calm, be patient, have faith and do things consistently and surrender to god."

tools = [search]
tool_node = ToolNode(tools)

def main(user_input:str) -> str:
    # user_input = "All my coworkers are causing trouble to me, always a tough situation at office, how to handle this ?"
    hymn_json_response = get_content_for_llm(user_input=user_input)
    # final_response = build_story_with_llm(hymn_json_response)
    return hymn_json_response

def call_model(state: MessagesState):
    # Your logic here
    return {"messages": [{"role": "assistant", "content": "The path is clear."}]}

# backend.py
import json, os
import ollama
from typing import Annotated, TypedDict, Optional, Generator, Literal
from pymongo import MongoClient
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.mongodb import MongoDBSaver
from models.kaumran_model import Muruganmantra
from langchain_core.messages import convert_to_openai_messages, SystemMessage, HumanMessage
from kaumaran_sp import system_prompt, story_system_promt, default_response
from load_dotenv import load_dotenv
from langsmith import traceable
import voyageai

load_dotenv()

class SpiritualState(TypedDict):
    messages: Annotated[list, add_messages]
    current_verse: Optional[dict]
    structured_guidance: Optional[dict]
    route: str

class SpiritualEngine:
    def __init__(self, db_uri: str = os.getenv("atlas_mongodb_uri"), cp_db_name: str = "agent_memory"):
        # Setup persistent connection pools
        self.client = MongoClient(db_uri)
        self.checkpointer = MongoDBSaver(self.client, db_name=cp_db_name)
        self.graph = self._build_graph()
        self.hymns_db = self.client['spiritual_hymns']
        self.hymns_collection = self.hymns_db['lord_muruga']
    
    @traceable
    def _model_router(self, state: SpiritualState) -> Literal['situation', 'general']:
        # Step 1: Define the classification rules
        # classifier_prompt = (
        #     "Classify the text into exactly one word: 'GENERAL' or 'SITUATION'.\n"
        #     "GENERAL = broad opinions, facts, casual small talk.\n"
        #     "SITUATION = specific personal events, problems, unique contexts.\n"
        #     f"Text: '{state["messages"][-1].content}'\n"
        #     "Classification:"
        # )
        
        classifier_prompt = (f"""
        You are an expert text classification AI. Your task is to classify an input sentence into one of two categories: "Situation" or "General".

        ### Definitions:
        1. Situation: The sentence describes a specific, time-bound event, personal experience, immediate context, or localized occurrence. It often uses specific pronouns (I, we, they), past/present progressive tenses, or references a particular moment.
        2. General: The sentence describes a universal truth, timeless fact, broad habit, general preference, law of nature, or abstract concept. It is not tied to a specific moment or a single ongoing event.

        ### Instructions:
        - Analyze the input sentence carefully.
        - Output ONLY a JSON object with two keys: "category" (either "Situation" or "General") and "reasoning" (a short, one-sentence explanation).
        - Do not include any conversational filler, markdown formatting (outside the code block), or extra text.

        ### Examples:
        Input: "I am stuck in heavy traffic on my way to the office right now."
        Output: {"category": "Situation", "reasoning": "Describes a specific, ongoing personal event happening in the present moment."}

        Input: "Traffic congestion usually increases during rush hour in major cities."
        Output: {"category": "General", "reasoning": "States a broad, recurring fact rather than a specific event."}

        Input: "Water boils at 100 degrees Celsius."
        Output: {"category": "General", "reasoning": "States a universal scientific fact."}

        Input: "The kitchen pipe burst and water is leaking everywhere."
        Output: {"category": "Situation", "reasoning": "Refers to a localized, immediate incident requiring attention."}

        ### Input Sentence:
        "{state["messages"][-1].content}"

        ### Output:

        """)
        
        # Step 2: Run the quick classification pass
        try:
            class_res = ollama.generate(
                model='llama3.2:3b',  # Using Llama 3.2 to classify
                prompt=classifier_prompt,
                options={'temperature': 0.0}  # 0.0 ensures maximum token consistency
            )
            category = class_res['response'].strip().upper()
        except Exception as e:
            return f"Routing Error: {e}"

        # Step 3: Choose the model based on the classification result
        # We check if 'SITUATION' is in the response to account for stray punctuation
        if "SITUATION" in category:
            chosen_model = 'llama3.2:3b'  # Use a smarter model for complex situations
            return  {
                "route": "situation"            }
        else:
            chosen_model = 'phi4:mini'     # Use a faster, lighter model for general talk
            return {
            "route": "general"
        }

    @traceable
    def _route_after_model(self, state):
        return state["route"]
    
    @traceable
    def _general_talk_node(self, state: SpiritualState):
        try:
            {'role': 'system', 'content': story_system_promt}
            genral_talk_prompt = "The user is engaging in general talk. \
            Keep your response casual, conversational, and brief."
            
            user_message = state["messages"][-1].content
            system_message = {
            'role': 'system', 
            'content': f"{genral_talk_prompt}\nContext: {user_message}"}
        
            chat_history = convert_to_openai_messages(state["messages"])
            
            # 3. Combine them simply using list addition
            chat_messages = [system_message] + chat_history
            try:
                # 3. Prompt the local Ollama model
                response = ollama.chat(model='llama3.2:3b', 
                                    messages=chat_messages,
                    options={
                    'temperature': 0.2,       # Makes it less "robotic"
                    'repeat_penalty': 1.2,    # Stops it from saying "I am an AI" repeatedly
                    'top_k': 40,              # Limits word pool to keep it coherent
                    'top_p': 0.9,
                    'num_ctx': 4096# Ensures diverse vocabulary
                })
            except Exception as e:
                print(f"Error getting response from LLM {e}")
                
            try:
                # vel_guidance = Velmantra.model_validate_json(response.message.content)    
                content = response['message']['content']
                # structured_response = json.loads(content)
                return {
                    "messages": [{"role": "assistant", "content": content}],
                }
            except Exception as e:
                print(f"Error getting llm response {str(e)}")
                # to do: add a generic response
                return {"messages": [{"role": "assistant", "content": "I apologize, but I am unable to process that right now."}]}  

        except Exception as e:
            print(f"Error getting general response {e}")
            
    @traceable
    def _search_node(self, state: SpiritualState):
        # Clean up your pipeline result safely (no ObjectId serialization issues)

        atlas_result = {}
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
            atlas_result = list(self.hymns_collection.aggregate(pipeline))[0]
            atlas_result.pop("_id", None)
            return {"current_verse": atlas_result}
        except Exception as e:
            print(f"Error getting result from atlas {str(e)}")
            return {"current_verse": atlas_result}

    @traceable
    def _guidance_node(self, state: SpiritualState):
        # user_message = state["messages"][-1].content
        verse_data = state.get("current_verse", {})
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
                "structured_guidance": structured_response
            }
        except Exception as e:
            print(f"Error loading llm response to json {str(e)}")
            # to do: add a generic response
            return {"messages": [{"role": "assistant", "content": "I apologize, but I am unable to process that right now."}]}

    @traceable
    def _build_graph(self):
        workflow = StateGraph(SpiritualState)
        workflow.add_node("choose_model", self._model_router)
        workflow.add_node("search", self._search_node)
        workflow.add_node("general_talk", self._general_talk_node)
        workflow.add_node("guide", self._guidance_node)
        # workflow.add_edge(START, "choose_model")
        workflow.set_entry_point("choose_model")
        workflow.add_conditional_edges(
            "choose_model",
            self._route_after_model,
            {
                "situation": "search",
                "general": "general_talk"
            }
        )
        workflow.add_edge("general_talk", END)
        workflow.add_edge("search", "guide")
        workflow.add_edge("guide", END)
        return workflow.compile(checkpointer=self.checkpointer)

    @traceable
    def get_history(self, thread_id: str) -> list:
        """Helper to get a clean history for the UI without leaky abstractions."""
        state = self.graph.get_state({"configurable": {"thread_id": thread_id}})
        return state.values.get("messages", [])

    @traceable
    def stream_chat(self, thread_id: str, text_input: str) -> Generator[dict, None, None]:
        """Streams back active node status to keep UI completely reactive."""
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {"messages": [SystemMessage(content = system_prompt),HumanMessage(content=text_input)]}
        
        # Yielding updates step-by-step as they execute across nodes
        for event in self.graph.stream(inputs, config, stream_mode="updates"):
            yield event
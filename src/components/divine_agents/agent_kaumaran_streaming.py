# backend.py
import json, os
import ollama
from typing import Annotated, TypedDict, Optional, Generator, Literal
from pymongo import MongoClient
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.mongodb import MongoDBSaver
from langchain_core.tools import tool
from langchain_core.messages import AIMessage
from models.kaumran_model import Muruganmantra
from langchain_core.messages import convert_to_openai_messages, SystemMessage, HumanMessage
from kaumaran_sp import system_prompt, story_system_promt, default_response
from langgraph.prebuilt import ToolNode, tools_condition
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
    
    @tool
    def search_temple(self, hymn_name: str) -> str:
        """
        Searches and identifies the historical temple associated with a given spiritual hymn.

        Args:
            hymn_name (str): The name or line of the hymn suggested.
        """
        # LangGraph's ToolNode executes this function automatically when Ollama requests it
        # You can access external databases here using the hymn_name parameter
        return "Kumarakottam Subramanya Swamy Temple, Kanchipuram"
    
    
    
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
        
        user_sentence = state["messages"][-1].content
        classifier_prompt = (f"""You are an expert text classification AI. Your task is to classify the user's message into one category:

            - casual_chat
            - spiritual_guidance
            
        ### Definitions:
        
        1. spiritual_guidance: This category applies if the text focuses on transcendent concepts, connection to a higher power, soul/spirit growth, ancient scriptures, cosmic consciousness, mindfulness as a path to enlightenment, or deeply philosophical/existential concepts about the nature of reality beyond material existence.
        2. casual_chat: This category applies if the text focuses on standard self-help, practical life advice, psychological well-being, or everyday wisdom. **Crucially, this also includes all standard conversational text, casual greetings, small talk, and introductory questions (e.g., "Hi," "How are you?", "Tell me about yourself," "What's up?").
        
        ### Instructions:
        - Analyze the input sentence carefully.

        ### Examples:
        Input: "I am stuck in heavy traffic on my way to the office right now."
        Output: "spiritual_guidance"
        
        Input: "I feel low whenever I think of the future"
        Output: "spiritual_guidance"

        Input: "Traffic congestion usually increases during rush hour in major cities."
        Output: "casual_chat"

        Input: "Water boils at 100 degrees Celsius."
        Output: "casual_chat"
        
        Input: "Hi there! How are you doing today? I've been meaning to check in and ask if you could tell me a bit more about yourself and your background."
        Output: "casual_chat"
        
        Input: "Tell me about yourself"
        Output: "casual_chat"
        
        Input: "The kitchen pipe burst and water is leaking everywhere."
        Output: "casual_chat"
        
        ### Input Sentence:
        "{user_sentence}"

        Return only the category name.
        """
        )
        
        # Step 2: Run the quick classification pass
        try:
            class_res = ollama.generate(
                model='llama3.2:3b',  # Using Llama 3.2 to classify
                prompt=classifier_prompt,
                options={'temperature': 0.0}  # 0.0 ensures maximum token consistency
            )
            category = class_res['response'].strip().upper()
            print(f"Classification result: {category}")
        except Exception as e:
            return f"Routing Error: {e}"

        # Step 3: Choose the model based on the classification result
        # We check if 'SITUATION' is in the response to account for stray punctuation
        if "casual_chat".upper() in category:
            return {"route": "general"}
        else:
            return {"route": "situation"}

    @traceable
    def _route_after_model(self, state):
        return state["route"]
    
    @traceable
    def _general_talk_node(self, state: SpiritualState):
        try:
            # {'role': 'system', 'content': story_system_promt}
            
            general_talk_prompt = (
            "CRITICAL: Do NOT use JSON format, do NOT use brackets {}, do NOT use key value pairs"
            "You are a warm, compassionate spiritual guide inspired by Lord Muruga. "
            "The user is engaging in casual conversation, greetings, or small talk. "
            "Respond naturally, directly, and kindly in plain text. "
            "Do NOT use JSON, do NOT output structured schemas, and do NOT reply with code labels."
            "Never open your response with a curly brace '{'. Speak directly to the human as a person."
            )

            
            user_message = state["messages"][-1].content
            
            #removing user message about the general talk prompt to avoid confusion in the model
            g_system_message = {
            'role': 'system', 
            'content': general_talk_prompt
            }
            
            g_system_message_v1 = {
            'role': 'system', 
            'content': f"{general_talk_prompt}\nContext: {user_message}"
            }
            
            clean_history = []
            for msg in state["messages"][-6:]:
                # Skip any past assistant messages that look like JSON structure
                if msg.type == "assistant" and ("{" in msg.content or "verse" in msg.content):
                    continue
                clean_history.append(msg)
                
            chat_history = convert_to_openai_messages(clean_history)  # Convert to OpenAI format for consistency with prompts
            
            # 3. Combine them simply using list addition
            chat_messages = [g_system_message] + chat_history
            try:
                # 3. Prompt the local Ollama model
                response = ollama.chat(model='llama3.2:3b', 
                                    messages=chat_messages,
                    options={
                    'temperature': 0.8,       # Makes it less "robotic"
                    'repeat_penalty': 1.2,    # Stops it from saying "I am an AI" repeatedly
                    'top_k': 40,              # Limits word pool to keep it coherent
                    'top_p': 0.9,
                    'num_ctx': 2048, # Ensures diverse vocabulary
                    'num_predict': 150
                })
                
                # vel_guidance = Velmantra.model_validate_json(response.message.content)    
                content = response['message']['content']
                # structured_response = json.loads(content)
                
                # Clean up hack: If the model STILL managed to output JSON despite everything,
                # fallback to a clean, safe conversational string so your user interface doesn't break.
                if content.startswith("{") or '"verse"' in content:
                    print("⚠️ System caught a JSON leak in casual chat node! Triggering hard fallback.")
                    content = "I hear you completely. Let us take a breath and speak simply, heart to heart. What is on your mind today?"

                print("*"*20)
                print("General Talk Response:", content)
                print("*"*20)
                
                
                # Return an AIMessage and explicitly clear out structured elements
                return {
                    "messages": [AIMessage(content=content)],
                    "structured_guidance": None  # Wipes any structural leaking left over in graph state
                }
                
                
            except Exception as e:
                print(f"General Talk Node: Error getting response from LLM {e}")
                return { 
                        "messages": [AIMessage(content="I am here with you. Let us speak simply and peacefully.")],
                        "structured_guidance": None
                        }
                
        except Exception as e:
            print(f"General Talk Node: Error getting general response final try excep {e}")
            return {
            "messages": [AIMessage(content="Peace be with you. How can I assist your journey today?")],
            "structured_guidance": None
            }
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
        chat_history = convert_to_openai_messages(state["messages"][-20:])

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
                                tools=[self.search_temple],
                options={
                'temperature': 0.1,       # Makes it less "robotic"
                'repeat_penalty': 1.2,    # Stops it from saying "I am an AI" repeatedly
                'top_k': 40,              # Limits word pool to keep it coherent
                'top_p': 0.9,
                'num_ctx': 4096# Ensures diverse vocabulary
            },format= Muruganmantra.model_json_schema())
        except Exception as e:
            print(f"Error getting response from guidance vel-maaral-s1-v4:latest LLM model {e}")
            
        try:
            
            # FIX 3: Dynamic Hand-off to LangGraph's tools_condition
            # Ollama returns tool calls in 'tool_calls' inside the message dictionary if it triggers one
            message_obj = response.get('message', {})
            tool_calls = message_obj.get('tool_calls', [])
            content = message_obj.get('content', '')

            # Create a true LangChain/LangGraph compatible message state update
            ai_message = AIMessage(
                content=content,
                tool_calls=tool_calls
            )
            # vel_guidance = Velmantra.model_validate_json(response.message.content)    
            
            # Process structured guidance ONLY if the model didn't decide to call a tool instead
            structured_response = None
            if not tool_calls and content:
                try:
                    structured_response = json.loads(content)
                    print("Structured guidance parsed successfully:", structured_response)
                except Exception as e:
                    print(f"Error loading llm response to json: {str(e)}")

            return {
                "messages": [ai_message],  # LangGraph tools_condition inspects this exact object for tool_calls!
                "structured_guidance": structured_response
            }
    
            # content = response['message']['content']
            # structured_response = json.loads(content)
            # return {
            #     "messages": [{"role": "assistant", "content": content}],
            #     "structured_guidance": structured_response
            # }
        except Exception as e:
            print(f"Error loading llm response to json {str(e)}")
            # to do: add a generic response
            return {"messages": [{"role": "assistant", "content": f"IIIII apologize, but I am unable to process that right now."}]}

    @traceable
    def _build_graph(self):
        
        self.tools = [self.search_temple]
        self.tool_node = ToolNode(self.tools)
        
        workflow = StateGraph(SpiritualState)
        workflow.add_node("choose_model", self._model_router)
        workflow.add_node("search", self._search_node)
        workflow.add_node("general_talk", self._general_talk_node)
        workflow.add_node("guide", self._guidance_node)
        workflow.add_node("tools", ToolNode(self.tools))
        # workflow.add_node("tools", tool_node)  # Must add the tool execution worker node!
        workflow.add_edge(START, "choose_model")
        # workflow.set_entry_point("search")
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
        # 4. Bind conditional tool logic
        workflow.add_conditional_edges(
            "guide", 
            tools_condition  # Routes to "tools" if LLM requests a tool call, else routes to END
        )
        workflow.add_edge("tools", "guide")
        # workflow.add_edge("guide", END)
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
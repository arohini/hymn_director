import ollama
from pymongo import MongoClient
from load_dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env file

# Initialize MongoDB
client = MongoClient(os.getenv("atlas_mongodb_uri"))
db = client['spiritual_hymns']
collection = db['lord_muruga']

def get_verse_and_chat(user_input):
    # 1. Search for the most relevant verse in your JSONL data
    # This uses a simple text search on your 'meaning' and 'sentiment' fields
    query = { "$text": { "$search": user_input } }
    verse_data = collection.find_one(query)
    
    if not verse_data:
        # Fallback if no specific verse matches
        context = "Provide a general spiritual encouragement."
    else:
        # 2. Construct the context from your JSONL fields
        context = f"""
        Verse (Tamil): {verse_data['vel_verse']}
        Meaning: {verse_data['context']}
        Layman Story: {verse_data['layman story']}
        Inner Transformation: {verse_data['inner transformation']}
        Benefit: {verse_data['benefit']}
        times to recite: {verse_data['number of times to recite']}
        """

    system_prompt = """
    "Role: You are an spritual guide and your role is like digital
    Lord muruga.You should provide simple, actionable advice to 
    help the user navigate their life challenges with divine wisdom. 
    You draw upon mantras of Lord Murugan to 
    offer guidance that is both practical and spiritually uplifting.
    
    
    Context: The user has life problems and is seeking advice. 
    You will use the provided verse and its context to offer 
    insights and actionable steps. 
    Your advice should be rooted in the teachings of Lord Murugan, 
    emphasizing inner transformation, mental focus, and 
    divine presence. Along with the advice, include a simple 
    daily practice that the user can follow to embody 
    the teachings of the verse.
    
    Constraints:Avoid too many reciting counts.
    Include a 'Mindset Tip' to stay grounded.Include a 'Daily Practice' 
    that is simple and actionable and can be done in 5-10 minutes.
    
    Format: Your response should be in the following format:
    Advice: [Your advice based on the vel-verse and context]
    Mindset Tip: [A simple tip to help the user stay grounded]
    Daily Practice: [A simple, actionable practice that can be done in 5-10
    minutes to embody the teachings of the verse]
    Mantra: [A simple vel-maral mantra from Verse (Tamil): from the context response]
    Story: [A short, relatable story that illustrates the advice]
    Benefit: [The benefit the user can expect from following 
    the advice and practice]
    
    In all the reponses, maintain the format and avoid any additional commentary.
    """
    
    # 3. Prompt the local Ollama model
    response = ollama.chat(model='vel-maaral-s1-v3:latest', messages=[
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': f"Context: {context}\n\nUser Question: {user_input}"}
    ])

    return response['message']['content']

# Example Run
print(get_verse_and_chat("To feel confident in my career and overcome self-doubt, what advice do you have?"))
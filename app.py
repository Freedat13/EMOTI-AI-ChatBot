import os
import io
import pandas as pd
from flask import Flask, request, jsonify, render_template
from google import genai
from google.genai import types
import pymongo
from typing import List, Dict
import re
import smtplib
from email.message import EmailMessage
import random
from gtts import gTTS
import uuid 

API_KEY = os.getenv("GEMINI_API_KEY")
app = Flask(__name__)
client = None
chat_sessions = {} 

EMAIL_CONFIG = {
    'SENDER_EMAIL': 'freedathennela@gmail.com',  
    'SENDER_PASSWORD': 'qkwe mahk qkbk taes',    
    'RECEIVER_EMAIL': 'freedathennela@gmail.com',    
    'SMTP_SERVER': 'smtp.gmail.com',
    'SMTP_PORT': 587
}

STRESS_KEYWORDS_EN = ['stressed', 'depressed', 'anxious', 'failing', 'give up', 'hopeless', 'overwhelmed', 'pressure', 'panic', 'not good', 'mentally weak', 'tired', 'burnout']
SEVERE_CRISIS_KEYWORDS_EN = ['suicide', 'die', 'kill myself', 'end it all', 'not worth living']

STRESS_KEYWORDS_HI = ['tension', 'pareshan', 'dukhi', 'haar maan li', 'thak gaya', 'mushkil', 'dikhkat', 'nahi hoga', 'bohot zyada']
SEVERE_CRISIS_KEYWORDS_HI = ['khudkushi', 'mar jaunga', 'jaan de dunga', 'khatam karna']

STRESS_KEYWORDS_ES = ['estresado', 'deprimido', 'ansioso', 'fracaso', 'renunciar', 'sin esperanza', 'abrumado', 'presión', 'pánico', 'no puedo', 'agotado']
SEVERE_CRISIS_KEYWORDS_ES = ['suicidio', 'morir', 'matarme', 'terminar con todo']

# Telugu Keywords (Romanized)
STRESS_KEYWORDS_TE = ['tension', 'badhaga undhi', 'nirasam', 'kastam ga undhi', 'odipoyanu', 'aashalevu', 'baaram', 'pressure', 'bayapadtunna', 'sari ledu', 'mental ga weak', 'alasipoyanu', 'buranout']
SEVERE_CRISIS_KEYWORDS_TE = ['aathmahatya', 'chachipota', 'chanipota', 'chivariki theerchestha', 'bathuku waste']

# Tamil Keywords (Romanized)
STRESS_KEYWORDS_TA = ['tension', 'manasukkulle kashtam', 'kavalai', 'thothutten', 'vitudraven', 'nambikkai illa', 'romba pressure', 'bayama irukku', 'sariya illa', 'manasala weak', 'tired', 'veruppu']
SEVERE_CRISIS_KEYWORDS_TA = ['tharkolai', 'saituven', 'kondukolven', 'mudichiduven', 'vazhve thevai illa']

STRESS_KEYWORDS = STRESS_KEYWORDS_EN + STRESS_KEYWORDS_HI + STRESS_KEYWORDS_ES + STRESS_KEYWORDS_TE + STRESS_KEYWORDS_TA 
SEVERE_CRISIS_KEYWORDS = SEVERE_CRISIS_KEYWORDS_EN + SEVERE_CRISIS_KEYWORDS_HI + SEVERE_CRISIS_KEYWORDS_ES + SEVERE_CRISIS_KEYWORDS_TE + SEVERE_CRISIS_KEYWORDS_TA

RESPONSE_THRESHOLD = 3 

MOTIVATIONAL_MEMES = [
    'Memes/Motivation 1.jpg',
    'Memes/Motivation 2.jpeg',
    'Memes/Motivation 3.jpeg',
    'Memes/Motivational 4.jpeg',
    'Memes/Motivational 5.jpeg',
]
FUNNY_MEMES = [
    'Memes/Funny 1.jpeg',
    'Memes/Funny 2.jpeg',
    'Memes/Funny 3.jpeg',
    'Memes/Funny 4.jpeg',
]

MONGO_URI = os.getenv("MONGO_URI") or "mongodb://localhost:27017/" 
INITIAL_DATA_FILE = "placement_assistance_company_multilingual_emotional_links.csv" 
DEFAULT_SESSION_ID = "default_user" 

mongo_client = None
db = None
chats_collection = None          
placement_collection = None
user_contact_collection = None 


def load_initial_data(session_id: str):
    """Loads the CSV file into MongoDB for a specific session ID."""
    global placement_collection
    if placement_collection is None:
        print("ERROR: Placement collection is not initialized. Cannot load data.")
        return

    try:
        if not os.path.exists(INITIAL_DATA_FILE):
             print(f"WARNING: Initial data file not found at {INITIAL_DATA_FILE}. Skipping data load.")
             return

        df = pd.read_csv(INITIAL_DATA_FILE, encoding='utf-8')
        
        data_records: List[Dict] = df.where(pd.notnull(df), None).to_dict('records')
        for record in data_records:
            record['session_id'] = session_id
        
        placement_collection.delete_many({"session_id": session_id})
        
        if data_records:
            placement_collection.insert_many(data_records)
            print(f"SUCCESS: Loaded {len(data_records)} records from {INITIAL_DATA_FILE} for session {session_id}.")
            
    except Exception as e:
        print(f"ERROR: Failed to load initial data from CSV: {e}")
        
def generate_tts_audio(text: str, session_id: str) -> str:
    """
    Generates an MP3 audio file from the given text using gTTS and saves it 
    to the static/audio folder, returning the relative path (e.g., 'audio/filename.mp3').
    Uses lang='auto' for robust multilingual support.
    """
    try:
        audio_filename = f"response_{session_id}_{uuid.uuid4()}.mp3"
        audio_path = os.path.join('static', 'audio', audio_filename)
        
        tts = gTTS(text=text, lang='auto') 
        
        tts.save(audio_path)
        print(f"DEBUG: Successfully generated TTS audio file: {audio_path}") # Debug print
        
        return f'audio/{audio_filename}'
        
    except Exception as e:
        print(f"ERROR: Failed to generate TTS audio. Check text for non-standard characters. Error: {e}")
        return None

try:
    mongo_client = pymongo.MongoClient(MONGO_URI)
    mongo_client.admin.command('ping')
    db = mongo_client["placelytics_db"] 
    chats_collection = db["chats_history"]  
    placement_collection = db["placement_data"] 
    user_contact_collection = db["user_contacts"] 
    
    load_initial_data(DEFAULT_SESSION_ID) 
    
except Exception as e:
    mongo_client = None
    print(f"MongoDB connection failed: {e}")

try:
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
except Exception as e:
    client = None
    print(f"Gemini client initialization failed: {e}")

def send_alert_email(session_id: str, message: str, user_details: dict):
    sender = EMAIL_CONFIG['SENDER_EMAIL']
    recipient = EMAIL_CONFIG['RECEIVER_EMAIL']
    password = EMAIL_CONFIG['SENDER_PASSWORD'].replace(' ', '')
    name = user_details.get('name', 'N/A')
    contact = user_details.get('email', 'N/A')

    msg = EmailMessage()
    msg['Subject'] = f"🚨 URGENT: Emoti AI Stress Alert for Session {session_id}"
    msg['From'] = sender
    msg['To'] = recipient
    
    body = (
        f"A user in the Emoti AI chat has exhibited severe stress or depression keywords.\n\n"
        f"--- USER DETAILS ---\n"
        f"Session ID: {session_id}\n"
        f"User Name: {name}\n"
        f"Contact Email: {contact}\n\n"
        f"--- LAST MESSAGE TRIGGER ---\n"
        f"Message: {message}\n"
        f"--------------------------\n"
        f"Please contact the user immediately."
    )
    msg.set_content(body)

    try:
        with smtplib.SMTP(EMAIL_CONFIG['SMTP_SERVER'], EMAIL_CONFIG['SMTP_PORT']) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        print(f"Email alert successfully sent for session {session_id}.")
        return True
    except Exception as e:
        print(f"ERROR: Failed to send email alert for session {session_id}: {e}")
        return False

def save_chat_message(session_id: str, role: str, text: str, meme_path: str = None, audio_path: str = None):  # UPDATED
    if chats_collection is not None:
        message_doc = {"role": role, "text": text, "timestamp": pd.Timestamp.now().isoformat()}
        if meme_path:
            message_doc['meme'] = meme_path # Save meme path if one was sent
        if audio_path: # NEW
            message_doc['audio'] = audio_path # Save audio path
            
        chats_collection.update_one(
            {"_id": session_id},
            {"$push": {"history": message_doc}},
            upsert=True
        )

def save_user_details(session_id: str, name: str = None, email: str = None):
    if user_contact_collection is not None:
        update_doc = {}
        if name:
            update_doc['name'] = name
        if email:
            update_doc['email'] = email
            
        if update_doc:
            user_contact_collection.update_one(
                {"_id": session_id},
                {"$set": update_doc},
                upsert=True
            )

def get_user_details(session_id: str) -> dict:
    if user_contact_collection is not None:
        doc = user_contact_collection.find_one({"_id": session_id})
        return doc if doc else {}
    return {}

def get_chat_session(session_id: str):
    global client
    
    if client is None:
        raise Exception("Gemini client is not initialized.")
    
    if session_id not in chat_sessions:
        
        system_instruction = (
            "You are Emoti AI, a helpful, multilingual, and empathetic career assistant. "
            "Your main goal is to provide concise, direct, and actionable advice. "
            "DO NOT use markdown headings (#) or bold formatting (**). "
            "If the user is talking about their feelings or mental state, offer non-judgmental support, "
            "and DO NOT mention placement or career assistance unless they explicitly ask for it. "
            "Respond in the language the user is using."
        )
        config = types.GenerateContentConfig(system_instruction=system_instruction)

        mongo_doc = chats_collection.find_one({"_id": session_id})
        gemini_history: List[types.Content] = []
        
        if mongo_doc and 'history' in mongo_doc:
            for message in mongo_doc['history']:
                text_part = message.get('text', '')
                if text_part and not text_part.startswith("Initial setup:"):
                    gemini_history.append(
                        types.Content(
                            role=message['role'],
                            parts=[types.Part(text=text_part)]
                        )
                    )
        else:
            data_context = "No custom placement data uploaded."
            if placement_collection.find_one({"session_id": DEFAULT_SESSION_ID}):
                 data_context = "A foundational placement dataset is loaded. The columns are: Domain, Difficulty, Resource Type, Query, Answer, Links. Use this for RAG lookups."

            initial_history = [
                types.Content(
                    role="user", 
                    parts=[types.Part(text=f"Initial setup: The user's context is: {data_context}")] 
                ),
                types.Content(
                    role="model", 
                    parts=[types.Part(text="Initialization complete. Ready to assist. Please start by telling me your name and preferred contact email.")] 
                )
            ]
            gemini_history.extend(initial_history)
            
            mongo_doc_to_insert = {
                "_id": session_id,
                "history": [
                    {"role": initial_history[0].role, "text": initial_history[0].parts[0].text, "timestamp": pd.Timestamp.now().isoformat()},
                    {"role": initial_history[1].role, "text": initial_history[1].parts[0].text, "timestamp": pd.Timestamp.now().isoformat()},
                ]
            }
            if chats_collection is not None:
                chats_collection.insert_one(mongo_doc_to_insert)

        chat = client.chats.create(
            model="gemini-2.5-flash",
            config=config,
            history=gemini_history
        )
        chat_sessions[session_id] = chat
    return chat_sessions[session_id]

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_session_list', methods=['GET'])
def get_session_list():
    if chats_collection is None:
        return jsonify({'error': 'MongoDB chats collection failed to initialize.'}), 500

    try:
        session_ids = chats_collection.distinct("_id")
        return jsonify({'sessions': session_ids})
    
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve session list: {e}'}), 500

@app.route('/get_history', methods=['GET'])
def get_history():
    session_id = request.args.get('session_id', 'default_user')
    
    if chats_collection is None:
        return jsonify({'error': 'MongoDB chats collection failed to initialize.'}), 500

    try:
        mongo_doc = chats_collection.find_one({"_id": session_id})
        # The first two messages are the hidden initialization context, so slice from index 2
        history = mongo_doc.get('history', [])[2:] if mongo_doc else []
        
        for message in history:
            if 'audio' in message and message['audio']:
                message['audio_url'] = f'/static/{message["audio"]}'
            else:
                message['audio_url'] = None
            
        return jsonify({'history': history})

    except Exception as e:
        return jsonify({'error': f'Failed to retrieve history: {e}'}), 500

@app.route('/delete_session', methods=['POST'])
def delete_session():
    if mongo_client is None:
        return jsonify({'error': 'MongoDB initialization failed.'}), 500
        
    data = request.get_json()
    session_id = data.get('session_id')

    if not session_id:
        return jsonify({'error': 'No session ID provided for deletion.'}), 400

    try:
        chats_collection.delete_one({"_id": session_id})
        
        if session_id != DEFAULT_SESSION_ID:
            placement_collection.delete_many({"session_id": session_id})
        
        user_contact_collection.delete_one({"_id": session_id})
        
        if session_id in chat_sessions:
            del chat_sessions[session_id]
            
        audio_dir = os.path.join('static', 'audio')
        if os.path.exists(audio_dir):
            for filename in os.listdir(audio_dir):
                if filename.startswith(f'response_{session_id}'):
                    os.remove(os.path.join(audio_dir, filename))
        
        return jsonify({'message': f'Session {session_id} and all associated data deleted successfully.'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to delete session: {e}'}), 500


@app.route('/chat', methods=['POST'])
def chat():
    if client is None or mongo_client is None or placement_collection is None:
        return jsonify({'error': 'Initialization failed.'}), 500
        
    data = request.get_json()
    user_message = data.get('message')
    session_id = data.get('session_id', DEFAULT_SESSION_ID) 

    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        chat_session = get_chat_session(session_id)
        
        user_details = get_user_details(session_id)
        email = user_details.get('email')
        
        email_match = re.search(r'[\w\.-]+@[\w\.-]+(?:\.\w+)+', user_message)
        if email_match:
            save_user_details(session_id, email=email_match.group(0))
            user_details = get_user_details(session_id) 
            email = user_details.get('email')

        user_message_lower = user_message.lower()
        is_stressed = any(keyword in user_message_lower for keyword in STRESS_KEYWORDS)
        is_severe_crisis = any(keyword in user_message_lower for keyword in SEVERE_CRISIS_KEYWORDS)
        
        mongo_doc = chats_collection.find_one({"_id": session_id})
        history_length = len(mongo_doc.get('history', [])) if mongo_doc else 0
        user_message_count = (history_length - 2) // 2

        placement_keywords = ['placement', 'aptitude', 'coding', 'interview', 'dsa', 'algorithm', 'vlsi', 'mechanical', 'civil', 'ai', 'ml', 'course', 'resource', 'study', 'how', 'where', 'link']
        is_placement_query = any(k in user_message_lower for k in placement_keywords)
        
        response_text = ""
        meme_path = None

        if is_stressed:
            
            if email and user_message_count >= RESPONSE_THRESHOLD:
                send_alert_email(session_id, user_message, user_details)
            
            meme_path = random.choice(MOTIVATIONAL_MEMES)
            
            if is_severe_crisis:
                support_prompt = f"The user just said: '{user_message}'. Respond ONLY with direct, urgent, supportive, and non-judgmental de-escalation. Do NOT mention career assistance. Urge them to seek professional help (like 988 or local services)."
            elif is_placement_query:
                  support_prompt = f"The user expressed stress but also asked about placement. Acknowledge their stress, offer a brief, non-committal supportive statement (e.g., 'Take a deep breath'), and then provide a VERY brief, general tip related to their placement query, without using RAG data. Do NOT push for further career talk. User message: {user_message}"
            else:
                support_prompt = f"The user just said: '{user_message}'. Respond with deep empathy, validate their feelings, and offer a general self-care tip (like stepping away or deep breathing). Do NOT talk about placements or career assistance AT ALL."

            support_response = chat_session.send_message(support_prompt)
            response_text = support_response.text 
            
            if not email and not email_match:
                response_text += "\n\nNote: To ensure we can reach out if needed, could you please provide a contact email in your next message?"
            
        else:
            user_message_with_context = user_message
            
            # RAG logic
            if is_placement_query and placement_collection.find_one({"session_id": session_id}):
                
                match = placement_collection.find_one({
                    "session_id": session_id,
                    "$or": [
                        {"Domain": {"$regex": user_message, "$options": "i"}},
                        {"Query": {"$regex": user_message, "$options": "i"}},
                    ]
                })

                if match:
                    retrieved_answer = (
                        f"RETRIEVED DATA:\n"
                        f"Query Match: {match.get('Query', 'N/A')}\n"
                        f"Suggested Action: {match.get('Answer', 'N/A')}\n"
                        f"Relevant Links: {match.get('Links', 'N/A')}\n"
                        f"Instruction: Use this retrieved data directly to formulate your concise response without markdown."
                    )
                    user_message_with_context = f"{user_message}\n\n[CONTEXT]: {retrieved_answer}"
            
            response = chat_session.send_message(user_message_with_context)
            response_text = response.text
        
        # --- TTS GENERATION (NEW) ---
        audio_file_path = generate_tts_audio(response_text, session_id)
        
        # --- PERSISTENCE ---
        save_chat_message(session_id, "user", user_message)
        save_chat_message(session_id, "model", response_text, meme_path, audio_file_path)  # UPDATED
        
        return jsonify({
            'response': response_text,
            'meme_url': f'/static/{meme_path}' if meme_path else None, 
            'audio_url': f'/static/{audio_file_path}' if audio_file_path else None, # NEW
            'status': 'success'
        })

    except Exception as e:
        return jsonify({'error': f'An error occurred: {e}'}), 500

if __name__ == '__main__':
    if not os.path.exists('templates'):
        os.makedirs('templates')
    if not os.path.exists('static/Memes'): 
        os.makedirs('static/Memes')
    # NEW: Create directory for TTS audio
    if not os.path.exists('static/audio'):
        os.makedirs('static/audio')
    
    app.run(debug=True)
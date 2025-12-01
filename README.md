An intelligent, LLM-powered chatbot designed to support students emotionally while also assisting them with placement-related queries. EMOTI combines empathetic conversation, safe responses, and career-oriented guidance into a single unified platform.

# 🧠 Project Overview

EMOTI is designed to address two common student needs:

##### Emotional Support — a safe space for students to express how they feel and receive supportive, non-judgmental messages.

##### Placement Assistance — exam, interview guidance, common questions, and career suggestions.

The system uses a Large Language Model as its reasoning engine, wrapped with multiple safety layers to ensure responsible, non-diagnostic, and supportive communication.

# 🚀 Features
### 💬 Emotional Support

Empathetic responses

Validating language

Stress-relief suggestions

Crisis-aware safety messages

### 🎓 Placement Assistance

Exam preparation 

Interview preparation

Frequently asked questions

Guidance for communication skills, projects, and tech stacks

### 🔐 Safety Built-in

Automatic inclusion of disclaimers

Emotion classification to avoid harmful outputs

Redirects to real human support in sensitive scenarios

### 📦 Architecture

Frontend: HTML, CSS, JavaScript

Backend: Python (Flask)

LLM: Gemini API

Error Handling: Robust fallback responses if LLM fails

📁 Project Structure
EMOTI-AI-ChatBot/
│
├── app.py
├── placement_assistance_company_multilingual_emotional_links.csv
├── static
├── templates 
└── README.md

⚙️ Installation & Setup

1️⃣ Install Python Dependencies
pip install Flask google-genai pymongo pandas secure-smtplib

2️⃣ Configure API Key
in the terminal:
$env:GEMINI_API_KEY='your-api-key'

3️⃣ Run the Backend
python app.py


🔄 How It Works
 1. User enters message
 2. Frontend sends request → Flask API
 3. LLM processes message with safety prompts
 4. JSON response returned with:
      - emotional_support
      - placement_guidance
      - safety_disclaimer

 5. Frontend displays structured response

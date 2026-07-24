import streamlit as st
import speech_recognition as sr
from gtts import gTTS
import os
import tempfile
import pygame
import random
import pickle
import time
import uuid
import langid
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

import db

# ---------------------------------------------------------------------------
# Database initialization (runs once per app start, idempotent)
# ---------------------------------------------------------------------------
db.init_db()

# ---------------------------------------------------------------------------
# Load intents from PostgreSQL (fallback to intents.json if DB is empty)
# ---------------------------------------------------------------------------
intents = db.load_intents_from_db()

if not intents["intents"]:
    # DB is empty — fall back to JSON so the app still works before migration
    import json
    with open("intents.json", "r", encoding='utf-8') as f:
        intents = json.load(f)

# Load trained model and vectorizer
with open("intent_model.pkl", "rb") as f:
    model = pickle.load(f)
with open("vectorizer.pkl", "rb") as f:
    vectorizer = pickle.load(f)

# Initialize pygame mixer for voice output
pygame.mixer.init()

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "input_mode" not in st.session_state:
    st.session_state.input_mode = "text"
if "selected_lang" not in st.session_state:
    st.session_state.selected_lang = "en"  # default to English
if "db_session_id" not in st.session_state:
    # Generate a unique session identifier and register it in the DB
    uid = str(uuid.uuid4())
    st.session_state.db_session_id = db.get_or_create_session(uid, "en")
    st.session_state.session_uid = uid

    # Load any prior chat history for this session (survives page reloads)
    prior = db.get_chat_history(st.session_state.db_session_id)
    for msg in prior:
        if msg["role"] == "user":
            prefix = "🎤 " if msg["input_mode"] == "voice" else ""
            st.session_state.chat_history.append((f"{prefix}{msg['message']}", ""))
        elif msg["role"] == "bot":
            # Pair bot response with the last user entry
            if st.session_state.chat_history and st.session_state.chat_history[-1][1] == "":
                last_user, _ = st.session_state.chat_history[-1]
                prefix = "🔊 " if msg["input_mode"] == "voice" else ""
                st.session_state.chat_history[-1] = (last_user, f"{prefix}{msg['message']}")

# Detect language
def detect_language(text):
    lang, _ = langid.classify(text)
    return "ta" if lang == "ta" else "en"

# Predict intent
def predict_intent(text):
    X = vectorizer.transform([text])
    return model.predict(X)[0]

# Get bot response
def get_bot_response(text):
    intent = predict_intent(text)
    lang = detect_language(text)
    responses = next((i["responses"] for i in intents["intents"] if i["tag"] == intent), {})
    response_list = responses.get(lang, [])
    if not response_list:
        return "மன்னிக்கவும், புரியவில்லை." if lang == "ta" else "Sorry, I didn't understand that."
    return random.choice(response_list)

# Voice recognition
def recognize_speech(lang_code):
    r = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("Listening...")
        audio = r.listen(source)
    try:
        text = r.recognize_google(audio, language=lang_code)
        return text
    except sr.UnknownValueError:
        return "Sorry, could not understand."
    except sr.RequestError:
        return "Could not request results."

# Voice output with safe playback
def play_voice_response(text, lang):
    try:
        tts = gTTS(text=text, lang=lang)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            temp_path = fp.name
            tts.save(temp_path)

        pygame.mixer.music.load(temp_path)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            time.sleep(0.1)

        pygame.mixer.music.unload()
        os.remove(temp_path)

    except Exception as e:
        print(f"Error in voice playback: {e}")

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.title("👮 CopChatbot - Tamil & English")

# Language selection buttons
col_lang1, col_lang2 = st.columns(2)
if col_lang1.button("தமிழ்"):
    st.session_state.selected_lang = "ta"
if col_lang2.button("English"):
    st.session_state.selected_lang = "en"

# Display current language
current_lang_display = "Tamil (தமிழ்)" if st.session_state.selected_lang == "ta" else "English"
st.markdown(f"**Selected Language:** {current_lang_display}")

# Chat display
for user, bot in st.session_state.chat_history:
    st.markdown(f"**You:** {user}")
    st.markdown(f"**CopChatbot:** {bot}")

# Input area
placeholder_text = "உங்கள் கேள்வியை இங்கே பதிவு செய்யவும்..." if st.session_state.selected_lang == "ta" else "Type your question here..."
col1, col2 = st.columns([9, 1])
with col1:
    user_input = st.text_input(placeholder_text, key="input", label_visibility="collapsed")
with col2:
    mic_clicked = st.button("🎤", key="mic")
send_clicked = st.button("Send")

# Handle input
if mic_clicked:
    recog_lang = "ta-IN" if st.session_state.selected_lang == "ta" else "en-IN"
    user_input = recognize_speech(recog_lang)
    st.session_state.input_mode = "voice"
    st.session_state.chat_history.append((f"🎤 {user_input}", ""))  # temp display
    response = get_bot_response(user_input)
    detected_lang = detect_language(user_input)
    st.session_state.chat_history[-1] = (f"🎤 {user_input}", f"🔊 {response}")
    play_voice_response(response, detected_lang)

    # Persist to DB
    db.save_chat_message(st.session_state.db_session_id, "user", user_input, "voice")
    db.save_chat_message(st.session_state.db_session_id, "bot", response, "voice")

elif send_clicked and user_input:
    st.session_state.input_mode = "text"
    response = get_bot_response(user_input)
    st.session_state.chat_history.append((user_input, response))

    # Persist to DB
    db.save_chat_message(st.session_state.db_session_id, "user", user_input, "text")
    db.save_chat_message(st.session_state.db_session_id, "bot", response, "text")

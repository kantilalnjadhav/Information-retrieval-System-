import os
import textwrap
import re
from io import BytesIO
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from gtts import gTTS
import speech_recognition as sr
import streamlit as st
import streamlit.components.v1 as components
from deep_translator import GoogleTranslator
from duckduckgo_search import DDGS

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

# ========== ENV SETUP ========== #
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    raise ValueError("❌ GOOGLE_API_KEY not found in .env")

# ========== HELPER FUNCTIONS ========== #
def get_pdf_text(pdf_files):
    text = ""
    for pdf in pdf_files:
        reader = PdfReader(pdf)
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content
    print("[DEBUG] Extracted PDF text length:", len(text))
    return text

def get_text_chunks(text, chunk_size=1000, chunk_overlap=200):
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_text(text)
    print("[DEBUG] Text chunk count:", len(chunks))
    return chunks

def get_vector_store(chunks):
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=API_KEY
    )
    return FAISS.from_texts(chunks, embedding=embeddings)

def get_conversational_chain(vector_store):
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=API_KEY,
        temperature=0.3
    )
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )
    return ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vector_store.as_retriever(),
        memory=memory
    )

def text_to_speech(text: str, lang='en', chunk_size=4500) -> BytesIO:
    tld_map = {
        'en': 'com', 'hi': 'co.in', 'mr': 'co.in', 'es': 'es', 'de': 'de',
        'ta': 'com', 'ja': 'co.jp', 'ru': 'ru', 'ko': 'co.kr'
    }
    tld = tld_map.get(lang, 'com')
    buffers = []
    for chunk in textwrap.wrap(text, chunk_size, break_long_words=False):
        buf = BytesIO()
        gTTS(chunk, lang=lang, tld=tld).write_to_fp(buf)
        buffers.append(buf.getvalue())
    audio = BytesIO(b"".join(buffers))
    audio.seek(0)
    return audio

def listen_for_voice_question(timeout=5):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎧 Listening...")
        try:
            audio = recognizer.listen(source, timeout=timeout)
            return recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return "Sorry, I couldn't understand your question."
        except sr.RequestError:
            return "Speech recognition service is not available."
        except sr.WaitTimeoutError:
            return "Listening timed out. Try again."

def classify_voice_intent(text: str) -> str:
    prompt = f"""Classify the user instruction into one of two categories: 'command' or 'question'.\nInstruction: \"{text}\"\nOnly respond with 'command' or 'question'."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=API_KEY,
        temperature=0
    )
    return llm.invoke(prompt).strip().lower()

def translate_text(text: str, target_lang_code: str) -> str:
    try:
        translated = GoogleTranslator(source='auto', target=target_lang_code).translate(text)
        return translated
    except Exception as e:
        print("[ERROR] Translation failed:", e)
        return "Translation failed. Please try again."
def web_search_snippet(query, max_results=1):
    with DDGS() as ddgs:
        results = ddgs.text(query, region='in-en', safesearch='moderate', max_results=max_results)
        for r in results:
            return r['body']
    return "No additional information found on the web."        
    
    
    
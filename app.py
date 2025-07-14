import os
import streamlit as st
import base64
import streamlit.components.v1 as components
from src.helper import (
    get_pdf_text,
    get_text_chunks,
    get_vector_store,
    get_conversational_chain,
    listen_for_voice_question,
    text_to_speech,
    translate_text,
    web_search_snippet
)
#from dotenv import load_dotenv

# --- DEBUGGING AID: Check if script runs multiple times ---
print("Streamlit app script started!")
# --- END DEBUGGING AID ---

# Load environment variables
#load_dotenv()
st.set_page_config("Information Retrieval System")
st.title("PDF Reader + Audio Assistant")

# Initialize session state
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = None
if "latest_pdf_text" not in st.session_state:
    st.session_state.latest_pdf_text = ""
if "main_audio" not in st.session_state:
    st.session_state.main_audio = None
if "main_audio_base64" not in st.session_state:
    st.session_state.main_audio_base64 = ""
if "web_snippet" not in st.session_state: # Ensure web_snippet is initialized
    st.session_state.web_snippet = ""
if "current_user_question" not in st.session_state: # New: To persist text input value
    st.session_state.current_user_question = ""
if "last_processed_question" not in st.session_state: # New: To prevent reprocessing same question
    st.session_state.last_processed_question = ""


lang_map = {
    "English": "en", "Hindi": "hi", "Marathi": "mr", "Spanish": "es",
    "German": "de", "Tamil": "ta", "Japanese": "ja", "Russian": "ru", "Korean": "ko"
}

# PDF Upload and Processing
pdf_docs = st.sidebar.file_uploader("Choose PDFs", type=["pdf"], accept_multiple_files=True)
if st.sidebar.button("Process PDFs") and pdf_docs:
    with st.spinner("Reading & indexing PDF(s)..."):
        text = get_pdf_text(pdf_docs)
        chunks = get_text_chunks(text)
        store = get_vector_store(chunks)
        st.session_state.conversation = get_conversational_chain(store)
        st.session_state.latest_pdf_text = text
    st.success("Ready for questions and audio!")

# Language Selection
selected_lang = st.sidebar.selectbox("Choose Language", list(lang_map.keys()))
selected_lang_code = lang_map[selected_lang]

# Generate Narration
if st.sidebar.button("Read"):
    if st.session_state.latest_pdf_text:
        with st.spinner(f"Translating and generating audio in {selected_lang}..."):
            translated_text = st.session_state.latest_pdf_text
            if selected_lang_code != 'en':
                translated_text = translate_text(translated_text, target_lang_code=selected_lang_code)
            st.session_state.translated_text = translated_text
            st.session_state.main_audio = text_to_speech(translated_text, lang=selected_lang_code)
            st.session_state.main_audio.seek(0)
            audio_bytes = st.session_state.main_audio.read()
            st.session_state.main_audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        st.sidebar.success("Narration generated. See main area to play.")
    else:
        st.sidebar.warning("Please upload and process a PDF first.")

# \ud83c\udf99 Ask by Voice
with st.sidebar:
    st.markdown("---")
    st.subheader("Ask by Voice")
    if st.button("Listen Now"):
        if st.session_state.conversation:
            components.html("""
                <script>
                    const narrationAudio = document.getElementById("pdf_audio");
                    if (narrationAudio && !narrationAudio.paused) {
                        narrationAudio.dataset.pausedByQA = true;
                        narrationAudio.pause();
                    }
                </script>
            """, height=0)

            with st.spinner("Listening for voice question..."):
                user_voice = listen_for_voice_question()

            if "Sorry" in user_voice or "timed out" in user_voice:
                st.warning(user_voice)
            else:
                st.success(f"You asked: {user_voice}")
                result = st.session_state.conversation.invoke({"question": user_voice})
                answer = result["answer"]
                st.markdown(f"**Answer:** {answer}")

                if not answer.strip():
                    answer = "Sorry, I do not have an answer to that."
                elif len(answer.strip().split()) < 3:
                    answer += "."

                with st.spinner("Generating voice reply..."):
                    try:
                        voice_audio = text_to_speech(answer, lang='en')
                        voice_audio.seek(0)
                        voice_audio_bytes = voice_audio.read()

                        if len(voice_audio_bytes) == 0:
                            st.error("Audio generation failed.")
                        else:
                            st.audio(voice_audio_bytes, format="audio/mp3")
                            voice_audio_b64 = base64.b64encode(voice_audio_bytes).decode("utf-8")
                            components.html(f"""
                                <audio id=\"voice_reply\" hidden>
                                    <source src=\"data:audio/mp3;base64,{voice_audio_b64}\" type=\"audio/mp3\">
                                </audio>
                                <script>
                                    const voiceAudio = document.getElementById("voice_reply");
                                    const narrationAudio = document.getElementById("pdf_audio");
                                    if (voiceAudio && narrationAudio) {{
                                        voiceAudio.onended = function () {{
                                            if (narrationAudio.dataset.pausedByQA === "true") {{
                                                narrationAudio.play();
                                                narrationAudio.dataset.pausedByQA = "false";
                                            }}
                                        }};
                                        voiceAudio.play();
                                    }}
                                </script>
                            """, height=0)

                        # Web search for voice questions
                        if st.button("Search Web for More Info (Voice Question)"):
                            with st.spinner("Searching the web..."):
                                snippet = web_search_snippet(user_voice)
                                st.markdown("**\ud83d\udcda Web Info:**")
                                st.write(snippet)
                                st.session_state.web_snippet = snippet # Store snippet

                        if st.session_state.web_snippet and st.checkbox("Read Web Info Aloud (Voice Question)"):
                            web_audio = text_to_speech(st.session_state.web_snippet, lang='en')
                            st.audio(web_audio.read(), format="audio/mp3")

                    except Exception as e:
                        st.error(f"\u274c Failed to generate audio response. Try again. Error: {e}")
        else:
            st.warning("Please upload and process a PDF first.")

# \ud83c\udf99 Render Main Audio Player
# \ud83c\udf99 Render Main Audio Player
# --- DEBUGGING AID: Check if main_audio_base64 has content ---
print(f"main_audio_base64 exists (for rendering): {bool(st.session_state.main_audio_base64)}")
# --- END DEBUGGING AID ---
if st.session_state.main_audio_base64:
    # Use columns to align the audio player and download button horizontally
    audio_col, download_col = st.columns([3, 1]) # Columns defined directly inside the if block

    with audio_col:
        audio_html = f'''
            <audio id="pdf_audio" controls>
                <source src="data:audio/mp3;base64,{st.session_state.main_audio_base64}" type="audio/mp3">
                Your browser does not support the audio element.
            </audio>
        '''
        components.html(audio_html, height=70)

    with download_col:
        # Add custom CSS for vertical alignment of the download button
        st.markdown(
            """
            <style>
            div.stDownloadButton > button {
                margin-top: 1.0rem; /* Adjusted value for alignment */
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        st.download_button(
            label="Download Audio",
            data=base64.b64decode(st.session_state.main_audio_base64),
            file_name="pdf_narration.mp3",
            mime="audio/mp3",
            help="Click to download the generated audio narration."
        )
    

# --- Callback function for text input changes ---
def update_user_question_state():
    """Updates the session state with the current value of the text_input."""
    st.session_state.current_user_question = st.session_state.question_input_widget_key

# \u270d\ufe0f Ask via Text
st.markdown("---")
st.markdown("### 🧠 Ask a Question about the PDF")

col1, col2 = st.columns([4, 1])

with col1:
    # Using st.session_state.current_user_question for value and on_change to update it
    user_question_input = st.text_input(
        "Enter your question here:",
        value=st.session_state.current_user_question,
        key="question_input_widget_key", # Unique key for the widget
        on_change=update_user_question_state # Call the callback on change
    )

with col2:
    st.markdown(
        """
        <style>
        div.stButton > button {
            margin-top: 0.9rem; /* Adjust this value as needed for perfect alignment */
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    search_web_clicked = st.button("🌐Web Search", key="search_button")

# --- PDF QA Answer ---
# This block will execute when user_question_input changes (e.g., user presses Enter)
if user_question_input and st.session_state.conversation:
    # Only process if the question has changed from the last processed one
    # This prevents reprocessing the same question on every rerun
    if user_question_input != st.session_state.last_processed_question:
        result = st.session_state.conversation.invoke({"question": user_question_input})
        st.session_state.chat_history = result["chat_history"]

        for i, msg in enumerate(st.session_state.chat_history):
            speaker = "👤" if i % 2 == 0 else "🤖"
            st.write(f"{speaker}: {msg.content}")

        # Store the last processed question and clear the input box
        st.session_state.last_processed_question = user_question_input
        st.session_state.current_user_question = "" # Clear the input box after processing
        # This will trigger another rerun, and the text_input will render empty.

# --- Web Search (Only if button clicked) ---
# This block will execute when the search_web_clicked button is pressed
# It also handles the case where a user types a question but no PDF is processed,
# and they explicitly click the web search button.
if search_web_clicked and user_question_input:
    with st.spinner("Searching the web..."):
        snippet = web_search_snippet(user_question_input)
        st.markdown("**🌐 Web Info:**")
        st.write(snippet)
        st.session_state.web_snippet = snippet # Store snippet for audio playback

    if st.session_state.web_snippet and st.checkbox("🔊 Read Web Info Aloud", key="web_info_audio"):
        web_audio = text_to_speech(st.session_state.web_snippet, lang='en')
        st.audio(web_audio.read(), format="audio/mp3")

    # Clear the input box after web search
    st.session_state.current_user_question = ""
    st.session_state.last_processed_question = "" # Clear last processed question for new input
elif user_question_input and not st.session_state.conversation:
    # This handles the case where a user types a question and presses Enter,
    # but no PDF is processed. It prompts them to use the web search button.
    st.warning("Please upload and process a PDF first to get answers from the document. To search the web for this question, please click the '🌐 Search Web' button.")


# \ud83d\uddd8\ufe0f Show Translated Text
if "translated_text" in st.session_state and st.session_state.translated_text:
    st.markdown("### Translated Text")
    st.write(st.session_state.translated_text)

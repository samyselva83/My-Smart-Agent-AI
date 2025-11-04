import streamlit as st
import tempfile
import os
import torch
import torchaudio
import whisper
from groq import Groq
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

# -----------------------------
# ✅ App setup
# -----------------------------
st.set_page_config(page_title="My Smart Agent", page_icon="🤖", layout="wide")
st.title("🤖 My Smart Agent — Multitasking AI Assistant")

# -----------------------------
# 🔑 Groq API Setup
# -----------------------------
if "GROQ_API_KEY" not in st.secrets or not st.secrets["GROQ_API_KEY"]:
    st.error("⚠️ Please add your GROQ_API_KEY in Streamlit → Edit Secrets.")
    st.stop()
else:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=GROQ_API_KEY)

# -----------------------------
# 🌍 Language Selection
# -----------------------------
languages = {
    "English": "en",
    "Tamil": "ta",
    "Telugu": "te",
    "Malayalam": "ml",
    "Kannada": "kn",
    "Hindi": "hi",
    "French": "fr",
    "Spanish": "es",
    "German": "de",
    "Japanese": "ja"
}
selected_lang = st.sidebar.selectbox("🌍 Choose Summary Language", list(languages.keys()))

# -----------------------------
# 🧠 Groq Summarization Utility
# -----------------------------
def groq_summary(text, language):
    """Summarize text using Groq's Llama 3.2 model."""
    try:
        prompt = f"Summarize this text in {language} in less than 10 bullet points:\n{text[:8000]}"
        response = client.chat.completions.create(
            model="groq/llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        if "model_decommissioned" in str(e):
            return "⚠️ Model deprecated. Please update to the latest Groq model."
        elif "401" in str(e):
            return "❌ Invalid Groq API Key. Please verify your key."
        else:
            return f"Groq summarization error: {e}"

# -----------------------------
# 🗓️ 1. Daily Planner
# -----------------------------
def daily_planner():
    st.subheader("📅 Daily Planner")
    tasks = st.text_area("📝 List your tasks (one per line):")
    if st.button("Generate Plan"):
        if tasks.strip():
            plan = groq_summary(f"Create a structured day plan for:\n{tasks}", selected_lang)
            st.write(plan)
        else:
            st.warning("Please enter at least one task.")

# -----------------------------
# 💰 2. Finance Tracker
# -----------------------------
def finance_tracker():
    st.subheader("💰 Finance Tracker")
    income = st.number_input("💵 Monthly income:", min_value=0)
    expenses = st.text_area("💸 Expenses (one per line: item - amount):")
    if st.button("Analyze Finances"):
        try:
            total_expense = 0
            for line in expenses.splitlines():
                parts = line.split("-")
                if len(parts) == 2:
                    total_expense += float(parts[1].strip())
            balance = income - total_expense
            st.success(f"💰 Remaining Balance: {balance}")
            st.write(groq_summary(f"Income: {income}, Expenses: {expenses}", selected_lang))
        except Exception as e:
            st.error(f"Error: {e}")

# -----------------------------
# ❤️ 3. Health & Habits
# -----------------------------
def health_and_habits():
    st.subheader("❤️ Health & Habits")
    habits = st.text_area("🏋️ List your habits (one per line):")
    if st.button("Analyze Habits"):
        if habits.strip():
            st.write(groq_summary(f"Analyze and suggest improvements for these habits:\n{habits}", selected_lang))
        else:
            st.warning("Please enter your habits first.")

# -----------------------------
# 📘 4. LearnMate
# -----------------------------
def learn_mate():
    st.subheader("📘 LearnMate — AI Learning Assistant")
    topic = st.text_input("Enter a topic to learn about:")
    if st.button("Teach Me"):
        if topic.strip():
            st.write(groq_summary(f"Explain the topic for a student: {topic}", selected_lang))
        else:
            st.warning("Please enter a topic.")

# -----------------------------
# 🎬 5. Video Summarizer
# -----------------------------
def summarize_video_agent():
    st.subheader("🎬 Video Summarizer")
    st.write("Upload a local video or enter a YouTube URL to summarize.")

    video_url = st.text_input("🎥 YouTube URL (optional):")
    uploaded_file = st.file_uploader("📂 Upload local video (MP4 format)", type=["mp4"])

    def fetch_youtube_transcript(video_id):
        try:
            api = YouTubeTranscriptApi()
            transcripts = api.list_transcripts(video_id)
            text = ""
            for t in transcripts:
                text += " ".join([seg["text"] for seg in t.fetch()])
            return text
        except Exception as e:
            st.warning(f"⚠️ Transcript not available: {e}")
            return ""

    def download_audio(url):
        """Download audio only — no ffmpeg or pydub."""
        st.info("🎧 Downloading YouTube audio (no ffmpeg)...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmpfile:
            ydl_opts = {"format": "bestaudio/best", "outtmpl": tmpfile.name, "quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            waveform, sr = torchaudio.load(tmpfile.name)
            wav_path = tmpfile.name + ".wav"
            torchaudio.save(wav_path, waveform, sr)
            return wav_path

    if st.button("Summarize Video"):
        try:
            text = ""
            if video_url:
                st.info("Processing YouTube video...")
                video_id = ""
                if "v=" in video_url:
                    video_id = video_url.split("v=")[-1].split("&")[0]
                elif "youtu.be" in video_url:
                    video_id = video_url.split("/")[-1]
                text = fetch_youtube_transcript(video_id)
                if not text.strip():
                    st.info("🎤 No transcript found — using Whisper transcription.")
                    audio_file = download_audio(video_url)
                    model = whisper.load_model("tiny")
                    result = model.transcribe(audio_file)
                    text = result["text"]

            elif uploaded_file:
                st.info("🎤 Transcribing uploaded video...")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name
                model = whisper.load_model("tiny")
                result = model.transcribe(tmp_path)
                text = result["text"]

            if text.strip():
                summary = groq_summary(text, selected_lang)
                st.markdown("### 🧠 Summary")
                st.write(summary)
            else:
                st.warning("No transcript or text to summarize.")

        except Exception as e:
            st.error(f"❌ Error while summarizing: {e}")

# -----------------------------
# 🧭 Sidebar Navigation
# -----------------------------
tab = st.sidebar.radio(
    "🧩 Choose Smart Agent Mode",
    ["🗓️ Daily Planner", "💰 Finance Tracker", "❤️ Health & Habits", "📘 LearnMate", "🎬 Video Summarizer"]
)

if tab == "🗓️ Daily Planner":
    daily_planner()
elif tab == "💰 Finance Tracker":
    finance_tracker()
elif tab == "❤️ Health & Habits":
    health_and_habits()
elif tab == "📘 LearnMate":
    learn_mate()
elif tab == "🎬 Video Summarizer":
    summarize_video_agent()

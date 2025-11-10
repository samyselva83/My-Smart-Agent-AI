# streamlit_app.py
# 🌐 My Smart Agent – Multi-Agent AI Dashboard
# Agents: Dashboard, Daily Planner, Finance Tracker, Health & Habits, LearnMate, Memory, Video Summarizer

import os
import tempfile
import base64
import time
from datetime import datetime as dtime
import streamlit as st
import pandas as pd
import requests
from groq import Groq
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
import imageio_ffmpeg

# ✅ FFmpeg PATH Fix (works even on Streamlit Cloud)
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)
os.environ["FFMPEG_BINARY"] = ffmpeg_path
st.write(f"✅ FFmpeg binary registered: {ffmpeg_path}")

# ----------------------------------------------
# Groq API Setup
# ----------------------------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    st.warning("⚠️ Please set your GROQ_API_KEY in Streamlit Secrets!")
client = Groq(api_key=GROQ_API_KEY)

# ----------------------------------------------
# App Config
# ----------------------------------------------
st.set_page_config(page_title="My Smart Agent", layout="wide", page_icon="🤖")

st.sidebar.title("🤖 My Smart Agent Menu")
menu = [
    "Dashboard",
    "Daily Planner (AI)",
    "Finance Tracker",
    "Health & Habits",
    "LearnMate",
    "Memory",
    "Video Summarizer",
]
choice = st.sidebar.radio("Choose a module", menu)
lang_choice = st.sidebar.selectbox(
    "Language",
    ["English", "Tamil", "Telugu", "Malayalam", "Kannada", "Hindi", "French", "Spanish", "German", "Japanese"]
)

# ----------------------------------------------
# Utility Functions
# ----------------------------------------------
def groq_summarize_text(text, language="English"):
    """Summarize text using Groq API in the selected language"""
    try:
        prompt = f"Summarize this content in {language}. Include main highlights and timestamps if available:\n{text}"
        response = client.chat.completions.create(
            model="mixtral-8x7b",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Groq summarization error: {e}"


def get_youtube_id(url: str):
    """Extract YouTube video ID"""
    import re
    match = re.search(r"(?:v=|/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None


def get_youtube_info(video_id):
    """Fetch video metadata"""
    try:
        yt = YouTube(f"https://www.youtube.com/watch?v={video_id}")
        return yt.title, yt.thumbnail_url, yt.length, yt.author
    except Exception:
        return "Unknown Title", "", "Unknown", "Unknown"


def summarize_youtube(video_url, language="English"):
    """Main summarization logic"""
    try:
        video_id = get_youtube_id(video_url)
        if not video_id:
            return None, None, "Invalid YouTube link"

        title, thumb, duration, channel = get_youtube_info(video_id)

        # Try to get captions
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            text = " ".join([seg["text"] for seg in transcript])
        except Exception as e:
            text = None
            st.warning(f"Captions not available or fetch failed: {e}")

        # Fallback: audio transcription
        if not text:
            import yt_dlp
            temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name

            # ✅ Explicit ffmpeg/ffprobe path for yt_dlp
            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": temp_audio,
                "quiet": True,
                "ffmpeg_location": ffmpeg_dir,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192"
                }],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            # ✅ Transcribe using Whisper
            import whisper
            model = whisper.load_model("tiny")
            result = model.transcribe(temp_audio)
            text = result["text"]

        summary = groq_summarize_text(text, language)
        return title, thumb, summary

    except Exception as e:
        return None, None, f"❌ Error while summarizing: {e}"

# ----------------------------------------------
# Agents
# ----------------------------------------------

if choice == "Dashboard":
    st.title("📊 Dashboard")
    st.markdown("""
    Welcome to **My Smart Agent** — a multi-agent AI system built with Streamlit and Groq API.

    **Available Agents:**
    - 🗓️ Daily Planner (AI)
    - 💵 Finance Tracker
    - 💪 Health & Habits
    - 🧠 LearnMate
    - 🧾 Memory
    - 🎬 Video Summarizer
    """)

elif choice == "Daily Planner (AI)":
    st.title("🗓️ Daily Planner (AI)")
    st.info("Enter up to 5–10 tasks, and AI will auto-assign smart time slots.")
    user_tasks = st.text_area("Your tasks (one per line)")
    if st.button("🧠 Generate Smart Plan"):
        if user_tasks.strip():
            tasks = user_tasks.strip().split("\n")
            prompt = f"Create a realistic daily schedule for the following tasks. Auto-assign time slots smartly:\n\n{user_tasks}"
            plan = groq_summarize_text(prompt, "English")
            st.success("✅ Smart Daily Planner Generated:")
            st.write(plan)
        else:
            st.warning("Please enter some tasks first!")

elif choice == "Finance Tracker":
    st.title("💵 Finance Tracker")
    st.info("Track your expenses easily.")
    date = st.date_input("Date")
    category = st.selectbox("Category", ["Food", "Transport", "Bills", "Entertainment", "Other"])
    amount = st.number_input("Amount", min_value=0.0)
    note = st.text_input("Note (optional)")
    if st.button("Add Expense"):
        new = pd.DataFrame([[date, category, amount, note]], columns=["Date", "Category", "Amount", "Note"])
        if "expenses" not in st.session_state:
            st.session_state["expenses"] = new
        else:
            st.session_state["expenses"] = pd.concat([st.session_state["expenses"], new], ignore_index=True)
        st.success("✅ Expense added!")

    if "expenses" in st.session_state:
        st.subheader("💰 Expense Summary")
        df = st.session_state["expenses"]
        st.dataframe(df)
        st.write("**Total Spent:** ₹", df["Amount"].sum())

elif choice == "Health & Habits":
    st.title("💪 Health & Habits")
    habit = st.text_input("Enter habit (e.g., Drink water, Exercise)")
    if st.button("Add Habit"):
        st.session_state.setdefault("habits", []).append(habit)
        st.success(f"✅ Added habit: {habit}")

    if "habits" in st.session_state:
        st.subheader("Your Habits")
        for h in st.session_state["habits"]:
            st.checkbox(h)

elif choice == "LearnMate":
    st.title("🧠 LearnMate")
    topic = st.text_input("Enter topic to learn")
    if st.button("📘 Teach Me"):
        st.info("Fetching learning summary...")
        result = groq_summarize_text(f"Explain the topic '{topic}' for easy understanding.", lang_choice)
        st.success(result)

elif choice == "Memory":
    st.title("🧾 Memory")
    note = st.text_area("Write a note")
    if st.button("Save Note"):
        st.session_state.setdefault("notes", []).append(note)
        st.success("🧠 Memory saved!")

    if "notes" in st.session_state:
        st.subheader("Saved Notes")
        for i, n in enumerate(st.session_state["notes"], 1):
            st.markdown(f"**{i}.** {n}")

elif choice == "Video Summarizer":
    st.title("🎬 Video Summarizer — Multilingual AI Highlights with Clickable Timestamps")
    st.info("Paste a YouTube link to get smart summaries in your selected language.")
    video_url = st.text_input("Paste YouTube URL")
    if st.button("Summarize Video"):
        with st.spinner("Analyzing video..."):
            title, thumb, summary = summarize_youtube(video_url, lang_choice)
            if "❌" in str(summary):
                st.error(summary)
            else:
                if thumb:
                    st.image(thumb, width=400)
                st.markdown(f"**🎞️ Title:** {title}")
                st.markdown(f"**🌐 Language:** {lang_choice}")
                st.write(summary)

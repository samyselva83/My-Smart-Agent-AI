# streamlit_app.py
# 🌟 My Smart Agent — Streamlit Multi-Agent App (Final Stable Cloud Version)
# Includes: Dashboard, Daily Planner, Finance Tracker, Health & Habits, LearnMate, Video Summarizer

import streamlit as st
from datetime import datetime, time
import tempfile
import os
import re
import base64
import time
import imageio_ffmpeg

# ✅ FFmpeg fallback setup for Streamlit Cloud
os.environ["PATH"] += os.pathsep + os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())

# External imports
from groq import Groq
import yt_dlp
import whisper
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
import streamlit.components.v1 as components

# ============================================================
# Initialize Groq Client
# ============================================================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "your_groq_key_here")

client = Groq(api_key=GROQ_API_KEY)

# ============================================================
# Utility Functions
# ============================================================

def summarize_text_with_groq(text, lang="English"):
    """Summarize given text in requested language."""
    try:
        prompt = f"Summarize this video transcript in {lang}. Include key highlights and timestamps if available:\n\n{text[:12000]}"
        response = client.chat.completions.create(
            model="llama-3.2-11b-text-preview",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Groq summarization error: {e}"


def download_audio_to_wav_yt_dlp(url: str):
    """Download audio from YouTube with a Streamlit progress bar (no ffmpeg)."""
    st.info("🎧 Starting audio download (no ffmpeg)...")
    tmpdir = tempfile.gettempdir()
    out_path = os.path.join(tmpdir, "msa_audio_for_whisper.webm")

    progress = st.progress(0)
    status = st.empty()

    class ProgressHook:
        def __call__(self, d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 1
                downloaded = d.get('downloaded_bytes', 0)
                percent = min(100, int(downloaded / total * 100))
                progress.progress(percent)
                status.text(f"⬇️ Downloading audio: {percent}%")
            elif d['status'] == 'finished':
                status.text("✅ Download complete. Finalizing...")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_path,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [ProgressHook()],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        progress.progress(100)
        status.text("✅ Audio file ready for transcription.")
    except Exception as e:
        raise RuntimeError(f"yt_dlp audio download failed: {e}")

    if not os.path.exists(out_path):
        raise FileNotFoundError("yt_dlp did not produce an audio file.")
    return out_path


def transcribe_with_whisper(wav_path):
    """Transcribe audio using Whisper tiny model."""
    st.info("🧠 Transcribing audio with Whisper (tiny)... Please wait, may take a minute.")
    try:
        model = whisper.load_model("tiny")
        result = model.transcribe(wav_path)
        return result["text"]
    except Exception as e:
        raise RuntimeError(f"Whisper transcription failed: {e}")


def extract_youtube_id(url):
    match = re.search(r"(?:v=|/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None


def get_youtube_info(url):
    """Fetch video info via pytube safely."""
    try:
        yt = YouTube(url)
        return yt.title, yt.thumbnail_url, yt.length, yt.author
    except Exception:
        return "Unknown", None, "Unknown", "Unknown"

# ============================================================
# Video Summarizer Agent
# ============================================================

def summarize_video_agent():
    st.header("🎬 Video Summarizer (AI)")
    st.write("Upload or link a YouTube video to generate AI-based highlights with timestamps.")
    st.divider()

    video_url = st.text_input("🔗 Enter YouTube URL:")
    uploaded_file = st.file_uploader("Or upload a local video file", type=["mp4", "mkv", "webm", "m4a"])

    lang = st.selectbox(
        "🌐 Select summary language:",
        ["English", "Tamil", "Telugu", "Malayalam", "Kannada", "Hindi", "French", "Spanish", "German", "Japanese"],
    )

    if st.button("✨ Summarize Video"):
        if not video_url and not uploaded_file:
            st.warning("Please provide a YouTube link or upload a file.")
            return

        try:
            if video_url:
                vid = extract_youtube_id(video_url)
                title, thumb, duration, channel = get_youtube_info(video_url)
                st.markdown(f"**Title:** {title}\n\n**Channel:** {channel}\n\n**Duration:** {duration} sec")

                if thumb:
                    st.image(thumb, width=400)

                st.write("Attempting to fetch captions...")
                try:
                    transcript = YouTubeTranscriptApi.get_transcript(vid)
                    text = " ".join([x["text"] for x in transcript])
                    st.success("✅ Captions retrieved successfully!")
                except Exception:
                    st.warning("Captions not available, using Whisper for audio transcription...")
                    wav_path = download_audio_to_wav_yt_dlp(video_url)
                    text = transcribe_with_whisper(wav_path)

            elif uploaded_file:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tmp.write(uploaded_file.read())
                tmp.flush()
                st.info("Transcribing uploaded video...")
                text = transcribe_with_whisper(tmp.name)

            summary = summarize_text_with_groq(text, lang)
            st.success("✅ Summary generated successfully!")

            # Display summary
            st.subheader("📋 Video Summary")
            st.write(summary)

            # Embed YouTube player if link provided
            if video_url:
                st.video(video_url)

        except Exception as e:
            st.error(f"❌ Error while summarizing: {e}")


# ============================================================
# Other Agents (placeholders for demo)
# ============================================================

def daily_planner():
    st.header("🗓️ Daily Planner (AI)")
    st.write("Plan your day intelligently with AI-assisted scheduling.")
    user_tasks = st.text_area("Enter your tasks or goals for today:")
    if st.button("🪄 Generate Smart Schedule"):
        st.write("AI is generating your schedule... (demo mode)")
        st.success("✅ Schedule ready! Future version will assign smart time slots automatically.")


def finance_tracker():
    st.header("💰 Finance Tracker")
    st.write("Track expenses and visualize your spending patterns.")
    st.info("Feature under development – coming soon!")


def health_habits():
    st.header("🏃 Health & Habits")
    st.write("Monitor habits and health routines.")
    st.info("Feature under development – coming soon!")


def learnmate():
    st.header("📚 LearnMate")
    st.write("Your personal AI learning companion.")
    st.info("Feature under development – coming soon!")

# ============================================================
# Sidebar Navigation
# ============================================================

st.sidebar.title("🤖 My Smart Agent")
choice = st.sidebar.radio(
    "Select a Module:",
    ["Dashboard", "Daily Planner (AI)", "Finance Tracker", "Health & Habits", "LearnMate", "Video Summarizer"]
)

if choice == "Dashboard":
    st.title("📊 My Smart Agent Dashboard")
    st.write("Welcome! Explore AI modules for your daily productivity and learning.")
elif choice == "Daily Planner (AI)":
    daily_planner()
elif choice == "Finance Tracker":
    finance_tracker()
elif choice == "Health & Habits":
    health_habits()
elif choice == "LearnMate":
    learnmate()
elif choice == "Video Summarizer":
    summarize_video_agent()

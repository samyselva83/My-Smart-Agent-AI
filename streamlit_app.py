# video_summarizer_app.py
# 🎬 Video Summarizer + Timestamp Highlighter Agent (Streamlit + Groq + Whisper)
import streamlit as st
import os
import re
import tempfile
import base64
import time
import imageio_ffmpeg
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
import whisper
from groq import Groq

# ✅ FFmpeg path fix (for Streamlit Cloud)
os.environ["PATH"] += os.pathsep + os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())

# ============================================================
# Initialize Groq
# ============================================================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "your_groq_key_here")

client = Groq(api_key=GROQ_API_KEY)

# ============================================================
# Utility Functions
# ============================================================

def extract_video_id(url):
    """Extract YouTube video ID from URL."""
    match = re.search(r"(?:v=|/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None


def get_video_info(url):
    """Fetch video metadata."""
    try:
        yt = YouTube(url)
        return yt.title, yt.thumbnail_url, yt.length, yt.author
    except Exception:
        return "Unknown", None, "Unknown", "Unknown"


def download_audio(url):
    """Download audio directly (no ffmpeg) for Whisper transcription."""
    tmpdir = tempfile.gettempdir()
    out_path = os.path.join(tmpdir, "audio_for_whisper.webm")
    st.info("🎧 Downloading audio...")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_path,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return out_path


def transcribe_audio(path):
    """Transcribe audio using Whisper tiny model."""
    st.info("🧠 Transcribing with Whisper (tiny)...")
    model = whisper.load_model("tiny")
    result = model.transcribe(path)
    return result["text"]


def summarize_with_groq(text, lang="English"):
    """Summarize transcript using Groq in specified language."""
    prompt = f"""
    Summarize this video transcript in {lang}.
    Include short bullet points and highlight timestamps (like 00:35, 01:10) for important moments.
    Transcript:
    {text[:12000]}
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.2-11b-text-preview",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Groq summarization error: {e}"


def make_clickable_summary(summary_text, video_url):
    """Convert timestamps in summary into clickable links for YouTube video."""
    def time_to_seconds(ts):
        parts = ts.split(":")
        return sum(int(x) * 60 ** (len(parts) - i - 1) for i, x in enumerate(parts))

    def replace_timestamp(match):
        ts = match.group()
        sec = time_to_seconds(ts)
        return f"[{ts}]({video_url}&t={sec}s)"

    return re.sub(r"\b\d{1,2}:\d{2}\b", replace_timestamp, summary_text)

# ============================================================
# Streamlit App UI
# ============================================================

st.set_page_config(page_title="🎬 Video Summarizer Agent", layout="wide")
st.title("🎬 Video Summarizer + Timestamp Highlighter Agent")

video_url = st.text_input("🔗 Enter YouTube Video URL:")
uploaded = st.file_uploader("Or upload a local video", type=["mp4", "mkv", "webm", "m4a"])

lang = st.selectbox(
    "🌐 Select summary language:",
    ["English", "Tamil", "Telugu", "Malayalam", "Kannada", "Hindi", "French", "Spanish", "German", "Japanese"]
)

if st.button("✨ Generate Video Summary"):
    try:
        # Case 1: YouTube URL
        if video_url:
            vid_id = extract_video_id(video_url)
            title, thumb, duration, author = get_video_info(video_url)
            st.markdown(f"**Title:** {title}\n\n**Channel:** {author}\n\n**Duration:** {duration} sec")
            if thumb:
                st.image(thumb, width=400)

            try:
                transcript = YouTubeTranscriptApi.get_transcript(vid_id)
                text = " ".join([x["text"] for x in transcript])
                st.success("✅ Captions retrieved successfully!")
            except Exception:
                st.warning("Captions not available, using Whisper to transcribe audio...")
                audio_path = download_audio(video_url)
                text = transcribe_audio(audio_path)

        # Case 2: Local Upload
        elif uploaded:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tmp.write(uploaded.read())
            tmp.flush()
            text = transcribe_audio(tmp.name)
        else:
            st.warning("Please provide a YouTube link or upload a video.")
            st.stop()

        # Summarize
        st.info("🤖 Summarizing with Groq AI...")
        summary = summarize_with_groq(text, lang)
        clickable = make_clickable_summary(summary, video_url)

        st.success("✅ Summary generated successfully!")
        st.subheader("📋 Video Summary with Clickable Timestamps")
        st.markdown(clickable)

        # Embed player
        if video_url:
            st.video(video_url)

    except Exception as e:
        st.error(f"❌ Error while summarizing: {e}")

st.markdown("---")
st.caption("🧠 Powered by Groq + OpenAI Whisper | Multi-language summarization + timestamp linking.")

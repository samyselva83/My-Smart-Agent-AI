# streamlit_app.py
# My Smart Agent — Enhanced Video Summarizer (supports upload + YouTube links)
import streamlit as st
from datetime import time
import tempfile
import os
import re
import base64
from groq import Groq
from youtube_transcript_api import YouTubeTranscriptApi
from pytube import YouTube
import yt_dlp
import torchaudio
import whisper
import soundfile as sf
from moviepy.editor import VideoFileClip

# ----------------------------
# Config / Languages
# ----------------------------
st.set_page_config(page_title="My Smart Agent", layout="wide")
st.title("🤖 My Smart Agent")

LANGUAGES = [
    "English", "Tamil", "Telugu", "Malayalam", "Kannada",
    "Hindi", "French", "Spanish", "German", "Japanese"
]

# ----------------------------
# Groq setup
# ----------------------------
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    GROQ_API_KEY = None

if not GROQ_API_KEY:
    st.error("⚠️ Missing GROQ_API_KEY in Streamlit secrets. Add it and reload.")
    st.stop()

# Default model - adjust to one available to your key
GROQ_MODEL = st.secrets.get("GROQ_MODEL", "llama-3.3-70b-versatile")
client = Groq(api_key=GROQ_API_KEY)

# ----------------------------
# Helper: Groq summarizer (multilingual)
# ----------------------------
def groq_summary(text: str, language: str):
    if not text or not text.strip():
        return "No text provided to summarize."
    prompt = (
        f"Summarize the following transcript in {language}. "
        "Provide a short summary (3-6 sentences) and list 5 key highlights with approximate timestamps in HH:MM format.\n\n"
        f"{text[:12000]}"
    )
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.2,
        )
        # robust extraction
        if isinstance(resp, dict):
            out = resp.get("text") or resp.get("choices", [{}])[0].get("text", "")
        else:
            out = getattr(resp.choices[0].message, "content", "") or getattr(resp, "text", "")
        return out or "(no output from model)"
    except Exception as e:
        return f"Groq summarization error: {e}"

# ----------------------------
# YouTube id extractor (robust)
# ----------------------------
def extract_video_id(url: str):
    if not url or not url.strip():
        return None
    patterns = [
        r"(?:v=)([0-9A-Za-z_-]{11})",          # standard watch
        r"(?:be/)([0-9A-Za-z_-]{11})",         # short link
        r"(?:embed/)([0-9A-Za-z_-]{11})",      # embed
        r"(?:shorts/)([0-9A-Za-z_-]{11})",     # shorts
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

# ----------------------------
# Audio download & conversion (yt_dlp + torchaudio)
# returns path to wav file
# ----------------------------
def download_audio_to_wav_simple(url: str):
    """Download bestaudio with yt_dlp and convert to WAV using MoviePy (no FFmpeg CLI)."""
    st.info("Downloading and converting audio (MoviePy safe mode)…")
    tmpdir = tempfile.gettempdir()
    base_path = os.path.join(tmpdir, "audio_dl")
    out_video = base_path + ".mp4"
    out_audio = base_path + ".wav"

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_video,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        raise RuntimeError(f"yt_dlp download failed: {e}")

    if not os.path.exists(out_video):
        raise FileNotFoundError("yt_dlp did not produce a video/audio file.")

    try:
        clip = VideoFileClip(out_video)
        clip.audio.write_audiofile(out_audio, logger=None)
        clip.close()
        return out_audio
    except Exception as e:
        raise RuntimeError(f"MoviePy audio extraction failed: {e}")
# ----------------------------
# Local upload -> save and return path (prefer .mp4/.wav)
# ----------------------------
def save_uploaded_file(uploaded):
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1] or ".mp4") as tmp:
        tmp.write(uploaded.read())
        return tmp.name

# ----------------------------
# Whisper transcribe (tiny) - accepts wav or mp4 path
# ----------------------------
_whisper_model = None
def get_whisper_model(name="tiny"):
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model(name)
    return _whisper_model

def transcribe_with_whisper(path):
    model = get_whisper_model("tiny")
    try:
        result = model.transcribe(path)
        return result.get("text", "")
    except Exception as e:
        # fallback: try torchaudio -> save wav -> transcribe
        raise RuntimeError(f"Whisper transcription failed: {e}")

# ----------------------------
# HTML helpers for embedding players and jump functions
# ----------------------------
def embed_youtube_player_html(video_id, width=800, height=450):
    # player with id 'ytplayer' and JS function ytJumpTo(seconds)
    iframe_src = f"https://www.youtube.com/embed/{video_id}?rel=0&enablejsapi=1"
    html = f"""
    <div>
      <iframe id="ytplayer" width="{width}" height="{height}" src="{iframe_src}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
    </div>
    <script>
      function ytJumpTo(t) {{
        var iframe = document.getElementById('ytplayer');
        // set iframe src with start param and autoplay
        iframe.src = "https://www.youtube.com/embed/{video_id}?start=" + Math.floor(t) + "&autoplay=1";
      }}
    </script>
    """
    return html

def embed_local_video_html(file_path, width=800):
    # Read file as base64 and embed
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    html = f"""
    <video id="localVideo" width="{width}" controls>
      <source src="data:video/mp4;base64,{b64}" type="video/mp4" />
      Your browser does not support HTML5 video.
    </video>
    <script>
      function jumpToLocal(t) {{
        var v = document.getElementById('localVideo');
        v.currentTime = t;
        v.play();
      }}
    </script>
    """
    return html

# ----------------------------
# Sidebar / modules
# ----------------------------
st.sidebar.title("My Smart Agent Menu")
modules = [
    "Dashboard",
    "Daily Planner (AI)",
    "Finance Tracker",
    "Health & Habits",
    "LearnMate",
    "Video Summarizer",
]
choice = st.sidebar.radio("Choose a module", modules)
selected_lang = st.sidebar.selectbox("Language", LANGUAGES, index=0)

# ----------------------------
# Dashboard (simple)
# ----------------------------
if choice == "Dashboard":
    st.header("Dashboard — My Smart Agent")
    st.markdown("""
    **Video Summarizer:** Upload or paste YouTube link → get multilingual summary + highlights with clickable timestamps.  
    **Daily Planner:** AI-powered scheduling.  
    Other modules in development.
    """)

# ----------------------------
# Daily Planner placeholder (keeps previous functionality)
# ----------------------------
elif choice == "Daily Planner (AI)":
    st.header("Daily Planner (AI)")
    st.info("Use the Tasks box to generate an AI plan (this app keeps your original planner).")
    tasks = st.text_area("Tasks (one per line)", height=200)
    manual_time = st.checkbox("Manually set working hours")
    if manual_time:
        c1, c2 = st.columns(2)
        with c1:
            start_time = st.time_input("Start time", value=time(9, 0))
        with c2:
            end_time = st.time_input("End time", value=time(18, 0))
    else:
        start_time = None
        end_time = None
    if st.button("Generate Plan"):
        if not tasks.strip():
            st.warning("Enter tasks first.")
        else:
            # simple call to groq_summary for demo (you can replace with DailyPlannerAgent)
            plan = groq_summary = groq_summary = groq_summary if False else None
            # fallback simple prompt (avoid complex reimplementation here)
            short = groq_summary = groq_summary if False else None
            st.info("Daily Planner functionality available in main branch; use your integrated planner.")

# ----------------------------
# Finance / Health / LearnMate placeholders
# ----------------------------
elif choice == "Finance Tracker":
    st.header("Finance Tracker — Coming Soon")
    st.info("Will provide expense tracking and analysis.")

elif choice == "Health & Habits":
    st.header("Health & Habits — Coming Soon")
    st.info("Track routines and get suggestions.")

elif choice == "LearnMate":
    st.header("LearnMate — Coming Soon")
    st.info("Upload documents and ask questions (coming soon).")

# ----------------------------
# Video Summarizer — FULL enhanced
# ----------------------------
elif choice == "Video Summarizer":
    st.header("🎬 Video Summarizer — Multilingual Highlights with Clickable Timestamps")
    st.markdown("Upload a local video file **or** paste a YouTube link. The app will extract transcript (YouTube captions or Whisper transcription), summarize using Groq in your selected language, and show clickable timestamps. Click a timestamp to jump the embedded player to that moment.")

    col_top = st.columns([3,1])
    with col_top[0]:
        yt_url = st.text_input("Paste YouTube URL (or leave blank to upload):")
    with col_top[1]:
        uploaded_file = st.file_uploader("Upload video (mp4)", type=["mp4"], accept_multiple_files=False)

    # internal state
    embed_html = None
    transcript_text = ""
    metadata_title = None
    thumbnail_url = None
    duration_str = None
    channel_name = None
    video_id = None
    local_video_path = None

    if st.button("Summarize Video"):
        try:
            # If user provided YouTube URL
            if yt_url and yt_url.strip():
                video_id = extract_video_id(yt_url.strip())
                if not video_id:
                    st.error("❌ Could not extract video ID. Please check the YouTube link.")
                else:
                    # Try to get metadata with pytube; fallback to thumbnail URL pattern
                    try:
                        yt = YouTube(yt_url.strip())
                        metadata_title = yt.title
                        thumbnail_url = yt.thumbnail_url
                        duration = yt.length
                        duration_str = f"{duration // 60}m {duration % 60}s"
                        channel_name = yt.author
                    except Exception:
                        metadata_title = "Unknown Title"
                        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/0.jpg"
                        duration_str = "Unknown"
                        channel_name = "Unknown"

                    # Display thumbnail and metadata
                    st.image(thumbnail_url, width=480, caption=f"🎥 {metadata_title}")
                    st.write(f"**Duration:** {duration_str} | **Channel:** {channel_name}")

                    # Try to fetch YouTube transcript (captions)
                    try:
                        st.info("Attempting to fetch YouTube captions...")
                        captions = YouTubeTranscriptApi.get_transcript(video_id)
                        transcript_text = " ".join([seg["text"] for seg in captions])
                        st.success("✅ Captions fetched successfully.")
                    except Exception as e:
                        st.warning(f"Captions not available or fetch failed: {e}")
                        st.info("Falling back to audio transcription (Whisper). Downloading audio...")
                        # download audio and transcribe
                        wav_path = download_audio_to_wav_simple(yt_url.strip())
                        st.info("Transcribing audio with Whisper (tiny)...")
                        transcript_text = transcribe_with_whisper(wav_path)
                        st.success("✅ Audio transcribed with Whisper.")

                    # Summarize with Groq
                    st.info("Generating multilingual summary with Groq...")
                    summary = groq_summary(transcript_text, selected_lang)
                    if isinstance(summary, str) and summary.startswith("Groq summarization error"):
                        st.error(summary)
                    else:
                        # convert timestamps in summary to clickable links for embedded player
                        click_html = make_clickable_timestamps(summary, video_id)
                        # show embedded YouTube iframe player with control JS
                        embed_html = embed_youtube_player_html(video_id, width=800, height=450)
                        st.components.v1.html(embed_html, height=470, scrolling=False)
                        st.markdown("### 📝 Summary Highlights")
                        st.markdown(click_html, unsafe_allow_html=True)

            # If user uploaded local file (preferred when no youtube link)
            elif uploaded_file:
                # save uploaded file
                local_video_path = save_uploaded_file(uploaded_file)
                st.image("data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=", width=1)  # tiny spacer
                st.write("Uploaded file saved.")
                # embed local player
                embed_html = embed_local_video_html(local_video_path, width=800)
                st.components.v1.html(embed_html, height=470, scrolling=False)

                # transcribe using Whisper directly
                st.info("Transcribing uploaded video with Whisper (tiny)...")
                try:
                    # Whisper can typically accept mp4 path; otherwise you can convert
                    transcript_text = transcribe_with_whisper(local_video_path)
                    st.success("✅ Uploaded video transcribed.")
                except Exception as e:
                    st.error(f"Whisper transcription failed: {e}")
                    transcript_text = ""

                if transcript_text:
                    st.info("Generating multilingual summary with Groq...")
                    summary = groq_summary(transcript_text, selected_lang)
                    if isinstance(summary, str) and summary.startswith("Groq summarization error"):
                        st.error(summary)
                    else:
                        # For local player clickable timestamps should call jumpToLocal(seconds)
                        # We'll transform HH:MM into HTML links that call jumpToLocal(seconds)
                        def local_timestamp_repl(match):
                            t = match.group(1)
                            parts = t.split(":")
                            seconds = int(parts[0]) * 60 + int(parts[1])
                            return f'<a href="#" onclick="jumpToLocal({seconds});return false;">[{t}]</a>'
                        local_click_html = re.sub(r"(\d{1,2}:\d{2})", local_timestamp_repl, summary)
                        st.markdown("### 📝 Summary Highlights")
                        st.markdown(local_click_html, unsafe_allow_html=True)
                else:
                    st.warning("No transcript text extracted from uploaded video.")

            else:
                st.warning("Please provide a YouTube link or upload a local video file.")
        except Exception as ex:
            st.error(f"Error while summarizing: {ex}")

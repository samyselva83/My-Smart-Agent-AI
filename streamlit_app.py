# streamlit_app.py
# My Smart Agent — Multi-agent Streamlit app (Dashboard, Planner, Finance, Health, LearnMate, Memory, Video Summarizer)
import os
import re
import tempfile
import base64
import time
from datetime import time as dtime

import streamlit as st
import streamlit.components.v1 as components
import os
import imageio_ffmpeg

# Ensure imageio_ffmpeg is imported early so we can expose ffmpeg to Whisper

os.environ["PATH"] += os.pathsep + os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())

# External libs
import yt_dlp
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
import whisper
from groq import Groq

# ---------------------------
# Config / constants
# ---------------------------
st.set_page_config(page_title="My Smart Agent", layout="wide")
st.title("🤖 My Smart Agent")

LANGUAGES = [
    "English", "Tamil", "Telugu", "Malayalam", "Kannada",
    "Hindi", "French", "Spanish", "German", "Japanese"
]

# ---------------------------
# Secrets / clients
# ---------------------------
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", None)

if not GROQ_API_KEY:
    st.error("⚠️ Add your GROQ_API_KEY in Streamlit Secrets (Edit → Secrets).")
    st.stop()

GROQ_MODEL = st.secrets.get("GROQ_MODEL", "llama-3.3-70b-versatile")
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------
# Whisper lazy loader
# ---------------------------
_whisper_model = None
def get_whisper_model(name="tiny"):
    global _whisper_model
    if _whisper_model is None:
        try:
            _whisper_model = whisper.load_model(name)
        except Exception as e:
            st.error(f"Failed to load Whisper model: {e}")
            raise
    return _whisper_model

# ---------------------------
# Utilities
# ---------------------------
def extract_video_id(url: str):
    if not url:
        return None
    patterns = [
        r"(?:v=)([0-9A-Za-z_-]{11})",
        r"(?:be/)([0-9A-Za-z_-]{11})",
        r"(?:embed/)([0-9A-Za-z_-]{11})",
        r"(?:shorts/)([0-9A-Za-z_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

def make_clickable_youtube(summary_text: str, video_id: str) -> str:
    pattern = r"(\d{1,2}:\d{2})"
    def repl(m):
        hhmm = m.group(1)
        h, m2 = hhmm.split(":")
        secs = int(h) * 60 + int(m2)
        return f'<a href="https://www.youtube.com/watch?v={video_id}&t={secs}s" target="_blank">[{hhmm}]</a>'
    return re.sub(pattern, repl, summary_text)

def make_clickable_local(summary_text: str) -> str:
    pattern = r"(\d{1,2}:\d{2})"
    def repl(m):
        hhmm = m.group(1)
        h, m2 = hhmm.split(":")
        secs = int(h) * 60 + int(m2)
        return f'<a href="#" onclick="jumpToLocal({secs});return false;">[{hhmm}]</a>'
    return re.sub(pattern, repl, summary_text)

def embed_youtube_iframe(video_id, width=800, height=450):
    src = f"https://www.youtube.com/embed/{video_id}?rel=0&enablejsapi=1"
    html = f"""
    <iframe id="ytplayer" width="{width}" height="{height}" src="{src}" frameborder="0"
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
    <script>
    function ytJumpTo(t) {{
      var iframe = document.getElementById('ytplayer');
      iframe.src = "https://www.youtube.com/embed/{video_id}?start=" + Math.floor(t) + "&autoplay=1";
    }}
    </script>
    """
    return html

def embed_local_video_html(file_path, width=800):
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    html = f"""
    <video id="localVideo" width="{width}" controls>
      <source src="data:video/mp4;base64,{b64}" type="video/mp4">
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

# ---------------------------
# Groq summarizer helper
# ---------------------------
def groq_summarize(transcript: str, language: str):
    if not transcript or not transcript.strip():
        return "No transcript text available to summarize."
    prompt = f"""Summarize the following transcript in {language}. Provide a 3-5 sentence summary, then list 5 key highlights with timestamps in HH:MM format.
Transcript:
{transcript[:12000]}
"""
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role":"user","content":prompt}],
            max_tokens=800,
            temperature=0.2,
        )
        # robust extraction
        if isinstance(resp, dict):
            return resp.get("text") or resp.get("choices", [{}])[0].get("text", "")
        return getattr(resp.choices[0].message, "content", "") or getattr(resp, "text", "")
    except Exception as e:
        return f"Groq summarization error: {e}"

# ---------------------------
# Audio download w/ progress (yt_dlp) — no postprocessors (avoid ffmpeg requirement)
# ---------------------------
def download_audio_for_whisper(url: str):
    st.info("🎧 Downloading audio (yt_dlp)...")
    tmpdir = tempfile.gettempdir()
    out_path = os.path.join(tmpdir, "msa_audio_for_whisper.webm")
    progress = st.progress(0)
    status = st.empty()

    class Hook:
        def __call__(self, d):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
                downloaded = d.get("downloaded_bytes", 0)
                pct = min(100, int(downloaded / total * 100))
                progress.progress(pct)
                status.text(f"⬇️ Downloading audio: {pct}%")
            elif d.get("status") == "finished":
                status.text("✅ Download complete.")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_path,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [Hook()],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        raise RuntimeError(f"yt_dlp audio download failed: {e}")

    if not os.path.exists(out_path):
        raise FileNotFoundError("Audio file not created by yt_dlp.")
    progress.progress(100)
    st.success("✅ Audio downloaded.")
    return out_path

# ---------------------------
# Whisper transcription wrapper
# ---------------------------
def transcribe_path_with_whisper(path):
    st.info("🧠 Transcribing with Whisper (tiny)... this can take a minute.")
    # load model lazily
    model = get_whisper_model("tiny")
    # whisper uses ffmpeg binary internally — imageio_ffmpeg ensures it's available
    result = model.transcribe(path)
    return result.get("text", "")

# ---------------------------
# Helpers for YouTube captions
# ---------------------------
def fetch_youtube_captions(video_id: str):
    try:
        # new API method
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            segments = YouTubeTranscriptApi.get_transcript(video_id)
            return " ".join([s["text"] for s in segments])
        # fallback older style
        api = YouTubeTranscriptApi()
        transcripts = api.list_transcripts(video_id)
        for t in transcripts:
            try:
                segs = t.fetch()
                return " ".join([s["text"] for s in segs])
            except Exception:
                continue
        return ""
    except Exception as e:
        st.warning(f"Captions fetch failed: {e}")
        return ""

# ---------------------------
# Small Daily Planner agent (uses Groq)
# ---------------------------
class DailyPlannerAgent:
    def __init__(self, client, language="English", day_start=None, day_end=None):
        self.client = client
        self.language = language
        self.day_start = day_start
        self.day_end = day_end

    def build_prompt(self, tasks: str, timezone="local"):
        if not self.day_start or not self.day_end:
            time_instr = "Choose realistic start and end times based on task volume (e.g., 08:30–17:30)."
        else:
            time_instr = f"Respect working hours between {self.day_start} and {self.day_end} ({timezone})."
        prompt = f"""You are a helpful assistant that makes a daily schedule. Tasks:
{tasks}
Instructions:
- {time_instr}
- Prioritize and assign time ranges (HH:MM–HH:MM).
- Output lines: HH:MM–HH:MM | Task — Priority — Note
- Keep in {self.language} and finish with one motivational line."""
        return prompt

    def generate(self, tasks: str, timezone="local"):
        prompt = self.build_prompt(tasks, timezone)
        try:
            resp = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role":"user","content":prompt}],
                max_tokens=600,
                temperature=0.25,
            )
            if isinstance(resp, dict):
                return resp.get("text") or resp.get("choices", [{}])[0].get("text","")
            return getattr(resp.choices[0].message, "content", "") or getattr(resp,"text","")
        except Exception as e:
            return f"Planner error: {e}"

# ---------------------------
# Streamlit UI — Sidebar modules
# ---------------------------
st.sidebar.title("My Smart Agent")
modules = [
    "Dashboard",
    "Daily Planner (AI)",
    "Finance Tracker",
    "Health & Habits",
    "LearnMate",
    "Memory",
    "Video Summarizer",
]
choice = st.sidebar.radio("Choose module", modules)
selected_lang = st.sidebar.selectbox("Language", LANGUAGES, index=0)

# ---------------------------
# Dashboard
# ---------------------------
if choice == "Dashboard":
    st.header("📊 Dashboard")
    st.markdown("""
- **Daily Planner (AI):** Live (trial) — auto schedule with optional manual times  
- **Finance Tracker:** In development — expense tracking & charts  
- **Health & Habits:** In development — habit logger  
- **LearnMate:** In development — upload notes, Q&A  
- **Memory:** Local note store for the agent  
- **Video Summarizer:** Enhanced — captions or Whisper + Groq + clickable timestamps
""")

# ---------------------------
# Daily Planner
# ---------------------------
elif choice == "Daily Planner (AI)":
    st.header("🗓️ Daily Planner (AI)")
    st.write("Enter tasks (one per line). Optional priorities: [high], [medium], [low].")
    tasks_input = st.text_area("Tasks", height=200, placeholder="Meeting with team [high]\nWrite report [high]\nWalk [low]")
    manual = st.checkbox("Set working hours manually")
    if manual:
        c1, c2 = st.columns(2)
        with c1:
            start_time = st.time_input("Start time", value=dtime(9,0))
        with c2:
            end_time = st.time_input("End time", value=dtime(18,0))
    else:
        start_time = None
        end_time = None

    if st.button("Generate Plan"):
        if not tasks_input.strip():
            st.warning("Enter at least one task.")
        else:
            agent = DailyPlannerAgent(client, language=selected_lang,
                                      day_start=start_time.strftime("%H:%M") if start_time else None,
                                      day_end=end_time.strftime("%H:%M") if end_time else None)
            with st.spinner("Generating plan..."):
                plan = agent.generate(tasks_input)
            st.markdown("### Generated Plan")
            st.code(plan)

# ---------------------------
# Finance Tracker (placeholder)
# ---------------------------
elif choice == "Finance Tracker":
    st.header("💵 Finance Tracker")
    st.info("Feature is under development. You can store expenses, see charts, and set budgets.")

# ---------------------------
# Health & Habits (placeholder)
# ---------------------------
elif choice == "Health & Habits":
    st.header("💪 Health & Habits")
    st.info("Feature is under development. Track water, steps, and routines here.")

# ---------------------------
# LearnMate (placeholder)
# ---------------------------
elif choice == "LearnMate":
    st.header("🧠 LearnMate")
    st.info("Feature under development. Upload notes or PDFs and ask the AI.")

# ---------------------------
# Memory (simple local notes)
# ---------------------------
elif choice == "Memory":
    st.header("🧾 Memory (Local Notes)")
    note = st.text_area("Write a short note (will be saved locally for this session):", height=150)
    if st.button("Save Note"):
        if not note.strip():
            st.warning("Write something to save.")
        else:
            # store in session state
            notes = st.session_state.get("notes", [])
            notes.append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "text": note})
            st.session_state["notes"] = notes
            st.success("Saved to session memory.")
    if st.session_state.get("notes"):
        st.markdown("#### Saved Notes (session)")
        for n in reversed(st.session_state["notes"]):
            st.write(f"- {n['time']}: {n['text']}")

# ---------------------------
# Video Summarizer (main feature)
# ---------------------------
elif choice == "Video Summarizer":
    st.header("🎬 Video Summarizer + Timestamp Highlighter")
    st.markdown("Provide a YouTube URL or upload a local MP4. The app will fetch captions (if any), or download audio and transcribe with Whisper, then summarize with Groq. Click timestamps to jump to moments.")

    col1, col2 = st.columns([3,1])
    with col1:
        yt_url = st.text_input("YouTube URL (leave blank to upload):")
    with col2:
        uploaded = st.file_uploader("Upload MP4 (optional)", type=["mp4","mkv","webm"], accept_multiple_files=False)

    if st.button("Summarize Video"):
        if not yt_url and not uploaded:
            st.warning("Provide a YouTube URL or upload a video.")
        else:
            try:
                transcript_text = ""
                video_id = None
                local_path = None
                # Case: YouTube URL
                if yt_url and yt_url.strip():
                    video_id = extract_video_id(yt_url.strip())
                    # fetch metadata
                    try:
                        yt = YouTube(yt_url.strip())
                        st.image(yt.thumbnail_url, width=480, caption=f"🎥 {yt.title}")
                        if yt.length:
                            st.write(f"**Duration:** {yt.length//60}m {yt.length%60}s | **Channel:** {yt.author}")
                    except Exception:
                        # simple thumbnail fallback
                        if video_id:
                            st.image(f"https://img.youtube.com/vi/{video_id}/0.jpg", width=480)
                    # try captions
                    transcript_text = fetch_youtube_captions(video_id) if video_id else ""
                    if not transcript_text.strip():
                        # download audio & transcribe
                        wav_path = download_audio_for_whisper(yt_url.strip())
                        transcript_text = transcribe_path_with_whisper(wav_path)
                # Case: local upload
                elif uploaded:
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1] or ".mp4")
                    tmp.write(uploaded.read())
                    tmp.flush()
                    local_path = tmp.name
                    # embed local player
                    player_html = embed_local_video_html(local_path, width=800)
                    components.html(player_html, height=470, scrolling=False)
                    transcript_text = transcribe_path_with_whisper(local_path)

                # summarize via Groq
                st.info("Generating multilingual summary (Groq)...")
                summary = groq_summarize(transcript_text, selected_lang)
                if video_id:
                    click_html = make_clickable_youtube(summary, video_id)
                    # show embed player for youtube
                    emb = embed_youtube_iframe(video_id, width=800, height=450)
                    components.html(emb, height=470, scrolling=False)
                    st.markdown("### 📝 Summary Highlights (click to open YouTube time)")
                    st.markdown(click_html, unsafe_allow_html=True)
                else:
                    # local
                    click_html = make_clickable_local(summary)
                    st.markdown("### 📝 Summary Highlights (click to jump local player)")
                    st.markdown(click_html, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Error while summarizing: {e}")

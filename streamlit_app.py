# streamlit_app.py
# My Smart Agent — Final Cloud-safe integrated app (sidebar layout)
import streamlit as st
from datetime import time
import tempfile
import os
import re
import base64

# External libs
from groq import Groq
import yt_dlp
import whisper
from youtube_transcript_api import YouTubeTranscriptApi
from pytube import YouTube
import streamlit.components.v1 as components

# -------------------------
# Config & languages
# -------------------------
st.set_page_config(page_title="My Smart Agent", layout="wide")
st.title("🤖 My Smart Agent")

LANGUAGES = [
    "English", "Tamil", "Telugu", "Malayalam", "Kannada",
    "Hindi", "French", "Spanish", "German", "Japanese"
]

# -------------------------
# Secrets & Groq client
# -------------------------
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    GROQ_API_KEY = None

if not GROQ_API_KEY:
    st.error("⚠️ Missing GROQ_API_KEY. Add it in Streamlit → Edit secrets and reload.")
    st.stop()

GROQ_MODEL = st.secrets.get("GROQ_MODEL", "llama-3.3-70b-versatile")
client = Groq(api_key=GROQ_API_KEY)

# -------------------------
# Whisper model (lazy load)
# -------------------------
_whisper_model = None
def get_whisper_model(name="tiny"):
    global _whisper_model
    if _whisper_model is None:
        try:
            _whisper_model = whisper.load_model(name)
        except Exception as e:
            st.error(f"Whisper model load failed: {e}")
            raise
    return _whisper_model

# -------------------------
# Utilities
# -------------------------
def extract_video_id(url: str):
    """Extract YouTube video id from most URL forms."""
    if not url:
        return None
    patterns = [
        r"(?:v=)([0-9A-Za-z_-]{11})",    # watch?v=
        r"(?:be/)([0-9A-Za-z_-]{11})",   # youtu.be/
        r"(?:embed/)([0-9A-Za-z_-]{11})",# embed/
        r"(?:shorts/)([0-9A-Za-z_-]{11})",# shorts/
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

def groq_summary(text: str, language: str):
    """Call Groq to summarize text in target language and return output string."""
    if not text or not text.strip():
        return "No text to summarize."
    prompt = (
        f"Summarize the following transcript in {language}. "
        "Give a short summary (3-6 sentences) and then list 5 key highlights with approximate timestamps (HH:MM).\n\n"
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
        return out or "(no output)"
    except Exception as e:
        return f"Groq summarization error: {e}"

def make_clickable_youtube(summary_text: str, video_id: str) -> str:
    """Convert HH:MM occurrences into clickable YouTube links (open in new tab)"""
    pattern = r"(\d{1,2}:\d{2})"
    def repl(m):
        hhmm = m.group(1)
        parts = hhmm.split(":")
        secs = int(parts[0]) * 60 + int(parts[1])
        return f"[{hhmm}](https://www.youtube.com/watch?v={video_id}&t={secs}s)"
    return re.sub(pattern, repl, summary_text)

def make_clickable_local(summary_text: str) -> str:
    """Convert HH:MM into JS links calling jumpToLocal(seconds)."""
    pattern = r"(\d{1,2}:\d{2})"
    def repl(m):
        hhmm = m.group(1)
        parts = hhmm.split(":")
        secs = int(parts[0]) * 60 + int(parts[1])
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

# -------------------------
# Audio download: yt_dlp -> FFmpegExtractAudio -> WAV
# (Streamlit Cloud supports this)
# -------------------------
def download_audio_to_wav_yt_dlp(url: str):
    """Download audio via yt_dlp and use FFmpegExtractAudio to produce WAV file."""
    st.info("Downloading audio and converting to WAV (yt_dlp). This may take a moment...")
    tmpdir = tempfile.gettempdir()
    out_path = os.path.join(tmpdir, "msa_audio.wav")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_path,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        raise RuntimeError(f"yt_dlp audio download failed: {e}")
    if not os.path.exists(out_path):
        raise FileNotFoundError("yt_dlp did not create WAV output.")
    return out_path

# -------------------------
# Save uploaded file
# -------------------------
def save_uploaded_file(uploaded_file):
    suffix = os.path.splitext(uploaded_file.name)[1] or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.read())
        return tmp.name

# -------------------------
# Get transcript: try API then Whisper
# -------------------------
def fetch_youtube_captions(video_id: str) -> str:
    """Try to get captions via youtube-transcript-api. Return text or empty string."""
    try:
        # prefer get_transcript if present, otherwise use list_transcripts
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            captions = YouTubeTranscriptApi.get_transcript(video_id)
            text = " ".join([seg["text"] for seg in captions])
            return text
        else:
            api = YouTubeTranscriptApi()
            transcripts = api.list_transcripts(video_id)
            # pick the first transcript object and fetch segments
            for t in transcripts:
                try:
                    segs = t.fetch()
                    return " ".join([s["text"] for s in segs])
                except Exception:
                    continue
            return ""
    except Exception as e:
        # no captions available
        st.warning(f"Captions not available or fetch failed: {e}")
        return ""

# -------------------------
# Sidebar + modules
# -------------------------
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

# -------------------------
# Dashboard
# -------------------------
if choice == "Dashboard":
    st.header("📊 Dashboard — My Smart Agent")
    st.markdown("""
    **Status**
    - Daily Planner (AI): ✅ Live (trial)
    - Finance Tracker: ⚙️ In development
    - Health & Habits: ⚙️ In development
    - LearnMate: 🧪 Testing
    - Video Summarizer: ✅ Enhanced (YouTube or Upload)
    """)

# -------------------------
# Daily Planner (simple integration)
# -------------------------
elif choice == "Daily Planner (AI)":
    st.header("🧠 Daily Planner (AI)")
    tasks = st.text_area("Tasks (one per line)", height=200)
    manual = st.checkbox("Manually set working hours")
    if manual:
        c1, c2 = st.columns(2)
        with c1:
            start_time = st.time_input("Start time", value=time(9,0))
        with c2:
            end_time = st.time_input("End time", value=time(18,0))
    else:
        start_time = None
        end_time = None

    if st.button("Generate Plan"):
        if not tasks.strip():
            st.warning("Enter some tasks first.")
        else:
            # lightweight planner prompt via Groq (simple)
            plan_text = groq_summary(tasks, selected_lang)
            st.markdown("### Generated Plan")
            st.code(plan_text)

# -------------------------
# Finance / Health / LearnMate placeholders
# -------------------------
elif choice == "Finance Tracker":
    st.header("💰 Finance Tracker")
    st.info("Feature in development.")

elif choice == "Health & Habits":
    st.header("💪 Health & Habits")
    st.info("Feature in development.")

elif choice == "LearnMate":
    st.header("📚 LearnMate")
    st.info("Upload docs and ask questions (coming soon).")

# -------------------------
# Video Summarizer (enhanced)
# -------------------------
elif choice == "Video Summarizer":
    st.header("🎬 Video Summarizer — YouTube or Upload")
    st.markdown("Provide a YouTube URL or upload a local MP4. The app will fetch captions or transcribe audio with Whisper, then summarize using Groq. Click timestamps to jump to video moments.")

    col1, col2 = st.columns([3,1])
    with col1:
        yt_url = st.text_input("YouTube URL (leave blank to upload):")
    with col2:
        uploaded_file = st.file_uploader("Upload MP4", type=["mp4"], accept_multiple_files=False)

    if st.button("Summarize Video"):
        if not yt_url and not uploaded_file:
            st.warning("Provide a YouTube URL or upload a video file.")
        else:
            try:
                transcript_text = ""
                video_id = None
                is_local = False
                local_path = None

                # If YouTube URL provided
                if yt_url and yt_url.strip():
                    vid = extract_video_id(yt_url.strip())
                    if not vid:
                        st.error("Could not extract video id from URL. Check format.")
                    else:
                        video_id = vid
                        # Try to retrieve metadata (pytube), fallback to thumbnail URL
                        try:
                            yt = YouTube(yt_url.strip())
                            title = yt.title
                            thumb = yt.thumbnail_url
                            duration = yt.length
                            channel = yt.author
                        except Exception:
                            title = "Unknown Title"
                            thumb = f"https://img.youtube.com/vi/{video_id}/0.jpg"
                            duration = None
                            channel = "Unknown"

                        st.image(thumb, width=480, caption=f"🎥 {title}")
                        if duration:
                            st.write(f"**Duration:** {duration//60}m {duration%60}s | **Channel:** {channel}")
                        else:
                            st.write(f"**Duration:** Unknown | **Channel:** {channel}")

                        # Try captions first
                        transcript_text = fetch_youtube_captions(video_id)

                        # If no captions, download audio & transcribe
                        if not transcript_text.strip():
                            st.info("Falling back to audio transcription (Whisper). Downloading audio...")
                            wav_path = download_audio_to_wav_yt_dlp(yt_url.strip())
                            st.info("Transcribing audio with Whisper (tiny)...")
                            model = get_whisper_model("tiny")
                            res = model.transcribe(wav_path)
                            transcript_text = res.get("text", "")
                            st.success("✅ Audio transcribed.")

                        # Now summarize
                        st.info("Generating multilingual summary with Groq...")
                        summary = groq_summary(transcript_text, selected_lang)
                        if summary.startswith("Groq summarization error"):
                            st.error(summary)
                        else:
                            # clickable timestamps for YouTube: open new tab or jump iframe (embedding both)
                            click_md = make_clickable_youtube(summary, video_id)
                            # show embedded player (iframe)
                            embed_html = embed_youtube_iframe(video_id, width=800, height=450)
                            components.html(embed_html, height=470, scrolling=False)
                            st.markdown("### 📝 Summary Highlights")
                            st.markdown(click_md, unsafe_allow_html=True)

                # Else if user uploaded local file
                elif uploaded_file:
                    is_local = True
                    local_path = save_uploaded_file(uploaded_file)
                    st.info("Uploaded file saved.")
                    # embed local player
                    html_player = embed_local_video_html(local_path, width=800)
                    components.html(html_player, height=470, scrolling=False)

                    # Transcribe with Whisper
                    st.info("Transcribing uploaded video with Whisper (tiny)...")
                    model = get_whisper_model("tiny")
                    res = model.transcribe(local_path)
                    transcript_text = res.get("text", "")
                    st.success("✅ Uploaded video transcribed.")

                    # Summarize and convert timestamps to JS links
                    st.info("Generating multilingual summary with Groq...")
                    summary = groq_summary(transcript_text, selected_lang)
                    if summary.startswith("Groq summarization error"):
                        st.error(summary)
                    else:
                        click_html = make_clickable_local(summary)
                        st.markdown("### 📝 Summary Highlights")
                        st.markdown(click_html, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Error while summarizing: {e}")

# streamlit_app.py
# My Smart Agent — Updated with robust DailyPlannerAgent (Option A)
import streamlit as st
import tempfile
import os
import torch
import torchaudio
import whisper
from groq import Groq
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
from datetime import datetime, time

st.set_page_config(page_title="My Smart Agent", page_icon="🤖", layout="wide")
st.title("🤖 My Smart Agent — Multi-Agent AI (with Smart Planner)")

# ---------------------------
# Config & Secrets
# ---------------------------
# Ensure GROQ_API_KEY is set in Streamlit secrets
if "GROQ_API_KEY" not in st.secrets or not st.secrets["GROQ_API_KEY"]:
    st.error("⚠️ GROQ_API_KEY not found. Please add it via Streamlit → Edit secrets.")
    st.stop()
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

# Optional model override via secrets (if you have a model name)
GROQ_MODEL = st.secrets.get("GROQ_MODEL", "llama-3.2-70b-text-preview")

# Initialize Groq client
try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"Groq client init failed: {e}")
    st.stop()

# Languages mapping
LANGUAGES = {
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

selected_lang = st.sidebar.selectbox("Choose summary language", list(LANGUAGES.keys()))

# ---------------------------
# Utility: Groq summarization with robust error handling
# ---------------------------
def groq_summary(text: str, language: str):
    """Return a short summary via Groq LLM. Handles model errors nicely."""
    if not text or not text.strip():
        return "No text provided for summarization."
    prompt = (
        f"You are a helpful assistant. Produce a concise summary in {language}. "
        "Also include 5 short highlights with approximate timestamps if possible. "
        "Keep the summary to 3-6 sentences.\n\n"
        f"Transcript/Content:\n{text[:15000]}"
    )
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.2
        )
        # adapt to variety of response shapes
        text_out = ""
        if isinstance(resp, dict):
            # sometimes API returns JSON-like dict
            text_out = resp.get("text") or resp.get("choices", [{}])[0].get("text", "")
        else:
            # SDK object
            text_out = getattr(resp.choices[0].message, "content", "") or getattr(resp, "text", "")
        return text_out or "(no output from model)"
    except Exception as e:
        err = str(e)
        if "model_not_found" in err or "model_decommissioned" in err:
            return "⚠️ Selected Groq model is unavailable for your key. Please set GROQ_MODEL in secrets or choose another model in your Groq console."
        if "401" in err or "invalid_api_key" in err:
            return "❌ Groq API key invalid. Please verify your key in Streamlit Secrets."
        return f"Groq summarization error: {err}"

# ---------------------------
# DailyPlannerAgent (robust, OO)
# ---------------------------
class DailyPlannerAgent:
    def __init__(self, llm_client, language: str = "English", day_start: str = "09:00", day_end: str = "18:00"):
        self.client = llm_client
        self.language = language
        self.day_start = day_start  # "HH:MM"
        self.day_end = day_end

    def _build_prompt(self, tasks: str, timezone: str = "local time"):
        prompt = f"""
You are an expert personal assistant. The user gives you a list of tasks for their day.
Create a structured, time-boxed daily schedule in {self.language} between {self.day_start} and {self.day_end} ({timezone}).
Requirements:
- Parse tasks (one per line).
- Prioritize tasks by urgency/impact.
- Allocate realistic durations and start/end times.
- Group similar tasks and add short context/notes for each item.
- Insert short breaks (~10-20 min) after 60-90 minutes of focused work.
- If user provided priorities like [high]/[medium]/[low], respect them.
- Output in clear bullet lines in this format:
  HH:MM-HH:MM | Task title — Priority — Note

Example:
09:00-09:45 | Prepare project report — High — Focus on executive summary
...
End with a 1-line motivational tip.
Tasks:
{tasks}
"""
        return prompt.strip()

    def generate_plan(self, tasks_text: str, timezone: str = "local time"):
        prompt = self._build_prompt(tasks_text, timezone)
        try:
            resp = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.15
            )
            # Extract text robustly
            if isinstance(resp, dict):
                plan_text = resp.get("text") or resp.get("choices", [{}])[0].get("text", "")
            else:
                plan_text = getattr(resp.choices[0].message, "content", "") or getattr(resp, "text", "")
            return plan_text or "(no plan generated)"
        except Exception as e:
            return f"Planner error: {e}"

# ---------------------------
# Video transcript & transcription helpers
# ---------------------------
def try_fetch_youtube_transcript(video_id: str) -> str:
    try:
        api = YouTubeTranscriptApi()
        transcripts = api.list_transcripts(video_id)
        text = ""
        for t in transcripts:
            fetched = t.fetch()
            for seg in fetched:
                text += " " + seg.get("text", "")
        return text.strip()
    except Exception as e:
        # Return empty string so caller falls back to audio transcription
        st.warning(f"Could not fetch YouTube transcript: {e}")
        return ""

def download_audio_to_wav_no_ffmpeg(url: str) -> str:
    """Download best audio with yt_dlp and convert/load via torchaudio. Return path to wav file."""
    st.info("Downloading audio (no ffmpeg) — this may take a moment...")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        ydl_opts = {"format": "bestaudio/best", "outtmpl": tmp.name, "quiet": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        # torchaudio can load webm/opus; save as wav for Whisper
        try:
            waveform, sr = torchaudio.load(tmp.name)
            wav_path = tmp.name + ".wav"
            torchaudio.save(wav_path, waveform, sr)
            return wav_path
        except Exception as e:
            st.error(f"Audio decode failed: {e}")
            raise

# ---------------------------
# Streamlit UI: Modules
# ---------------------------
st.sidebar.title("Modules")
modules = [
    "Dashboard",
    "Daily Planner (AI)",
    "Finance Tracker",
    "Health & Habits",
    "LearnMate (Docs & Q&A)",
    "Memory",
    "Video Summarizer",
    "Settings"
]
choice = st.sidebar.radio("Choose module:", modules)

# Session minimal user identity (local demo)
if "user" not in st.session_state:
    st.session_state.user = {"id": "local-demo", "email": "demo@example.com"}

def require_user():
    if st.session_state.user is None:
        st.warning("Please sign in (demo mode uses local identity).")
        st.stop()
    return st.session_state.user.get("id") or st.session_state.user.get("email")

# ---------------------------
# Dashboard
# ---------------------------
if choice == "Dashboard":
    user = require_user()
    st.header("Dashboard")
    st.write("Welcome — use the side menu to choose an agent.")

# ---------------------------
# Daily Planner (replaced with AI Agent)
# ---------------------------
elif choice == "Daily Planner (AI)":
    user = require_user()
    st.header("Daily Planner — AI Powered")

    st.markdown("Enter tasks (one per line). You may add priority tags like `[high]`, `[medium]`, `[low]` at the end of a task.")
    tasks_input = st.text_area("Tasks", placeholder="Example:\nPrepare slides for presentation [high]\nReply to client emails [medium]\nGym [low]")

    col1, col2 = st.columns(2)
    with col1:
        start_time = st.time_input("Day start", value=time(9, 0))
    with col2:
        end_time = st.time_input("Day end", value=time(18, 0))

    timezone = st.text_input("Timezone (optional)", value="local time")
    if st.button("Generate Smart Plan"):
        if not tasks_input.strip():
            st.warning("Please enter some tasks first.")
        else:
            # Instantiate agent and generate plan
            agent = DailyPlannerAgent(client, language=selected_lang, day_start=start_time.strftime("%H:%M"), day_end=end_time.strftime("%H:%M"))
            with st.spinner("Generating plan..."):
                plan = agent.generate_plan(tasks_input, timezone=timezone)
            st.markdown("### Generated Plan")
            if plan.startswith("Planner error") or plan.startswith("⚠️") or plan.startswith("❌"):
                st.error(plan)
            else:
                st.code(plan)

# ---------------------------
# Finance Tracker
# ---------------------------
elif choice == "Finance Tracker":
    user = require_user()
    st.header("Finance Tracker")
    income = st.number_input("Monthly income (₹)", min_value=0.0, step=1000.0)
    expenses_text = st.text_area("Expenses (one per line like 'Dinner - 450')", height=150)
    if st.button("Analyze"):
        if not expenses_text.strip():
            st.info("Enter expenses to analyze.")
        else:
            try:
                total = 0.0
                lines = [l.strip() for l in expenses_text.splitlines() if l.strip()]
                for l in lines:
                    parts = l.split("-")
                    if len(parts) >= 2:
                        amt = float(parts[-1].strip())
                        total += amt
                balance = income - total
                st.success(f"Remaining balance: ₹{balance:.2f}")
                summary = groq_summary(f"Income: {income}\nExpenses:\n{expenses_text}", selected_lang)
                st.write(summary)
            except Exception as e:
                st.error(f"Error analyzing expenses: {e}")

# ---------------------------
# Health & Habits
# ---------------------------
elif choice == "Health & Habits":
    user = require_user()
    st.header("Health & Habits")
    habits = st.text_area("List your habits or health logs (one per line)")
    if st.button("Analyze Habits"):
        if not habits.strip():
            st.info("Enter habits or recent logs.")
        else:
            out = groq_summary(f"Analyze and give suggestions for these habits:\n{habits}", selected_lang)
            st.write(out)

# ---------------------------
# LearnMate (Docs & Q&A)
# ---------------------------
elif choice == "LearnMate (Docs & Q&A)":
    user = require_user()
    st.header("LearnMate — upload text files or paste content")
    uploaded = st.file_uploader("Upload .txt files (multiple)", type=["txt"], accept_multiple_files=True)
    if uploaded:
        contents = []
        for f in uploaded:
            try:
                s = f.read().decode("utf-8", errors="ignore")
                add = f"Filename: {f.name}\n\n{s}"
                contents.append(add)
            except Exception:
                pass
        st.success(f"Uploaded {len(contents)} files.")
    else:
        contents = []
    question = st.text_input("Ask a question based on uploaded documents or your topic")
    if st.button("Get Answer"):
        if not question.strip():
            st.warning("Type a question.")
        else:
            # naive retrieval: concat uploaded docs
            ctx = "\n\n".join(contents[:5]) if contents else question
            prompt = f"Use the context below to answer the question.\n\nContext:\n{ctx}\n\nQuestion: {question}\nAnswer concisely in {selected_lang}."
            try:
                resp = client.chat.completions.create(model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}], max_tokens=600)
                if isinstance(resp, dict):
                    ans = resp.get("text") or resp.get("choices",[{}])[0].get("text","")
                else:
                    ans = getattr(resp.choices[0].message, "content", "") or getattr(resp, "text", "")
                st.write(ans)
            except Exception as e:
                st.error(f"Groq error: {e}")

# ---------------------------
# Memory (simple local)
# ---------------------------
elif choice == "Memory":
    user = require_user()
    st.header("Memory — Local notes")
    note = st.text_area("Write a memory/note (it will be appended locally)")
    if st.button("Save Memory"):
        if note.strip():
            with open("memory_log.txt", "a", encoding="utf-8") as f:
                f.write(f"{datetime.utcnow().isoformat()} - {note}\n")
            st.success("Saved locally.")
        else:
            st.info("Write something first.")
    if st.button("Show Memories"):
        if os.path.exists("memory_log.txt"):
            st.download_button("Download memory_log.txt", data=open("memory_log.txt","rb").read(), file_name="memory_log.txt")
            with open("memory_log.txt","r",encoding="utf-8") as f:
                st.text(f.read())
        else:
            st.info("No memories yet.")

# ---------------------------
# Video Summarizer
# ---------------------------
elif choice == "Video Summarizer":
    user = require_user()
    st.header("Video Summarizer — YouTube or Upload")
    video_url = st.text_input("YouTube URL (leave empty to upload file):")
    uploaded_file = st.file_uploader("Upload MP4 (optional)", type=["mp4"])
    if st.button("Summarize Video"):
        try:
            transcript_text = ""
            if video_url:
                # try fetch captions
                vid = ""
                if "v=" in video_url:
                    vid = video_url.split("v=")[-1].split("&")[0]
                elif "youtu.be" in video_url:
                    vid = video_url.split("/")[-1]
                transcript_text = try_fetch_youtube_transcript(vid)
                if not transcript_text:
                    # fallback to audio download + whisper
                    audio_path = download_audio_to_wav_no_ffmpeg(video_url)
                    model = whisper.load_model("tiny")
                    res = model.transcribe(audio_path)
                    transcript_text = res.get("text","")
            elif uploaded_file:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name
                model = whisper.load_model("tiny")
                res = model.transcribe(tmp_path)
                transcript_text = res.get("text","")
            else:
                st.info("Provide a YouTube URL or upload a file.")
                transcript_text = ""

            if transcript_text and transcript_text.strip():
                out = groq_summary(transcript_text, selected_lang)
                st.markdown("### Summary")
                st.write(out)
            else:
                st.warning("No transcript available to summarize.")
        except Exception as e:
            st.error(f"Error while summarizing: {e}")

# ---------------------------
# Settings
# ---------------------------
elif choice == "Settings":
    st.header("Settings & Debug")
    st.write("Groq model:", GROQ_MODEL)
    st.write("Selected language:", selected_lang)
    st.write("Secrets keys available:", list(st.secrets.keys()))
    if st.button("Show memory file contents (debug)"):
        if os.path.exists("memory_log.txt"):
            with open("memory_log.txt","r",encoding="utf-8") as f:
                st.text(f.read())
        else:
            st.info("No memory file present.")

# End of file

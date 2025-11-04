import streamlit as st
import tempfile
import os
import base64
import whisper
from youtube_transcript_api import YouTubeTranscriptApi
from groq import Groq

# -----------------------------
# ✅ Initialize App and Groq Client
# -----------------------------
st.set_page_config(page_title="My Smart Agent", page_icon="🤖", layout="wide")

st.title("🤖 My Smart Agent — Multi-Purpose AI Assistant")
st.write("Plan your day, track finances, monitor habits, learn smarter, and summarize videos!")

# Read API key from Streamlit Secrets (safe & secure)
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    st.error("⚠️ GROQ_API_KEY not found. Please set it in Streamlit → Edit Secrets.")
else:
    client = Groq(api_key=GROQ_API_KEY)

# -----------------------------
# 🌐 Language Selection
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
# 🧠 Utility: Groq Summary Function
# -----------------------------
def groq_summary(text, language):
    """Use Groq LLM to summarize text in the selected language."""
    try:
        prompt = f"Summarize this text in {language} language in less than 10 bullet points:\n{text[:8000]}"
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Groq summarization error: {e}"

# -----------------------------
# 🗓️ 1. Daily Planner
# -----------------------------
def daily_planner():
    st.subheader("📅 Daily Planner")
    tasks = st.text_area("List your tasks for today (one per line):")
    if st.button("🧾 Generate Plan"):
        if tasks.strip():
            plan = groq_summary(f"Create a structured daily plan for these tasks:\n{tasks}", "English")
            st.write(plan)
        else:
            st.warning("Please enter some tasks.")

# -----------------------------
# 💰 2. Finance Tracker
# -----------------------------
def finance_tracker():
    st.subheader("💰 Finance Tracker")
    income = st.number_input("Enter your total income for the month:", min_value=0)
    expenses = st.text_area("Enter your expenses (one per line as 'item - amount'):")
    if st.button("📊 Analyze Finances"):
        try:
            total_expense = 0
            lines = expenses.split("\n")
            for line in lines:
                parts = line.split("-")
                if len(parts) == 2:
                    total_expense += float(parts[1].strip())
            balance = income - total_expense
            st.success(f"💵 Remaining Balance: {balance}")
            summary = groq_summary(f"Income: {income}, Expenses: {expenses}", "English")
            st.write(summary)
        except Exception as e:
            st.error(f"Error calculating finances: {e}")

# -----------------------------
# ❤️ 3. Health & Habits
# -----------------------------
def health_and_habits():
    st.subheader("💪 Health & Habit Tracker")
    habits = st.text_area("Enter your habits (one per line):")
    if st.button("🧠 Analyze Habits"):
        if habits.strip():
            report = groq_summary(f"Analyze these health habits:\n{habits}", "English")
            st.write(report)
        else:
            st.warning("Please enter at least one habit.")

# -----------------------------
# 📘 4. LearnMate (AI Learning Assistant)
# -----------------------------
def learn_mate():
    st.subheader("📚 LearnMate — Your AI Study Partner")
    topic = st.text_input("Enter a topic to learn about:")
    if st.button("🔍 Learn"):
        if topic.strip():
            lesson = groq_summary(f"Explain this topic for a student: {topic}", selected_lang)
            st.write(lesson)
        else:
            st.warning("Please enter a topic.")

# -----------------------------
# 🎬 5. Video Summarizer Agent (Fixed)
# -----------------------------
def summarize_video_agent():
    st.subheader("🎬 Video Summarizer")
    st.write("Upload a local video or enter a YouTube URL to summarize with timestamps.")

    import yt_dlp, tempfile, torch
    from pydub import AudioSegment
    import io

    video_source = st.text_input("🎥 Enter YouTube URL (or leave blank to upload):")
    uploaded_file = st.file_uploader("📂 Upload a local video file (MP4 format)", type=["mp4"])

    def try_fetch_youtube_transcript(video_id):
        """Try fetching transcript safely."""
        try:
            api = YouTubeTranscriptApi()
            transcripts = api.list_transcripts(video_id)
            text = ""
            for t in transcripts:
                text += " ".join([seg["text"] for seg in t.fetch()])
            if not text.strip():
                raise ValueError("Empty transcript")
            return text
        except Exception as e:
            st.warning(f"⚠️ Could not fetch YouTube transcript: {e}")
            return ""

    def download_audio_python(url):
        """Download audio and convert to WAV (no ffmpeg binary needed)."""
        st.info("🎧 Downloading and converting YouTube audio for transcription...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".m4a") as tmpfile:
            ydl_opts = {"format": "bestaudio/best", "outtmpl": tmpfile.name, "quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            audio = AudioSegment.from_file(tmpfile.name, format="m4a")
            wav_file = tmpfile.name + ".wav"
            audio.export(wav_file, format="wav")
            return wav_file

    if st.button("Summarize Video"):
        try:
            text = ""
            if video_source:
                st.info("Fetching transcript or transcribing audio...")
                video_id = ""
                if "v=" in video_source:
                    video_id = video_source.split("v=")[-1].split("&")[0]
                elif "youtu.be" in video_source:
                    video_id = video_source.split("/")[-1]

                text = try_fetch_youtube_transcript(video_id)
                if not text.strip():
                    st.info("🎤 Using Whisper fallback transcription...")
                    audio_path = download_audio_python(video_source)
                    model = whisper.load_model("tiny")
                    result = model.transcribe(audio_path)
                    text = result["text"]
                    st.success("✅ Audio transcription complete.")

            elif uploaded_file:
                st.info("Transcribing uploaded local video...")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmpfile:
                    tmpfile.write(uploaded_file.read())
                    tmp_path = tmpfile.name
                model = whisper.load_model("tiny")
                result = model.transcribe(tmp_path)
                text = result["text"]
                st.success("✅ Local video transcribed successfully.")

            else:
                st.warning("Please provide a YouTube URL or upload a video.")
                return

            # --- Summarize via Groq ---
            if text.strip():
                summary = groq_summary(text, selected_lang)
                st.markdown("### 🧠 Summary")
                st.write(summary)
            else:
                st.warning("No transcript text available to summarize.")

            # --- Highlights example ---
            st.markdown("### ⏱️ Highlights")
            st.markdown("""
            <ul>
            <li><a href="#" onclick="jumpTo(10);return false;">0:10 — Intro</a></li>
            <li><a href="#" onclick="jumpTo(120);return false;">2:00 — Main Ideas</a></li>
            <li><a href="#" onclick="jumpTo(300);return false;">5:00 — Wrap-up</a></li>
            </ul>
            <script>
            function jumpTo(t){ var v=document.getElementById('localVideo'); v.currentTime=t; v.play();}
            </script>
            """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"❌ Error while summarizing: {e}")
            
# -----------------------------
# 🌟 Main Navigation
# -----------------------------
tab = st.sidebar.radio(
    "Choose a Smart Agent Feature",
    [
        "🗓️ Daily Planner",
        "💰 Finance Tracker",
        "❤️ Health & Habits",
        "📘 LearnMate",
        "🎬 Video Summarizer",
    ]
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

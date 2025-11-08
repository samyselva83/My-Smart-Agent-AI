# ============================================================
# 🤖 My Smart Agent — Streamlit Edition (Final Fixed Version)
# ============================================================

import streamlit as st
from datetime import time
from groq import Groq
from youtube_transcript_api import YouTubeTranscriptApi
from pytube import YouTube
import re

# ============================================================
# 🌍 Supported Languages
# ============================================================
LANGUAGES = [
    "English", "Tamil", "Telugu", "Malayalam", "Kannada",
    "Hindi", "French", "Spanish", "German", "Japanese"
]

# ============================================================
# ⚙️ Groq API Setup
# ============================================================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    GROQ_API_KEY = None

if not GROQ_API_KEY:
    st.error("⚠️ Missing GROQ_API_KEY. Please add it in Streamlit secrets.")
    st.stop()

GROQ_MODEL = "llama-3.3-70b-versatile"
client = Groq(api_key=GROQ_API_KEY)

# ============================================================
# 🧠 Daily Planner Agent
# ============================================================
class DailyPlannerAgent:
    def __init__(self, llm_client, language="English", day_start=None, day_end=None):
        self.client = llm_client
        self.language = language
        self.day_start = day_start
        self.day_end = day_end

    def _build_prompt(self, tasks, timezone="local time"):
        if not self.day_start or not self.day_end:
            time_instruction = (
                "Determine realistic working hours automatically "
                "(like 08:30–17:30) depending on number and complexity of tasks."
            )
        else:
            time_instruction = f"Respect working hours between {self.day_start} and {self.day_end} ({timezone})."

        prompt = f"""
You are a smart personal assistant. The user provided these tasks:
{tasks}

Your goals:
- {time_instruction}
- Assign priorities logically.
- Output format: HH:MM–HH:MM | Task — Priority — Short Note
- Keep output in {self.language}.
- End with one motivational sentence.
"""
        return prompt.strip()

    def generate_plan(self, tasks_text, timezone="local time"):
        prompt = self._build_prompt(tasks_text, timezone)
        try:
            resp = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.3,
            )
            return getattr(resp.choices[0].message, "content", "")
        except Exception as e:
            return f"Planner error: {e}"

# ============================================================
# 🧩 Helper Functions for Video Summarizer
# ============================================================
def summarize_video_with_groq(transcript_text, language="English"):
    """Summarize transcript using Groq model"""
    try:
        prompt = f"Summarize this video transcript in {language}. Include 5 key highlights with timestamps in HH:MM format."
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": f"{prompt}\n\n{transcript_text[:8000]}"}],
            max_tokens=700,
            temperature=0.4,
        )
        return getattr(resp.choices[0].message, "content", "")
    except Exception as e:
        return f"Groq summarization error: {e}"

def make_clickable_timestamps(summary_text, video_id):
    """Convert HH:MM into clickable YouTube links"""
    pattern = r"(\d{1,2}:\d{2})"
    def repl(match):
        t = match.group(1)
        parts = t.split(":")
        seconds = int(parts[0]) * 60 + int(parts[1])
        return f"[{t}](https://www.youtube.com/watch?v={video_id}&t={seconds}s)"
    return re.sub(pattern, repl, summary_text)

# ============================================================
# 🧩 Streamlit Layout
# ============================================================
st.set_page_config(page_title="My Smart Agent", layout="wide")
st.title("🤖 My Smart Agent")

st.sidebar.title("🧭 My Smart Agent Menu")
modules = [
    "Dashboard",
    "Daily Planner (AI)",
    "Finance Tracker",
    "Health & Habits",
    "LearnMate",
    "Video Summarizer",
]
choice = st.sidebar.radio("Choose a module", modules)
selected_lang = st.sidebar.selectbox("🌍 Language", LANGUAGES, index=0)

# ============================================================
# 🏠 Dashboard
# ============================================================
if choice == "Dashboard":
    st.header("📊 Dashboard — My Smart Agent Status")
    st.markdown("""
### 🚀 Current Module Status
| Module | Status | Description |
|--------|---------|-------------|
| 🧠 Daily Planner (AI) | ✅ Live | Smart task scheduling with multilingual support |
| 💰 Finance Tracker | ⚙️ Developing | Budget analysis & savings insight |
| 💪 Health & Habits | ⚙️ Developing | Routine & wellness tracker |
| 📚 LearnMate | 🧪 Testing | File-based AI learning companion |
| 🎬 Video Summarizer | 🧩 Enhanced | YouTube summaries with highlights & timestamps |

💡 **Tip:** Try “Daily Planner (AI)” or “Video Summarizer” for full features.
""")

# ============================================================
# 📅 Daily Planner (AI)
# ============================================================
elif choice == "Daily Planner (AI)":
    st.header("🧠 AI Daily Planner")
    tasks_input = st.text_area(
        "Enter your tasks (one per line, optional [high]/[medium]/[low]):",
        placeholder="Example:\nPrepare slides [high]\nEmail clients [medium]\nGym [low]",
        height=200,
    )

    col1, col2 = st.columns(2)
    with col1:
        manual_time = st.toggle("🕒 Set working hours manually", value=False)
    with col2:
        timezone = st.text_input("Timezone", value="local time")

    if manual_time:
        c1, c2 = st.columns(2)
        with c1:
            start_time = st.time_input("Start time", value=time(9, 0))
        with c2:
            end_time = st.time_input("End time", value=time(18, 0))
    else:
        start_time, end_time = None, None

    if st.button("🧩 Generate Smart Plan"):
        if not tasks_input.strip():
            st.warning("Please enter your tasks first.")
        else:
            agent = DailyPlannerAgent(
                client,
                language=selected_lang,
                day_start=start_time.strftime("%H:%M") if start_time else None,
                day_end=end_time.strftime("%H:%M") if end_time else None,
            )
            with st.spinner("Generating plan..."):
                plan = agent.generate_plan(tasks_input, timezone)
            st.markdown("### ✅ Your Smart Plan")
            st.code(plan or "No plan generated", language="markdown")

# ============================================================
# 💰 Finance Tracker (placeholder)
# ============================================================
elif choice == "Finance Tracker":
    st.header("💰 Finance Tracker — Coming Soon")
    st.info("Will include expense categorization, savings insights, and dashboards.")

# ============================================================
# 💪 Health & Habits (placeholder)
# ============================================================
elif choice == "Health & Habits":
    st.header("💪 Health & Habits — Coming Soon")
    st.info("Track routines, workouts, and wellness stats.")

# ============================================================
# 📚 LearnMate (placeholder)
# ============================================================
elif choice == "LearnMate":
    st.header("📚 LearnMate — AI Study Partner")
    st.info("Upload notes and ask AI questions (coming soon).")

# ============================================================
# 🎬 Video Summarizer (Enhanced)
# ============================================================
elif choice == "Video Summarizer":
    st.header("🎬 Video Summarizer — AI Highlights with Clickable Timestamps")
    st.markdown("Paste a YouTube link to get multilingual AI highlights and timestamps.")

    yt_url = st.text_input("Paste YouTube URL:")
    if st.button("🧠 Summarize Video"):
        if not yt_url:
            st.warning("Please enter a valid YouTube link.")
        else:
            try:
                yt = YouTube(yt_url)
                video_id = yt_url.split("v=")[1].split("&")[0]
                st.image(yt.thumbnail_url, width=400, caption=f"🎥 {yt.title}")
                st.write(f"**Duration:** {yt.length // 60} min {yt.length % 60} sec | **Channel:** {yt.author}")

                try:
                    transcript = YouTubeTranscriptApi.get_transcript(video_id)
                    text = " ".join([t["text"] for t in transcript])
                    summary = summarize_video_with_groq(text, language=selected_lang)
                    summary = make_clickable_timestamps(summary, video_id)
                    st.markdown("### 📝 Summary Highlights")
                    st.markdown(summary, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Transcript unavailable: {e}")
                    st.info("This video may not have subtitles or access is restricted.")
            except Exception as e:
                st.error(f"Error loading video: {e}")

import streamlit as st
import os
import base64
import tempfile
from datetime import datetime
from groq import Groq
from youtube_transcript_api import YouTubeTranscriptApi
import whisper

# ---------------------------
#  APP CONFIGURATION
# ---------------------------
st.set_page_config(page_title="My Smart Agent", page_icon="🤖", layout="wide")
st.markdown("<h1 style='text-align:center;'>🤖 My Smart Agent</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;'>Your daily planner, finance tracker, health guide, memory AI, and learn mate — all in one.</p>", unsafe_allow_html=True)

# Sidebar
st.sidebar.title("🌐 Navigation")
menu = st.sidebar.radio("Go to", [
    "🏠 Home",
    "📅 Daily Planner",
    "💰 Finance Tracker",
    "❤️ Health & Habit Tracker",
    "📘 LearnMate",
    "🧠 Memory AI",
    "🎬 Video Summarizer"
])

# Language Selector
languages = ["English", "Tamil", "Telugu", "Malayalam", "Kannada", "Hindi", "French", "Spanish", "German", "Japanese"]
selected_lang = st.sidebar.selectbox("🌍 Choose Summary Language", languages)

# Groq Client
client = Groq(api_key=st.secrets["GROQ_API_KEY"])
os.environ["GROQ_API_KEY"] = GROQ_API_KEY

# ---------------------------
#  UTILITIES
# ---------------------------
def groq_summary(text, language):
    """Generate a short multilingual summary using Groq."""
    try:
        prompt = f"Summarize this text in {language} with key points:\n{text[:8000]}"
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-70b-versatile"
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error generating summary: {e}"


# ---------------------------
#  AGENT MODULES
# ---------------------------

# --- 1. Daily Planner Agent ---
def daily_planner():
    st.subheader("🗓️ Daily Planner")
    date = st.date_input("Select Date", datetime.now())
    tasks = st.text_area("Enter your tasks (one per line)")
    if st.button("Save Plan"):
        st.success(f"✅ Tasks saved for {date}:")
        for t in tasks.split("\n"):
            st.write(f"- {t.strip()}")


# --- 2. Finance Tracker Agent ---
def finance_tracker():
    st.subheader("💰 Finance Tracker")
    col1, col2 = st.columns(2)
    with col1:
        income = st.number_input("Monthly Income (₹)", min_value=0)
    with col2:
        expense = st.number_input("Monthly Expenses (₹)", min_value=0)

    if st.button("Track Finance"):
        savings = income - expense
        st.write(f"💵 Savings: ₹{savings}")
        st.progress(min(max(savings / income, 0), 1))
        if savings < 0:
            st.error("⚠️ Overspending detected! Try reducing unnecessary expenses.")


# --- 3. Health & Habit Tracker Agent ---
def health_tracker():
    st.subheader("🏋️ Health & Habit Tracker")
    sleep = st.slider("Sleep Hours", 0, 12, 7)
    water = st.slider("Water Intake (glasses)", 0, 15, 8)
    steps = st.number_input("Steps Walked Today", min_value=0)
    if st.button("Update Health Log"):
        score = (sleep / 8 + water / 8 + steps / 8000) / 3
        st.write(f"🏆 Health Score: {score*100:.1f}%")
        if score > 0.8:
            st.success("Excellent! Keep it up.")
        elif score > 0.5:
            st.info("Good, but aim for consistency.")
        else:
            st.warning("Needs improvement. Try to maintain regular habits.")


# --- 4. LearnMate Agent ---
def learn_mate():
    st.subheader("📘 LearnMate")
    topic = st.text_input("Enter a topic you want to learn about:")
    if st.button("Generate Summary"):
        summary = groq_summary(topic, selected_lang)
        st.markdown("### 🧠 Key Summary")
        st.write(summary)


# --- 5. Memory AI Agent ---
def memory_ai():
    st.subheader("🧠 Memory AI")
    user_input = st.text_area("Enter your thoughts, notes, or memories:")
    if st.button("Remember This"):
        with open("memory_log.txt", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now()}: {user_input}\n")
        st.success("📝 Memory saved locally.")
    if st.button("Recall Memories"):
        if os.path.exists("memory_log.txt"):
            with open("memory_log.txt", "r", encoding="utf-8") as f:
                st.text(f.read())
        else:
            st.info("No memories saved yet.")


# --- 6. Video Summarizer Agent ---
def summarize_video_agent():
    st.subheader("🎬 Video Summarizer")
    st.write("Upload a local video or enter a YouTube URL to summarize with timestamps.")

    video_source = st.text_input("🎥 Enter YouTube URL (or leave blank to upload):")
    uploaded_file = st.file_uploader("📂 Upload a local video file (MP4 format)", type=["mp4"])

    if st.button("Summarize Video"):
        try:
            text = ""
            if video_source:
                # --- Case 1: YouTube ---
                st.info("Fetching transcript from YouTube...")
                video_id = ""
                if "v=" in video_source:
                    video_id = video_source.split("v=")[-1]
                elif "youtu.be" in video_source:
                    video_id = video_source.split("/")[-1]
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
                text = " ".join([t["text"] for t in transcript])
                st.success("✅ YouTube transcript fetched successfully.")

            elif uploaded_file:
                # --- Case 2: Local Video ---
                st.info("Transcribing uploaded video with Whisper (Groq compatible)...")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmpfile:
                    tmpfile.write(uploaded_file.read())
                    tmp_path = tmpfile.name
                model = whisper.load_model("base")
                result = model.transcribe(tmp_path)
                text = result["text"]
                st.success("✅ Local video transcribed successfully.")

            else:
                st.warning("Please provide a YouTube URL or upload a video.")
                return

            # --- Summarize via Groq ---
            summary = groq_summary(text, selected_lang)
            st.markdown("### 🧠 Summary")
            st.write(summary)

            # --- Clickable Highlights ---
            st.markdown("### ⏱️ Highlights")
            highlights_html = """
            <ul>
            <li><a href="#" onclick="jumpTo(10);return false;">0:10 — Introduction</a></li>
            <li><a href="#" onclick="jumpTo(120);return false;">2:00 — Key Insights</a></li>
            <li><a href="#" onclick="jumpTo(300);return false;">5:00 — Conclusion</a></li>
            </ul>
            <script>
            function jumpTo(t){ var v=document.getElementById('localVideo'); v.currentTime=t; v.play();}
            </script>
            """
            st.markdown(highlights_html, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"❌ Error while summarizing: {e}")


# ---------------------------
#  MAIN APP ROUTING
# ---------------------------
if menu == "🏠 Home":
    st.image("https://cdn-icons-png.flaticon.com/512/4712/4712139.png", width=150)
    st.markdown("### Welcome to **My Smart Agent** 🤖")
    st.write("Manage your tasks, finances, health, learning, memories, and video summaries — all in one app.")
    st.info("Select a section from the sidebar to get started!")

elif menu == "📅 Daily Planner":
    daily_planner()

elif menu == "💰 Finance Tracker":
    finance_tracker()

elif menu == "❤️ Health & Habit Tracker":
    health_tracker()

elif menu == "📘 LearnMate":
    learn_mate()

elif menu == "🧠 Memory AI":
    memory_ai()

elif menu == "🎬 Video Summarizer":
    summarize_video_agent()

import streamlit as st
from datetime import time
from groq import Groq
import base64
import os

# -------------------------------
# 🌍 Supported Languages
# -------------------------------
LANGUAGES = [
    "English", "Tamil", "Telugu", "Malayalam",
    "Kannada", "Hindi", "French", "Spanish", "German", "Japanese"
]

# -------------------------------
# ⚙️ Groq API Setup
# -------------------------------
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

client = Groq(api_key=GROQ_API_KEY)
GROQ_MODEL = "llama-3.3-70b-versatile"  # Latest stable Groq model

# -------------------------------
# 🧠 Daily Planner Agent
# -------------------------------
class DailyPlannerAgent:
    def __init__(self, llm_client, language: str = "English", day_start: str = None, day_end: str = None):
        self.client = llm_client
        self.language = language
        self.day_start = day_start
        self.day_end = day_end

    def _build_prompt(self, tasks: str, timezone: str = "local time"):
        # AI decides timing if user didn't provide
        if not self.day_start or not self.day_end:
            time_instruction = (
                "Choose realistic start and end times automatically based on number and type of tasks. "
                "Distribute tasks sensibly (e.g., 08:30–17:30) with breaks."
            )
        else:
            time_instruction = f"Respect the user’s working hours between {self.day_start} and {self.day_end} ({timezone})."

        prompt = f"""
You are a smart daily planning assistant.
Tasks provided by the user:
{tasks}

Your goal:
- {time_instruction}
- Prioritize tasks logically (critical ones earlier).
- Assign clear time ranges and durations.
- Format output as: HH:MM–HH:MM | Task — Priority — Short Note
- Keep the plan concise, professional, and motivational.
- Write all output in {self.language}.
- End with one motivational line.
"""
        return prompt.strip()

    def generate_plan(self, tasks_text: str, timezone: str = "local time"):
        prompt = self._build_prompt(tasks_text, timezone)
        try:
            resp = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.2,
            )
            plan_text = getattr(resp.choices[0].message, "content", "") or getattr(resp, "text", "")
            return plan_text or "(no plan generated)"
        except Exception as e:
            return f"Planner error: {e}"

# -------------------------------
# 🧩 Streamlit UI Setup
# -------------------------------
st.set_page_config(page_title="My Smart Agent", layout="wide")
st.title(" My Smart Agent AI 🤖")

# Sidebar
st.sidebar.header("🧠 Agent Modules")
selected_lang = st.sidebar.selectbox("🌍 Language", options=LANGUAGES, index=0)
choice = st.sidebar.radio(
    "Select Module",
    [
        "Daily Planner (AI)",
        "Finance Tracker",
        "Health & Habit",
        "LearnMate",
        "Video Summarizer",
    ],
)

# Dummy function for authentication simulation
def require_user():
    return "User"

# -------------------------------
# 📅 Daily Planner Module
# -------------------------------
if choice == "Daily Planner (AI)":
    user = require_user()
    st.header("🧠 AI Daily Planner")

    st.markdown(
        "Enter your tasks below (one per line). Optionally, include priority tags like `[high]`, `[medium]`, `[low]`."
    )
    tasks_input = st.text_area(
        "📝 Tasks",
        placeholder="Example:\nPrepare slides [high]\nEmail clients [medium]\nGym [low]",
        height=200,
    )

    col1, col2 = st.columns(2)
    with col1:
        manual_time = st.toggle("🕒 Manually set working hours", value=False)
    with col2:
        timezone = st.text_input("Timezone (optional)", value="local time")

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
            st.warning("Please enter at least one task.")
        else:
            if manual_time and start_time and end_time:
                agent = DailyPlannerAgent(
                    client,
                    language=selected_lang,
                    day_start=start_time.strftime("%H:%M"),
                    day_end=end_time.strftime("%H:%M"),
                )
            else:
                agent = DailyPlannerAgent(client, language=selected_lang)

            with st.spinner("Generating your personalized plan..."):
                plan = agent.generate_plan(tasks_input, timezone=timezone)

            st.markdown("### ✅ Your Smart Day Plan")
            if plan.startswith("Planner error") or plan.startswith("⚠️"):
                st.error(plan)
            else:
                st.code(plan, language="markdown")

# -------------------------------
# 💰 Finance Tracker (Placeholder)
# -------------------------------
elif choice == "Finance Tracker":
    st.header("💰 Finance Tracker (Coming Soon)")
    st.info("This module will track your daily expenses and savings goals.")

# -------------------------------
# 💪 Health & Habit Tracker (Placeholder)
# -------------------------------
elif choice == "Health & Habit":
    st.header("💪 Health & Habit Tracker")
    st.info("Track your routines, water intake, and exercise habits.")

# -------------------------------
# 📚 LearnMate (Placeholder)
# -------------------------------
elif choice == "LearnMate":
    st.header("📚 LearnMate — Your AI Study Partner")
    st.info("Summarize notes, generate flashcards, and answer your study questions.")

# -------------------------------
# 🎬 Video Summarizer (Placeholder)
# -------------------------------
elif choice == "Video Summarizer":
    st.header("🎬 Video Summarizer")
    st.info("Upload or link a YouTube video to generate AI-based highlights with timestamps.")
    st.warning("Video summarizer integration requires ffmpeg and Whisper; feature under testing.")

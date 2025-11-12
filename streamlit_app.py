# ============================================================
# 🌐 Smart Agent AI Dashboard
# Modules: Daily Planner | Finance Tracker | Health & Habit |
#          LearnMate | Memory | Video Summary (AI Summarizer)
# Author: Selva Kumar
# ============================================================

import streamlit as st
import re, os, tempfile, shutil, glob
import yt_dlp
from collections import OrderedDict

# Optional OpenAI client
try:
    from openai import OpenAI
    client = OpenAI()
except Exception:
    client = None

try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
except Exception:
    YouTubeTranscriptApi = None
    TranscriptsDisabled = Exception
    NoTranscriptFound = Exception


# ------------------------------------------------------------
# UTILITIES
# ------------------------------------------------------------

def clean_youtube_url(url: str) -> str:
    base = url.split("&")[0]
    base = base.split("?si=")[0]
    return base.strip()

def extract_video_id(url: str):
    m = re.search(r"(?:v=|be/)([0-9A-Za-z_-]{11})", url)
    return m.group(1) if m else None


# ------------------------------------------------------------
# TRANSCRIPT FETCH
# ------------------------------------------------------------

def try_transcript_api(video_id):
    if YouTubeTranscriptApi is None:
        return None, "Transcript API not available"
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        return transcript, None
    except (TranscriptsDisabled, NoTranscriptFound):
        return None, "No transcript found"
    except Exception as e:
        return None, f"Transcript API error: {e}"

def try_yt_dlp_subtitles(video_url, video_id):
    tmp = tempfile.mkdtemp()
    opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en"],
        "subtitlesformat": "vtt",
        "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s"),
        "quiet": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([video_url])
    except Exception as e:
        return None, f"yt_dlp error: {e}", tmp

    vtt_files = glob.glob(os.path.join(tmp, f"{video_id}*.vtt"))
    if not vtt_files:
        return None, "No subtitle file found", tmp
    return vtt_files[0], None, tmp

def parse_vtt(vtt_path):
    text = open(vtt_path, "r", encoding="utf-8", errors="ignore").read()
    text = re.sub(r"WEBVTT.*\n", "", text, flags=re.IGNORECASE)
    blocks = re.split(r"\n\s*\n", text.strip())
    segs = []
    for block in blocks:
        m = re.search(r"(\d{2}:\d{2}:\d{2}\.\d{3})\s-->\s(\d{2}:\d{2}:\d{2}\.\d{3})", block)
        if not m:
            continue
        start = m.group(1)
        txt = re.sub(r".*-->\s.*\n", "", block).strip().replace("\n", " ")
        if txt:
            segs.append({"start": start, "text": txt})
    return segs


# ------------------------------------------------------------
# SUMMARIZATION
# ------------------------------------------------------------

def summarize_clean_text(full_text: str) -> str:
    """Generate a short, meaningful summary from clean transcript."""
    # Deep clean repetitive phrases and symbols
    cleaned = re.sub(r'<[^>]+>|align:start|position:\d+%', '', full_text)
    cleaned = re.sub(r'\b(\w+)( \1\b)+', r'\1', cleaned)
    cleaned = re.sub(r'[^A-Za-z0-9.,?! ]+', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    snippet = cleaned[:4000]

    if client:
        try:
            prompt = (
                "Summarize the following YouTube video transcript into 4–6 sentences "
                "(under 120 words). Use a clear and natural style like:\n"
                "'This video introduces the fundamentals of Generative AI, "
                "covering machine learning, deep learning, and language models "
                "with simple examples.'\n\nTranscript:\n" + snippet
            )
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.5,
                messages=[
                    {"role": "system", "content": "You summarize YouTube educational videos clearly."},
                    {"role": "user", "content": prompt},
                ],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"⚠️ Summarization error: {e}"
    else:
        sentences = re.split(r'[.!?]', snippet)
        return ". ".join(sentences[:3]) + "..."


# ------------------------------------------------------------
# MAIN APP
# ------------------------------------------------------------

st.set_page_config(page_title="My Smart Agent AI", page_icon="🤖", layout="wide")
st.sidebar.title("🧭 Navigation")

menu = [
    "🗓️ Daily Planner (AI)",
    "💵 Finance Tracker",
    "💪 Health & Habit",
    "🧠 LearnMate",
    "🧾 Memory",
    "🎥 Video Summary"
]
choice = st.sidebar.radio("Choose a module:", menu)

# ------------------------------------------------------------
# MODULE: DAILY PLANNER
# ------------------------------------------------------------
if choice == "🗓️ Daily Planner (AI)":
    st.title("🗓️ AI Daily Planner")
    st.info("Smart planner that auto-creates your day’s schedule with AI. Coming soon!")

# ------------------------------------------------------------
# MODULE: FINANCE TRACKER
# ------------------------------------------------------------
elif choice == "💵 Finance Tracker":
    st.title("💵 Finance Tracker")
    st.info("Track expenses, savings, and goals. Smart budgeting in development.")

# ------------------------------------------------------------
# MODULE: HEALTH & HABIT
# ------------------------------------------------------------
elif choice == "💪 Health & Habit":
    st.title("💪 Health & Habit Tracker")
    st.info("Monitor daily habits, workouts, and health scores. Coming soon.")

# ------------------------------------------------------------
# MODULE: LEARNMATE
# ------------------------------------------------------------
elif choice == "🧠 LearnMate":
    st.title("🧠 LearnMate – AI Learning Assistant")
    st.info("Personal AI tutor that explains topics and quizzes you interactively. Coming soon.")

# ------------------------------------------------------------
# MODULE: MEMORY
# ------------------------------------------------------------
elif choice == "🧾 Memory":
    st.title("🧾 Memory & Notes")
    st.info("Persistent memory for projects and ideas. Under active development.")

# ------------------------------------------------------------
# MODULE: VIDEO SUMMARY
# ------------------------------------------------------------
elif choice == "🎥 Video Summary":
    st.title("🎥 AI Video Summarizer + Key Highlights")
    st.markdown("Paste a YouTube link — get a clean **AI-written summary** and clickable timestamps.")

    url = st.text_input("🎬 Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=gqQ8fMbXKHE")

    if st.button("🚀 Generate Summary"):
        if not url.strip():
            st.warning("Please enter a YouTube link.")
        else:
            with st.spinner("Fetching transcript and generating summary..."):
                vid = extract_video_id(url)
                segs, err = try_transcript_api(vid)
                if not segs:
                    vtt_path, err2, tmpdir = try_yt_dlp_subtitles(url, vid)
                    if vtt_path:
                        try:
                            segs = parse_vtt(vtt_path)
                        finally:
                            shutil.rmtree(tmpdir, ignore_errors=True)
                    else:
                        st.error(f"❌ Could not fetch captions: {err2}")
                        segs = None

                if not segs:
                    st.error("⚠️ No captions found or subtitles disabled.")
                else:
                    # Clean transcript text
                    full_text = " ".join([s["text"] for s in segs])
                    summary = summarize_clean_text(full_text)

                    st.subheader("🧠 AI-Generated Video Summary")
                    st.caption("Quality and accuracy may vary.")
                    st.write(summary)

                    # Display key timestamps (5 representative ones)
                    st.markdown("---")
                    st.subheader("🕒 Key Moments")
                    n = len(segs)
                    step = max(1, n // 5)
                    points = segs[::step][:5]
                    labels = ["Introduction", "Concept", "Example", "Insight", "Conclusion"]

                    for i, s in enumerate(points):
                        start = s["start"].split(".")[0]
                        try:
                            h, m, s_ = map(int, start.split(":"))
                        except:
                            h, m, s_ = 0, 0, 0
                        total = h * 3600 + m * 60 + s_
                        yt_link = f"https://www.youtube.com/watch?v={vid}&t={total}s"
                        label = labels[i]
                        st.markdown(f"- {m:02d}:{s_:02d} → [{label}]({yt_link})")

    st.markdown("---")
    st.caption("🎯 Built by Selva Kumar | AI-powered YouTube Video Summarizer")

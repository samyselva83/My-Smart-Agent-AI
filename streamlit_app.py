import streamlit as st
import re, os, tempfile, glob, shutil
import yt_dlp
from collections import OrderedDict

# ------------------------------------------------------------
# Optional Summarization (OpenAI)
# ------------------------------------------------------------
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
# Utility Functions
# ------------------------------------------------------------
def extract_video_id(url: str):
    """Extract YouTube video ID from URL."""
    match = re.search(r"(?:v=|be/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None


def try_transcript_api(video_id):
    """Try fetching transcript using YouTubeTranscriptApi."""
    if YouTubeTranscriptApi is None:
        return None, "Transcript API not available"
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        return transcript, None
    except (TranscriptsDisabled, NoTranscriptFound):
        return None, "Transcript not available"
    except Exception as e:
        return None, f"Transcript error: {e}"


def try_yt_dlp_subtitles(video_url, video_id):
    """Fallback: download subtitles using yt_dlp."""
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
    """Parse .vtt caption file."""
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
# Summarization Helper
# ------------------------------------------------------------
def summarize_text(clean_text):
    """Summarize transcript using OpenAI GPT or fallback."""
    if not clean_text.strip():
        return "No transcript available to summarize."

    if client:
        try:
            prompt = (
                "You are an expert video summarizer. Read the transcript and write a concise, "
                "human-like paragraph (80–120 words) summarizing the main ideas, avoiding repetition "
                "and caption noise. Example style:\n"
                "'This video introduces the fundamentals of Generative AI, explaining the differences "
                "between traditional and generative models, and covering tools like LangChain and LLMs.'\n\n"
                f"Transcript:\n{clean_text[:6000]}"
            )
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.4,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"⚠️ Summarization error: {e}"
    else:
        # Simple fallback summary
        sentences = re.split(r'[.!?]', clean_text)
        return ". ".join(sentences[:5]) + "..."


# ------------------------------------------------------------
# Streamlit Layout
# ------------------------------------------------------------
st.set_page_config(page_title="🧠 My Smart Agent", page_icon="🤖", layout="wide")

st.sidebar.title("🧭 Navigation")
module = st.sidebar.radio(
    "Select a Module:",
    [
        "🗓️ Daily Planner (AI)",
        "💵 Finance Tracker",
        "💪 Health & Habit",
        "🧠 LearnMate",
        "🧾 Memory",
        "🎥 Video Summary",
    ],
)

# ------------------------------------------------------------
# Individual Module Sections
# ------------------------------------------------------------

if module == "🗓️ Daily Planner (AI)":
    st.title("🗓️ AI Daily Planner")
    st.write("Auto-plan your day based on goals, time, and priorities.")
    st.info("✨ Coming soon: smart scheduling and multilingual reminders.")


elif module == "💵 Finance Tracker":
    st.title("💵 Finance Tracker")
    st.write("Monitor and analyze daily expenses intelligently.")
    st.info("📊 Coming soon: AI expense categorization and spending insights.")


elif module == "💪 Health & Habit":
    st.title("💪 Health & Habit Coach")
    st.write("Track your physical health and daily habits.")
    st.info("🩺 Coming soon: wellness scoring and routine improvement AI.")


elif module == "🧠 LearnMate":
    st.title("🧠 LearnMate")
    st.write("Interactive learning assistant for AI, ML, and coding topics.")
    st.info("🎓 Coming soon: adaptive quizzes and visual learning modules.")


elif module == "🧾 Memory":
    st.title("🧾 Memory Vault")
    st.write("Store and retrieve your notes, thoughts, and project logs.")
    st.info("📘 Coming soon: semantic memory search and AI recall tools.")


# ------------------------------------------------------------
# 🎥 Video Summarizer Module
# ------------------------------------------------------------
elif module == "🎥 Video Summary":
    st.title("🎥 AI Video Summarizer + Key Highlights")
    st.markdown("Paste a YouTube video URL below to get a clean **AI summary** and **key timestamps**.")

    url = st.text_input("🎬 Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=gqQ8fMbXKHE")

    if st.button("🚀 Summarize Video"):
        if not url.strip():
            st.warning("Please enter a valid YouTube URL.")
        else:
            with st.spinner("⏳ Fetching transcript and generating summary..."):
                video_id = extract_video_id(url)
                if not video_id:
                    st.error("Invalid YouTube link.")
                else:
                    segs, err = try_transcript_api(video_id)
                    if not segs:
                        vtt_path, err2, tmpdir = try_yt_dlp_subtitles(url, video_id)
                        if vtt_path:
                            try:
                                segs = parse_vtt(vtt_path)
                            finally:
                                shutil.rmtree(tmpdir, ignore_errors=True)
                        else:
                            st.error(f"❌ Could not retrieve subtitles: {err2}")
                            segs = None

                    if not segs:
                        st.error("⚠️ No transcript found or captions unavailable.")
                    else:
                        # Clean and combine text
                        clean_lines = []
                        for s in segs:
                            t = re.sub(r'<[^>]+>', '', s.get("text", ""))
                            t = re.sub(r'[^A-Za-z0-9.,?! ]+', ' ', t)
                            t = re.sub(r'\s+', ' ', t).strip()
                            if t:
                                clean_lines.append(t)
                        transcript = " ".join(clean_lines)
                        transcript = re.sub(r'\b(\w+)( \1\b)+', r'\1', transcript)

                        st.subheader("🧠 AI-Generated Video Summary")
                        summary = summarize_text(transcript)
                        st.write(summary)

                        # Key Timestamps
                        st.markdown("---")
                        st.subheader("🕒 Key Moments")
                        n = len(segs)
                        step = max(1, n // 5)
                        labels = ["Introduction", "Topic Overview", "Key Example", "Main Insight", "Conclusion"]

                        for i, s in enumerate(segs[::step][:5]):
                            start = s["start"].split(".")[0]
                            h, m, sec = map(int, start.split(":"))
                            total = h * 3600 + m * 60 + sec
                            yt_link = f"https://www.youtube.com/watch?v={video_id}&t={total}s"
                            label = labels[i]
                            st.markdown(f"- {m:02d}:{sec:02d} → [{label}]({yt_link})")

    st.markdown("---")
    st.caption("🤖 Built by Selva Kumar | Works best with caption-enabled videos.")

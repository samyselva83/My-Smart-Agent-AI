# ============================================================
# 🎥 YouTube Video Summarizer + Timestamp Highlighter
# Integrated into My Smart Agent App
# Author: Selva Kumar
# ============================================================

import streamlit as st
import re, os, tempfile, glob, shutil
from collections import OrderedDict
import yt_dlp

# Optional AI summarizer
try:
    from openai import OpenAI
    client = OpenAI()
except Exception:
    client = None

# Optional transcript API
try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
except Exception:
    YouTubeTranscriptApi = None
    TranscriptsDisabled = Exception
    NoTranscriptFound = Exception


# ============================================================
# 📦 UTILITIES
# ============================================================

def clean_youtube_url(url: str) -> str:
    base = url.split("&")[0]
    base = base.split("?si=")[0]
    return base.strip()

def extract_video_id(url: str):
    m = re.search(r"(?:v=|be/)([0-9A-Za-z_-]{11})", url)
    return m.group(1) if m else None


# ============================================================
# 🎬 TRANSCRIPT FETCH
# ============================================================

def try_transcript_api(video_id):
    """Try fetching transcript via YouTubeTranscriptApi"""
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
    """Fallback using yt_dlp to get subtitles"""
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
    """Parse VTT subtitle into clean segments"""
    text = open(vtt_path, "r", encoding="utf-8", errors="ignore").read()
    text = re.sub(r"WEBVTT.*\n", "", text, flags=re.IGNORECASE)
    blocks = re.split(r"\n\s*\n", text.strip())
    segs = []
    for block in blocks:
        m = re.search(r"(\d{2}:\d{2}:\d{2}\.\d{3})\s-->\s(\d{2}:\d{2}:\d{2}\.\d{3})", block)
        if not m:
            continue
        start = m.group(1)
        txt = re.sub(r".*-->\s.*\n", "", block)
        txt = re.sub(r"<[^>]+>", "", txt)  # remove <c> tags
        txt = re.sub(r"align:start.*", "", txt)
        txt = txt.replace("\n", " ").strip()
        if txt:
            segs.append({"start": start, "text": txt})
    return segs


# ============================================================
# 🔎 CAPTION FETCH MASTER
# ============================================================

def fetch_captions(video_url):
    url = clean_youtube_url(video_url)
    vid = extract_video_id(url)
    if not vid:
        return None, "Invalid YouTube URL"

    segs, err = try_transcript_api(vid)
    if segs:
        return segs, None

    vtt_path, err2, tmpdir = try_yt_dlp_subtitles(url, vid)
    if vtt_path:
        try:
            parsed = parse_vtt(vtt_path)
            if parsed:
                return parsed, None
            return None, "Parsed 0 lines"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    else:
        return None, f"No captions: {err2}"


# ============================================================
# 🧠 AI SUMMARIZER
# ============================================================

def summarize_text(text):
    """Summarize transcript cleanly"""
    if not text.strip():
        return "No transcript content found."

    if not client:
        # fallback simple summary
        parts = text.split(". ")
        return ". ".join(parts[:8]) + "..."
    try:
        prompt = f"Summarize this YouTube video transcript clearly and concisely (within 200 words):\n{text}"
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"(Summarization error: {e})"


# ============================================================
# 🖥️ STREAMLIT APP (VIDEO SUMMARY MODULE)
# ============================================================

st.set_page_config(page_title="🎥 My Smart Agent", page_icon="🤖", layout="wide")

st.sidebar.title("🤖 My Smart Agent Menu")
module = st.sidebar.radio(
    "Select a module",
    [
        "🗓️ Daily Planner (AI)",
        "💵 Finance Tracker",
        "💪 Health & Habit",
        "🧠 LearnMate",
        "🧾 Memory",
        "🎥 Video Summary"
    ]
)

# ============================================================
# 🎥 VIDEO SUMMARY MODULE
# ============================================================

if module == "🎥 Video Summary":
    st.title("🎥 YouTube Video Summarizer + Timestamp Highlighter")
    st.markdown("Paste a YouTube link to get AI summary and clickable timestamps.")

    url = st.text_input("🎬 Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=6Dh-RL__uN4")

    if st.button("🚀 Generate Summary"):
        if not url.strip():
            st.warning("Please enter a valid YouTube link.")
        else:
            with st.spinner("Fetching transcript and generating summary..."):
                segs, err = fetch_captions(url)
                if err:
                    st.error(f"❌ {err}")
                elif not segs:
                    st.warning("⚠️ No captions found.")
                else:
                    # Clean duplicates
                    seen = OrderedDict()
                    for s in segs:
                        if s["text"] not in seen:
                            seen[s["text"]] = s["start"]
                    segs = [{"start": v, "text": k} for k, v in seen.items()]

                    # Build full transcript
                    full_text = " ".join([s["text"] for s in segs])

                    # 🧠 Show AI summary first
                    st.subheader("🧠 AI Summary of the Video")
                    summary = summarize_text(full_text)
                    st.write(summary)

                    # 🕒 Then show timestamps
                    st.markdown("---")
                    st.subheader("🕒 Clickable Timestamp Captions")

                    vid = extract_video_id(url)
                    for s in segs:
                        t = s["start"].split(".")[0]
                        h, m, s_ = map(int, t.split(":"))
                        total = h * 3600 + m * 60 + s_
                        yt_link = f"https://www.youtube.com/watch?v={vid}&t={total}s"
                        st.markdown(f"- [{s['start']}] → [{s['text']}]({yt_link})")

# ============================================================
# 🧩 OTHER MODULE PLACEHOLDERS
# ============================================================

elif module == "🗓️ Daily Planner (AI)":
    st.header("🗓️ Daily Planner (AI)")
    st.info("Coming soon — AI auto-plans your day based on your goals.")

elif module == "💵 Finance Tracker":
    st.header("💵 Finance Tracker")
    st.info("Track your expenses and generate smart finance insights.")

elif module == "💪 Health & Habit":
    st.header("💪 Health & Habit")
    st.info("Monitor your wellness activities and habits daily.")

elif module == "🧠 LearnMate":
    st.header("🧠 LearnMate")
    st.info("Learn smarter with AI notes, flashcards, and explanations.")

elif module == "🧾 Memory":
    st.header("🧾 Memory Vault")
    st.info("Save key information, notes, and personal AI memories.")

st.markdown("---")
st.caption("Developed by Selva Kumar | Supports only caption-enabled YouTube videos.")

# ============================================================
# 🎥 YouTube Video Summarizer + Smart Timestamp Highlighter
# Author: Selva Kumar (My Smart Agent)
# ============================================================

import streamlit as st
import re, os, tempfile, glob, shutil
from collections import OrderedDict
import yt_dlp
from difflib import SequenceMatcher

# Optional AI summarizer (OpenAI)
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
    """Parse and clean VTT subtitles"""
    text = open(vtt_path, "r", encoding="utf-8", errors="ignore").read()
    text = re.sub(r"WEBVTT.*\n", "", text, flags=re.IGNORECASE)
    blocks = re.split(r"\n\s*\n", text.strip())
    segs = []
    for block in blocks:
        m = re.search(r"(\d{2}:\d{2}:\d{2}\.\d{3})\s-->\s", block)
        if not m: continue
        start = m.group(1)
        txt = re.sub(r".*-->\s.*\n", "", block)
        txt = re.sub(r"<[^>]+>", "", txt)
        txt = txt.replace("\n", " ").strip()
        if txt:
            segs.append({"start": start, "text": txt})
    return segs


# ============================================================
# 🧠 TEXT CLEANING & CLUSTERING
# ============================================================

def is_similar(a, b, threshold=0.85):
    return SequenceMatcher(None, a, b).ratio() > threshold

def clean_and_group_segments(segs):
    """Merge repeated or overlapping captions & group by time"""
    cleaned = []
    prev = ""
    for s in segs:
        txt = re.sub(r'\s+', ' ', s["text"]).strip()
        if not txt:
            continue
        if not is_similar(prev, txt):
            cleaned.append(s)
        prev = txt
    # Now reduce to 5–6 segments for timestamp summary
    n = len(cleaned)
    group_size = max(1, n // 5)
    grouped = []
    for i in range(0, n, group_size):
        group = cleaned[i:i+group_size]
        if group:
            start = group[0]["start"]
            text = " ".join(g["text"] for g in group)
            grouped.append({"start": start, "text": text})
    return grouped


# ============================================================
# 🧠 SUMMARIZER
# ============================================================

def summarize_text(text):
    """Summarize transcript into short readable summary"""
    if not text.strip():
        return "No transcript content found."

    if not client:
        sentences = text.split(". ")
        return ". ".join(sentences[:5]) + "..."
    try:
        prompt = (
            "Summarize the following YouTube transcript in **less than 120 words**, "
            "keeping only key ideas and avoiding repetition:\n\n"
            f"{text}"
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"(Summarization error: {e})"


def generate_timestamps_summary(grouped, video_id):
    """Generate simplified timestamp-style summary"""
    results = []
    labels = ["Introduction", "Topic Overview", "Main Concept", "Example/Case Study", "Conclusion"]
    for i, g in enumerate(grouped[:5]):
        t = g["start"].split(".")[0]
        h, m, s_ = map(int, t.split(":"))
        total = h * 3600 + m * 60 + s_
        yt_link = f"https://www.youtube.com/watch?v={video_id}&t={total}s"
        label = labels[i] if i < len(labels) else f"Section {i+1}"
        results.append(f"{m}:{s_:02d} → [{label}]({yt_link})")
    return results


# ============================================================
# 🎥 STREAMLIT APP
# ============================================================

st.set_page_config(page_title="🎥 My Smart Agent", page_icon="🤖", layout="wide")

st.sidebar.title("🤖 My Smart Agent")
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
# ------------------------------------------------------------
# 🎥 VIDEO SUMMARIZER (Deduplicated + Clean Highlights)
# ------------------------------------------------------------

if module == "🎥 Video Summary":
    st.title("🎥 YouTube Video Summarizer + Key Highlights")
    st.markdown("Paste a YouTube URL to get a **clean AI summary** and **key clickable timestamps**.")

    url = st.text_input("🎬 Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=d4yCWBGFCEs")

    if st.button("🚀 Generate Summary"):
        if not url.strip():
            st.warning("Please paste a valid YouTube link.")
        else:
            with st.spinner("Fetching transcript and generating summary..."):
                video_id = extract_video_id(url)
                if not video_id:
                    st.error("Invalid YouTube URL format.")
                else:
                    segs, err = try_transcript_api(video_id)
                    if not segs:
                        vtt_path, err2, tmpdir = try_yt_dlp_subtitles(url, video_id)
                        if vtt_path:
                            try:
                                segs = parse_vtt(vtt_path)
                                err = err2
                            finally:
                                shutil.rmtree(tmpdir, ignore_errors=True)
                        else:
                            st.error(f"❌ Could not fetch subtitles: {err2}")
                            segs = None
                    if err:
                        st.warning(f"⚠️ {err}")

                    if not segs or not isinstance(segs, list):
                        st.error("Transcript could not be parsed correctly.")
                    else:
                        # ✅ 1️⃣ Clean + normalize transcript
                        raw_lines = [s["text"] for s in segs if s.get("text")]
                        cleaned_lines = []
                        for line in raw_lines:
                            line = re.sub(r"\d{2}:\d{2}:\d{2}\.\d{3}", "", line)
                            line = re.sub(r"align:start|position:\d+%|c>|<[^>]+>", "", line)
                            line = re.sub(r"\s+", " ", line).strip().lower()
                            if len(line) > 8:
                                cleaned_lines.append(line)

                        # ✅ 2️⃣ Deduplicate similar lines
                        unique_lines = []
                        for line in cleaned_lines:
                            if not unique_lines or line not in unique_lines[-1]:
                                if all(line not in prev for prev in unique_lines[-3:]):  # last 3 lines check
                                    unique_lines.append(line)

                        # ✅ 3️⃣ Sentence-level compression
                        compressed_text = " ".join(unique_lines)
                        compressed_text = re.sub(r"(?:\b(\w+)\s+\1\b)", r"\1", compressed_text)  # remove duplicate words
                        short_text = compressed_text[:2000]  # keep short for clarity

                        # 🧠 4️⃣ Concise AI Summary (forced bullet output)
                        st.subheader("🧠 Key Highlights Summary")
                        summary_prompt = (
                            "You are a professional video summarizer. "
                            "Summarize the following transcript into exactly **5 short bullet points**. "
                            "Do NOT include timestamps, repeated words, or unrelated sentences. "
                            "Focus on main ideas, key examples, and conclusions.\n\n"
                            f"Transcript:\n{short_text}"
                        )

                        short_summary = "(Summary unavailable)"
                        try:
                            if client:
                                resp = client.chat.completions.create(
                                    model="gpt-4o-mini",
                                    temperature=0.3,
                                    messages=[{"role": "user", "content": summary_prompt}]
                                )
                                result = resp.choices[0].message.content.strip()
                                lines = [l.strip("•- \n") for l in result.split("\n") if l.strip()]
                                lines = lines[:5]
                                short_summary = "• " + "\n• ".join(lines)
                            else:
                                sentences = re.split(r'[.!?]', short_text)
                                short_summary = "• " + "\n• ".join(sentences[:5])
                        except Exception as e:
                            short_summary = f"⚠️ Summarization error: {e}"

                        st.write(short_summary)

                        # 🕒 5️⃣ Key Moments
                        st.markdown("---")
                        st.subheader("🕒 Key Moments")

                        n = len(segs)
                        jump_points = [0, int(n/4), int(n/2), int(3*n/4), n-1]
                        labels = ["Introduction", "Core Idea", "Example / Case", "Conclusion"]

                        for i, idx in enumerate(jump_points[:len(labels)]):
                            s = segs[idx]
                            start_time = s["start"].split(".")[0]
                            try:
                                h, m, s_ = map(int, start_time.split(":"))
                            except:
                                h, m, s_ = 0, 0, 0
                            total = h * 3600 + m * 60 + s_
                            yt_link = f"https://www.youtube.com/watch?v={video_id}&t={total}s"
                            st.markdown(f"- {m:02d}:{s_:02d} → [{labels[i]}]({yt_link})")

    st.markdown("---")
    st.caption("Built by Selva Kumar | Smart AI Video Highlights 🎬")

# ------------------------------------------------------------
# 📋 PLACEHOLDER MODULES
# ------------------------------------------------------------

elif module == "🗓️ Daily Planner (AI)":
    st.header("🗓️ Daily Planner (AI)")
    st.info("Coming soon — AI auto-plans your day intelligently.")

elif module == "💵 Finance Tracker":
    st.header("💵 Finance Tracker")
    st.info("Monitor and analyze your daily expenses smartly.")

elif module == "💪 Health & Habit":
    st.header("💪 Health & Habit")
    st.info("Track your habits, goals, and health routines.")

elif module == "🧠 LearnMate":
    st.header("🧠 LearnMate")
    st.info("AI-assisted learning with flashcards and summaries.")

elif module == "🧾 Memory":
    st.header("🧾 Memory Vault")
    st.info("Store your thoughts and recall them anytime with AI.")

st.markdown("---")
st.caption("Developed by Selva Kumar | Optimized for caption-enabled YouTube videos.")

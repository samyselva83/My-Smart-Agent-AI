# 🎥 YouTube Smart Video Summarizer + Key Highlights
# Author: My Smart Agent (Selva Kumar)

import streamlit as st
import re, os, tempfile, shutil, glob
import yt_dlp
from collections import OrderedDict

# --- Optional OpenAI Summarizer ---
try:
    from openai import OpenAI
    client = OpenAI()
except Exception:
    client = None

# --- Transcript API ---
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
# FETCH TRANSCRIPT
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
        if not m: continue
        start = m.group(1)
        txt = re.sub(r".*-->\s.*\n", "", block).strip().replace("\n", " ")
        if txt:
            segs.append({"start": start, "text": txt})
    return segs


# ------------------------------------------------------------
# SUMMARIZATION
# ------------------------------------------------------------

def generate_summary(text: str):
    """Generate a human-like summary of a transcript"""
    if not client:
        # fallback simple method
        sentences = re.split(r'[.!?]', text)
        return ". ".join(sentences[:5]) + "..."

    prompt = (
        "You are a professional summarizer. "
        "Summarize the YouTube video transcript in a short, clear English paragraph "
        "(under 120 words). Focus on what the instructor explains — main ideas, concepts, and examples. "
        "Ignore filler words, repetitions, and timestamps. Write naturally, like this example:\n\n"
        "‘This video introduces the fundamentals of Generative AI, explaining key differences between "
        "traditional and generative models. The instructor discusses machine learning, neural networks, "
        "and language models with real-world examples and tools such as LangChain.’\n\n"
        f"Transcript:\n{text}"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            messages=[
                {"role": "system", "content": "You summarize educational YouTube content."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ AI Summarization failed: {e}"


# ------------------------------------------------------------
# STREAMLIT UI
# ------------------------------------------------------------

st.set_page_config(page_title="🎥 AI Video Summarizer", page_icon="🎬", layout="wide")

st.title("🎥 YouTube Video Summarizer + Key Highlights")
st.markdown("Paste a YouTube URL to get an **AI-written short summary** and **clickable key timestamps.**")

url = st.text_input("🎬 Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=gqQ8fMbXKHE")

if st.button("🚀 Generate Summary"):
    if not url.strip():
        st.warning("Please paste a valid YouTube link.")
    else:
        with st.spinner("⏳ Fetching transcript..."):
            video_id = extract_video_id(url)
            if not video_id:
                st.error("Invalid YouTube URL.")
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

                if not segs:
                    st.error("⚠️ No transcript data found or captions disabled.")
                else:
                    # Clean and combine transcript
                    text_parts = []
                    for s in segs:
                        txt = s.get("text", "")
                        txt = re.sub(r'<[^>]+>', '', txt)
                        txt = re.sub(r'[^A-Za-z0-9.,?! ]+', ' ', txt)
                        txt = re.sub(r'\s+', ' ', txt).strip()
                        if len(txt) > 3:
                            text_parts.append(txt)

                    full_text = " ".join(text_parts)
                    full_text = re.sub(r'\b(\w+)( \1\b)+', r'\1', full_text)
                    snippet = full_text[:6000]

                    # --- AI Summary ---
                    st.subheader("🧠 AI Summary of the Video")
                    st.caption("Generated using transcript — may vary slightly from full content.")
                    summary = generate_summary(snippet)
                    st.write(summary)

                    # --- Key Timestamps ---
                    st.markdown("---")
                    st.subheader("🕒 Key Moments")
                    n = len(segs)
                    step = max(1, n // 5)
                    points = segs[::step][:5]
                    labels = ["Introduction", "Topic Overview", "Main Concept", "Example", "Conclusion"]

                    for i, s in enumerate(points):
                        t = s["start"].split(".")[0]
                        try:
                            h, m, s_ = map(int, t.split(":"))
                        except:
                            h, m, s_ = 0, 0, 0
                        total = h * 3600 + m * 60 + s_
                        yt_link = f"https://www.youtube.com/watch?v={video_id}&t={total}s"
                        st.markdown(f"- {m:02d}:{s_:02d} → [{labels[i]}]({yt_link})")

st.markdown("---")
st.caption("Built by Selva Kumar | Smart AI Video Summarizer")

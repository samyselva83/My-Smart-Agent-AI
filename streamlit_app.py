# 🎯 YouTube Timestamp Summarizer (Groq API Edition)
# Author: My Smart Agent (Selva Kumar)

import streamlit as st
import re, os, tempfile, glob, shutil
import yt_dlp
from collections import OrderedDict
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from groq import Groq

# ------------------------------------------------------------
# 🧠 Initialize Groq Client
# ------------------------------------------------------------
try:
    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    groq_client = None


# ------------------------------------------------------------
# 🔧 Utility Functions
# ------------------------------------------------------------

def clean_youtube_url(url: str) -> str:
    base = url.split("&")[0]
    base = base.split("?si=")[0]
    return base.strip()

def extract_video_id(url: str):
    m = re.search(r"(?:v=|be/)([0-9A-Za-z_-]{11})", url)
    return m.group(1) if m else None


# ------------------------------------------------------------
# 🎬 Transcript Fetchers
# ------------------------------------------------------------

def try_transcript_api(video_id):
    """Try YouTubeTranscriptApi first (fastest)"""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        return transcript, None
    except (TranscriptsDisabled, NoTranscriptFound):
        return None, "No transcript found"
    except Exception as e:
        return None, f"Transcript API error: {e}"

def try_yt_dlp_subtitles(video_url, video_id):
    """Fallback: use yt_dlp to download auto subtitles"""
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
    """Convert .vtt to readable text and timestamps"""
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


def fetch_captions(video_url):
    """Main function to get captions"""
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


# ------------------------------------------------------------
# 🧩 Groq Summarization
# ------------------------------------------------------------

def summarize_with_groq(text: str):
    """Summarize transcript using Groq LLM"""
    if not groq_client:
        return "Groq API key not found. Add it to Streamlit secrets."
    try:
        response = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",  # can also use "llama3-70b-8192"
            messages=[
                {"role": "system", "content": "You are a professional summarizer for educational YouTube videos."},
                {"role": "user", "content": f"Summarize this transcript in under 250 words:\n{text}"}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"(Groq summarization failed: {e})"


# ------------------------------------------------------------
# 🖥️ Streamlit UI
# ------------------------------------------------------------

st.set_page_config(page_title="🎥 YouTube Summarizer (Groq)", page_icon="🎯", layout="wide")
st.title("🎯 YouTube Video Summarizer + Timestamp Extractor (Groq Edition)")
st.markdown("Paste a YouTube video URL and extract timestamps, captions, and an AI summary using **Groq LLM**.")

url = st.text_input("🎥 Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=6Dh-RL__uN4")

if st.button("🚀 Extract Summary and Timestamps"):
    if not url.strip():
        st.warning("Please enter a valid YouTube link.")
    else:
        with st.spinner("Fetching transcript..."):
            segs, err = fetch_captions(url)
            if err:
                st.error(f"❌ {err}")
            elif not segs:
                st.warning("⚠️ No captions found.")
            else:
                # remove duplicates
                seen = OrderedDict()
                for s in segs:
                    if s["text"] not in seen:
                        seen[s["text"]] = s["start"]
                segs = [{"start": v, "text": k} for k, v in seen.items()]

                st.success(f"✅ Extracted {len(segs)} caption segments.")

                vid = extract_video_id(url)
                st.markdown("### 🕒 Clickable Captions")

                for s in segs:
                    t = s["start"].split(".")[0]
                    h, m, s_ = map(int, t.split(":"))
                    total = h * 3600 + m * 60 + s_
                    yt_link = f"https://www.youtube.com/watch?v={vid}&t={total}s"
                    st.markdown(f"- ⏱️ [{s['start']}] → [{s['text']}]({yt_link})")

                # summarize
                st.markdown("---")
                st.subheader("🧠 Groq AI Summary")
                all_text = " ".join([s["text"] for s in segs])
                summary = summarize_with_groq(all_text)
                st.write(summary)

st.markdown("---")
st.caption("Built with ❤️ by Selva Kumar using Groq API + YouTubeTranscriptAPI + Streamlit")

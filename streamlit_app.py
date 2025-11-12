# 🎯 YouTube Timestamp Extractor + Summarizer
# Author: My Smart Agent (Selva Kumar)
# Works fully on Streamlit Cloud

import streamlit as st
import re, os, tempfile, glob, shutil
import yt_dlp
from collections import OrderedDict

# Optional summarizer (choose whichever API you have)
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
        if not m: continue
        start = m.group(1)
        txt = re.sub(r".*-->\s.*\n", "", block).strip().replace("\n", " ")
        if txt:
            segs.append({"start": start, "text": txt})
    return segs


# ------------------------------------------------------------
# MAIN FETCH
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# SUMMARIZATION
# ------------------------------------------------------------

def summarize_text(text):
    if not client:
        # fallback simple heuristic summary
        sentences = text.split(".")
        return ". ".join(sentences[:5]) + "..."
    try:
        prompt = f"Summarize this YouTube video transcript in under 200 words:\n{text}"
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"(Summarization error: {e})"


# ------------------------------------------------------------
# STREAMLIT UI
# ------------------------------------------------------------

st.set_page_config(page_title="🎯 YouTube Timestamp Extractor", page_icon="🎥", layout="wide")
st.title("🎯 YouTube Timestamp Extractor + Summarizer")
st.markdown("Paste a YouTube video URL and get clickable caption timestamps + an AI summary!")

url = st.text_input("🎥 Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=6Dh-RL__uN4")

if st.button("🚀 Get Timestamps & Summary"):
    if not url.strip():
        st.warning("Please paste a valid YouTube link.")
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

                st.success(f"✅ Found {len(segs)} caption lines.")

                st.markdown("### 🕒 Clickable Timestamps")
                vid = extract_video_id(url)
                for s in segs:
                    # Convert "00:00:05.000" → seconds
                    t = s["start"].split(".")[0]
                    h, m, s_ = map(int, t.split(":"))
                    total = h * 3600 + m * 60 + s_
                    yt_link = f"https://www.youtube.com/watch?v={vid}&t={total}s"
                    st.markdown(f"- ⏱️ [{s['start']}] → [{s['text']}]({yt_link})")

                # Summarize
                all_text = " ".join([s["text"] for s in segs])
                st.markdown("---")
                st.subheader("🧠 Video Summary")
                summary = summarize_text(all_text)
                st.write(summary)

st.markdown("---")
st.caption("Built by Selva Kumar | Works with caption-enabled YouTube videos only.")

# 🎯 YouTube Timestamp Extractor + (Groq-ready)
# Features:
# ✅ Fetches captions and timestamps accurately
# ✅ Clickable links to YouTube at timestamp
# ✅ Clean layout
# ✅ Ready for Groq API summarization (next phase)

import streamlit as st
import re, tempfile, os, glob, shutil
import yt_dlp

try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
except Exception:
    YouTubeTranscriptApi = None
    TranscriptsDisabled = Exception
    NoTranscriptFound = Exception


# -------------------- Utility Functions --------------------

def clean_youtube_url(url: str) -> str:
    """Remove extra params like ?si=, &t= etc."""
    if not url:
        return url
    base = url.split("&")[0].split("?si=")[0]
    return base.strip()

def extract_video_id(url: str):
    """Extract video ID"""
    m = re.search(r"(?:v=|be/)([0-9A-Za-z_-]{11})", url)
    return m.group(1) if m else None

def time_to_seconds(t: str) -> float:
    """Convert 00:01:23.45 → 83.45 seconds"""
    parts = re.split("[:.]", t)
    parts = [float(p) for p in parts]
    if len(parts) == 4:
        h, m, s, ms = parts
        return h * 3600 + m * 60 + s + ms / 1000
    elif len(parts) == 3:
        h, m, s = parts
        return h * 3600 + m * 60 + s
    elif len(parts) == 2:
        m, s = parts
        return m * 60 + s
    else:
        return 0.0


# -------------------- Transcript Fetching --------------------

def try_transcript_api(video_id, lang_pref=["en"]):
    """Try fetching captions via YouTubeTranscriptApi"""
    if YouTubeTranscriptApi is None:
        return None, "Transcript API not installed"
    try:
        data = YouTubeTranscriptApi.get_transcript(video_id, languages=lang_pref)
        return data, None
    except (TranscriptsDisabled, NoTranscriptFound):
        return None, "Transcript not available"
    except Exception as e:
        return None, str(e)


def try_yt_dlp_subtitles(video_url, video_id, lang="en"):
    """Fallback using yt_dlp to get subtitles"""
    tmp = tempfile.mkdtemp()
    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [lang],
        "subtitlesformat": "vtt",
        "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
    except Exception as e:
        return None, f"yt_dlp error: {e}", tmp

    vtt_files = glob.glob(os.path.join(tmp, f"{video_id}*.vtt"))
    if not vtt_files:
        return None, "No VTT subtitle found", tmp
    return vtt_files[0], None, tmp


def parse_vtt(vtt_path):
    """Convert .vtt file → structured caption data"""
    segments = []
    text = open(vtt_path, "r", encoding="utf-8", errors="ignore").read()
    blocks = re.split(r"\n\n+", text.strip())
    for b in blocks:
        m = re.search(r"(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})", b)
        if not m:
            continue
        start, end = m.groups()
        start_s = time_to_seconds(start)
        end_s = time_to_seconds(end)
        caption = re.sub(r".*-->\s*.*\n", "", b).replace("\n", " ").strip()
        if caption:
            segments.append({
                "start": start_s,
                "end": end_s,
                "text": caption
            })
    return segments


def fetch_segments(url):
    """Main: Get transcript via API or yt_dlp"""
    url = clean_youtube_url(url)
    vid = extract_video_id(url)
    if not vid:
        return None, "Invalid YouTube URL"

    # Try Transcript API
    segs, err = try_transcript_api(vid)
    if segs:
        normalized = [{"start": s["start"], "end": s["start"] + s["duration"], "text": s["text"]} for s in segs]
        return normalized, None

    # Fallback yt_dlp
    vtt_path, err2, tmpdir = try_yt_dlp_subtitles(url, vid)
    if vtt_path:
        parsed = parse_vtt(vtt_path)
        shutil.rmtree(tmpdir, ignore_errors=True)
        if parsed:
            return parsed, None
        else:
            return None, "Parsed 0 lines"
    return None, err2


# -------------------- Streamlit Interface --------------------

st.set_page_config(page_title="🎯 YouTube Timestamp Extractor", layout="wide")

st.title("🎯 YouTube Timestamp Extractor")
st.write("Paste a YouTube link below to extract caption timestamps. Click on timestamps to jump to that part of the video.")

video_url = st.text_input("🔗 Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=6Dh-RL__uN4")

if st.button("🚀 Get timestamps"):
    if not video_url.strip():
        st.warning("Please enter a valid YouTube URL.")
    else:
        with st.spinner("Fetching video captions..."):
            segs, err = fetch_segments(video_url)
            if err:
                st.error(f"❌ {err}")
            elif not segs:
                st.warning("⚠️ No captions found.")
            else:
                st.success(f"✅ Found {len(segs)} caption segments.")
                st.markdown("### ⏱️ Captions and Timestamps")
                vid = extract_video_id(video_url)
                for s in segs:
                    mins, secs = divmod(int(s["start"]), 60)
                    link = f"https://youtu.be/{vid}?t={int(s['start'])}"
                    st.markdown(f"- [**{mins}:{secs:02d}**]({link}) → {s['text']}")

st.markdown("---")
st.caption("Built with ❤️ by My Smart Agent | Next update: Groq AI Summaries")
    

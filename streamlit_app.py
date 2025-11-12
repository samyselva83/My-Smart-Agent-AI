# 🎯 YouTube Timestamp Extractor
# Author: My Smart Agent (Selva)
# Features: Fetch captions & timestamps from YouTube video (auto/manual)
# Works on Streamlit Cloud — no ffmpeg or Whisper needed

import streamlit as st
import re, tempfile, os, glob, shutil
import yt_dlp

# Optional transcript API (used first)
try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
except Exception:
    YouTubeTranscriptApi = None
    TranscriptsDisabled = Exception
    NoTranscriptFound = Exception

# ----------------------------- UTILITIES -----------------------------

def clean_youtube_url(url: str) -> str:
    """Remove extra parameters (&t=, ?si=, etc.)"""
    if not url:
        return url
    base = url.split("&")[0]
    base = base.split("?si=")[0]
    return base.strip()

def extract_video_id(url: str):
    """Extract 11-char YouTube video ID"""
    m = re.search(r"(?:v=|be/)([0-9A-Za-z_-]{11})", url)
    return m.group(1) if m else None

# -------------------------- FETCH TRANSCRIPT --------------------------

def try_transcript_api(video_id, lang_pref=["en"]):
    """Attempt to fetch captions using youtube_transcript_api"""
    if YouTubeTranscriptApi is None:
        return None, "youtube_transcript_api not installed"
    try:
        if hasattr(YouTubeTranscriptApi, "list_transcripts"):
            tl = YouTubeTranscriptApi.list_transcripts(video_id)
            for lang in lang_pref:
                try:
                    t = tl.find_transcript([lang])
                    data = t.fetch()
                    return data, None
                except Exception:
                    continue
            t_any = tl.find_transcript([l.language_code for l in tl])
            return t_any.fetch(), None
        else:
            data = YouTubeTranscriptApi.get_transcript(video_id, languages=lang_pref)
            return data, None
    except TranscriptsDisabled:
        return None, "TranscriptsDisabled"
    except NoTranscriptFound:
        return None, "NoTranscriptFound"
    except Exception as e:
        return None, f"Transcript API error: {e}"

def try_yt_dlp_subtitles(video_url, video_id, lang="en"):
    """Fallback: use yt_dlp to fetch automatic captions (auto subs)"""
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

    vtt_files = glob.glob(os.path.join(tmp, f"{video_id}*.vtt")) + glob.glob(os.path.join(tmp, f"{video_id}*.srt"))
    if not vtt_files:
        return None, "No subtitle files found", tmp
    return vtt_files[0], None, tmp

def parse_vtt_to_segments(vtt_path):
    """Parse a .vtt subtitle file into structured caption segments"""
    segments = []
    if not os.path.exists(vtt_path):
        return segments
    text = open(vtt_path, "r", encoding="utf-8", errors="ignore").read()
    text = re.sub(r"WEBVTT.*\n", "", text, flags=re.IGNORECASE)
    blocks = re.split(r"\n\s*\n", text.strip())
    for b in blocks:
        m = re.search(r"(\d{1,2}:\d{2}:\d{2}\.\d{3}|\d{1,2}:\d{2}:\d{2})\s*-->\s*(\d{1,2}:\d{2}:\d{2}\.\d{3}|\d{1,2}:\d{2}:\d{2})", b)
        if not m:
            continue
        start_s, end_s = m.group(1), m.group(2)
        def t_to_secs(t):
            parts = list(map(float, re.findall(r"\d+", t)))
            if len(parts) == 3:
                return parts[0]*3600 + parts[1]*60 + parts[2]
            elif len(parts) == 2:
                return parts[0]*60 + parts[1]
            return 0
        start = t_to_secs(start_s)
        end = t_to_secs(end_s)
        dur = max(0, end-start)
        txt = re.sub(r".*-->\s*.*\n", "", b).strip()
        txt = re.sub(r"<[^>]+>", "", txt).replace("\n", " ").strip()
        if txt:
            segments.append({"start": start, "duration": dur, "text": txt})
    return segments

# ------------------------ MASTER FETCH FUNCTION ------------------------

def fetch_segments_for_url(url):
    """Master function to fetch transcript or fallback"""
    url_clean = clean_youtube_url(url)
    vid = extract_video_id(url_clean)
    if not vid:
        return None, "Could not extract video ID"

    # Try API first
    segs, err = try_transcript_api(vid, lang_pref=["en", "en-US", "en-GB"])
    if segs:
        normalized = [
            {"start": float(s.get("start", 0)), "duration": float(s.get("duration", 0)), "text": s.get("text", "").strip()}
            for s in segs
        ]
        return normalized, None

    # Fallback with yt_dlp
    vtt_path, err2, tmpdir = try_yt_dlp_subtitles(url_clean, vid)
    if vtt_path:
        try:
            parsed = parse_vtt_to_segments(vtt_path)
            if parsed:
                return parsed, None
            return None, "Parsed 0 segments from subtitle file"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    else:
        return None, f"yt_dlp fallback failed: {err2}"

# ----------------------------- STREAMLIT UI -----------------------------

st.set_page_config(page_title="YouTube Timestamp Extractor", page_icon="🎯", layout="wide")

st.title("🎯 YouTube Timestamp Extractor")
st.markdown("Paste a YouTube video link below to fetch caption timestamps. Click a timestamp to open YouTube at that point.")

video_url = st.text_input("🎥 Paste YouTube URL (full link):", placeholder="https://www.youtube.com/watch?v=6Dh-RL__uN4")

if st.button("🔍 Get timestamps"):
    if not video_url.strip():
        st.warning("Please enter a valid YouTube URL.")
    else:
        with st.spinner("Fetching captions and timestamps..."):
            segments, error = fetch_segments_for_url(video_url)
            if error:
                st.error(f"❌ {error}")
            elif not segments:
                st.warning("⚠️ No captions found or accessible for this video.")
            else:
                st.success(f"✅ Found {len(segments)} caption lines.")
                st.markdown("### 🕒 Captions and Timestamps")
                for seg in segments:
                    start = int(seg["start"])
                    mins, secs = divmod(start, 60)
                    txt = seg["text"]
                    link = f"https://www.youtube.com/watch?v={extract_video_id(video_url)}&t={start}s"
                    st.markdown(f"- [{mins}:{secs:02d}] → [{txt}]({link})")

st.markdown("---")
st.caption("Built with ❤️ by My Smart Agent | Supports public captioned videos only.")
        

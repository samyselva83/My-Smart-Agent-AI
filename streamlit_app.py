import streamlit as st
import re, os, tempfile, glob, shutil
import yt_dlp
from collections import OrderedDict

# ------------------------------------------------------------
# OpenAI client
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
# Utility
# ------------------------------------------------------------
def extract_video_id(url: str):
    m = re.search(r"(?:v=|be/)([0-9A-Za-z_-]{11})", url)
    return m.group(1) if m else None


def try_transcript_api(video_id):
    """Try fetching transcript using YouTubeTranscriptApi"""
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
    """Fallback: yt_dlp subtitles"""
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
    """Parse vtt -> clean segments"""
    text = open(vtt_path, "r", encoding="utf-8", errors="ignore").read()
    text = re.sub(r"WEBVTT.*\n", "", text, flags=re.IGNORECASE)
    blocks = re.split(r"\n\s*\n", text.strip())
    segs = []
    for block in blocks:
        m = re.search(r"(\d{2}:\d{2}:\d{2}\.\d{3})\s-->\s", block)
        if not m:
            continue
        start = m.group(1)
        txt = re.sub(r".*-->\s.*\n", "", block).strip()
        txt = re.sub(r"<[^>]+>", "", txt)
        txt = re.sub(r"align:start.*", "", txt)
        txt = re.sub(r"position:\d+%", "", txt)
        txt = re.sub(r"[^A-Za-z0-9.,?!'\" ]+", " ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        if txt:
            segs.append({"start": start, "text": txt})
    return segs


def clean_transcript_text(segs):
    """Combine and clean text for summary"""
    all_text = " ".join([s["text"] for s in segs])
    all_text = re.sub(r"\b(\w+)( \1\b)+", r"\1", all_text)  # remove repeated words
    all_text = re.sub(r"\s+", " ", all_text)
    return all_text.strip()


# ------------------------------------------------------------
# Summarization
# ------------------------------------------------------------
def summarize_text(clean_text):
    """Short, human-style summary"""
    if not client:
        return "AI summary unavailable — please configure OpenAI API key."
    try:
        prompt = (
            "Summarize the following YouTube transcript in about 120 words. "
            "Focus on main ideas, avoid repetition and technical artifacts.\n\n"
            f"Transcript:\n{clean_text[:7000]}"
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.5,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Summarization error: {e}"


# ------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------
st.set_page_config(page_title="🤖 My Smart Agent", page_icon="🧠", layout="wide")

st.sidebar.title("🧭 Navigation")
choice = st.sidebar.radio(
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

# Other sections (placeholders)
if choice != "🎥 Video Summary":
    st.title(choice)
    st.info("✨ This module is under development.")
else:
    st.title("🎥 YouTube Video Summarizer + Timestamp Highlights")
    url = st.text_input("🎬 Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=YOUR_VIDEO_ID")

    if st.button("🚀 Summarize Video"):
        if not url:
            st.warning("Please enter a valid YouTube link.")
        else:
            with st.spinner("⏳ Extracting transcript and generating summary..."):
                video_id = extract_video_id(url)
                if not video_id:
                    st.error("Invalid YouTube link.")
                else:
                    segs, err = try_transcript_api(video_id)
                    if not segs:
                        vtt_path, err2, tmpdir = try_yt_dlp_subtitles(url, video_id)
                        if vtt_path:
                            segs = parse_vtt(vtt_path)
                            shutil.rmtree(tmpdir, ignore_errors=True)
                        else:
                            st.error(f"❌ {err2}")
                            segs = None

                    if not segs:
                        st.error("⚠️ No transcript found or captions unavailable.")
                    else:
                        clean_text = clean_transcript_text(segs)
                        summary = summarize_text(clean_text)
                        st.subheader("🧠 AI Summary of the Video")
                        st.write(summary)

                        # Generate key moments
                        st.markdown("---")
                        st.subheader("🕒 Key Moments")
                        n = len(segs)
                        step = max(1, n // 5)
                        labels = ["Introduction", "Main Concept", "Example", "Discussion", "Conclusion"]

                        for i, s in enumerate(segs[::step][:5]):
                            start = s["start"].split(".")[0]
                            h, m, sec = map(int, start.split(":"))
                            total = h * 3600 + m * 60 + sec
                            yt_link = f"https://www.youtube.com/watch?v={video_id}&t={total}s"
                            st.markdown(f"- [{m:02d}:{sec:02d}] → [{labels[i]}]({yt_link})")

    st.caption("⚙️ Built by Selva Kumar — works only for videos with captions enabled.")

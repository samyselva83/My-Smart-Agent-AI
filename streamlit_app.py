import streamlit as st
import re, os, tempfile, glob, shutil
import yt_dlp
from groq import Groq
from collections import OrderedDict

# ------------------------------------------------------------
# Initialize Groq client
# ------------------------------------------------------------
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    client = None
    st.error("⚠️ Groq API key missing. Please add GROQ_API_KEY in Streamlit Secrets.")

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
    """Fallback using yt_dlp"""
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
    """Parse .vtt captions"""
    text = open(vtt_path, "r", encoding="utf-8", errors="ignore").read()
    text = re.sub(r"WEBVTT.*\n", "", text)
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
    """Combine and clean text"""
    all_text = " ".join([s["text"] for s in segs])
    all_text = re.sub(r"\b(\w+)( \1\b)+", r"\1", all_text)
    all_text = re.sub(r"\s+", " ", all_text)
    return all_text.strip()


# ------------------------------------------------------------
# Summarization via Groq
# ------------------------------------------------------------
def summarize_text_with_groq(clean_text, language="English"):
    """Summarize YouTube transcript in selected language"""
    if not client:
        return "⚠️ Groq API not configured."
    try:
        prompt = (
            f"Summarize the following YouTube transcript in about 120 words. "
            f"The summary must be written in **{language}**. "
            "Focus on the main ideas, purpose, and topics. "
            "Avoid repetition, timestamps, or filler text.\n\n"
            f"Transcript:\n{clean_text[:7000]}"
        )
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Groq summarization error: {e}"


# ------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------
st.set_page_config(page_title="🤖 My Smart Agent", page_icon="🧠", layout="wide")

st.sidebar.title("🧭 Navigation")
choice = st.sidebar.radio(
    "Select Module:",
    [
        "🗓️ Daily Planner (AI)",
        "💵 Finance Tracker",
        "💪 Health & Habit",
        "🧠 LearnMate",
        "🧾 Memory",
        "🎥 Video Summary",
    ],
)

if choice != "🎥 Video Summary":
    st.title(choice)
    st.info("✨ This module is under development.")
else:
    st.title("🎥 YouTube Video Summarizer + Multilingual Highlights")

    url = st.text_input("🎬 Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=VIDEO_ID")

    lang = st.selectbox(
        "🌍 Select Summary Language:",
        [
            "English",
            "Tamil",
            "Telugu",
            "Malayalam",
            "Kannada",
            "Hindi",
            "French",
            "Spanish",
            "German",
            "Japanese",
        ],
        index=0,
    )

    if st.button("🚀 Generate Multilingual Summary"):
        if not url.strip():
            st.warning("Please paste a valid YouTube link.")
        else:
            with st.spinner("⏳ Fetching transcript and generating summary..."):
                video_id = extract_video_id(url)
                if not video_id:
                    st.error("Invalid YouTube URL.")
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
                        st.warning("⚠️ No captions found or unavailable.")
                    else:
                        clean_text = clean_transcript_text(segs)
                        summary = summarize_text_with_groq(clean_text, lang)

                        st.subheader(f"🧠 AI Summary ({lang})")
                        st.write(summary)

                        # Key timestamps
                        st.markdown("---")
                        st.subheader("🕒 Key Highlights")
                        n = len(segs)
                        step = max(1, n // 5)
                        labels = ["Introduction", "Main Topic", "Example", "Analysis", "Conclusion"]

                        for i, s in enumerate(segs[::step][:5]):
                            start = s["start"].split(".")[0]
                            h, m, sec = map(int, start.split(":"))
                            total = h * 3600 + m * 60 + sec
                            yt_link = f"https://www.youtube.com/watch?v={video_id}&t={total}s"
                            st.markdown(f"- [{m:02d}:{sec:02d}] → [{labels[i]}]({yt_link})")

    st.caption("⚙️ Built by Selva Kumar — multilingual summarization powered by Groq API.")

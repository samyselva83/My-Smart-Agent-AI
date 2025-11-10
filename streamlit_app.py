# streamlit_app.py — My Smart Agent (Video Summarizer + Timestamp Highlighter)
# ✅ Groq API Stable Version for Streamlit Cloud

import os, re
import streamlit as st
from pytube import YouTube
from datetime import timedelta
import imageio_ffmpeg
from groq import Groq

# Optional: handle YouTube transcript API safely
try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
except ImportError:
    YouTubeTranscriptApi = None
    TranscriptsDisabled = Exception

# --------------------------------------------------------
# 🔧 Configure FFmpeg (works on Streamlit Cloud)
# --------------------------------------------------------
os.environ["PATH"] += os.pathsep + os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
st.info(f"✅ FFmpeg registered: {imageio_ffmpeg.get_ffmpeg_exe()}")

# --------------------------------------------------------
# 🔑 Groq API setup
# --------------------------------------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", None)
if not GROQ_API_KEY:
    st.warning("⚠️ Please add your GROQ_API_KEY in Streamlit → Settings → Secrets")
client = Groq(api_key=GROQ_API_KEY)

# --------------------------------------------------------
# ⏱️ Helper to convert timestamps
# --------------------------------------------------------
def convert_to_seconds(time_str):
    """Convert 00:00:00 format to total seconds."""
    parts = list(map(int, time_str.split(":")))
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    else:
        return 0
    return h * 3600 + m * 60 + s

# --------------------------------------------------------
# 🤖 Groq Summarization (fixed model)
# --------------------------------------------------------
def summarize_text_groq(text, language="English"):
    """Summarize transcript text using Groq API (llama-3.2-3b-preview)."""
    if not text or len(text.strip()) == 0:
        return "⚠️ No transcript text found to summarize."

    try:
        prompt = (
            f"Summarize the following YouTube transcript in {language}. "
            f"Highlight important moments and timestamps where possible:\n\n{text[:5000]}"
        )

        # ✅ Use valid model (as of Nov 2025)
        response = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=900,
        )

        if hasattr(response, "choices") and response.choices:
            return response.choices[0].message.content.strip()
        return "⚠️ Groq returned an empty response. Try again."

    except Exception as e:
        return f"Groq summarization error: {e}"

# --------------------------------------------------------
# 📜 Transcript Extraction
# --------------------------------------------------------
def get_youtube_transcript(video_id, lang="en"):
    """Fetch transcript using YouTubeTranscriptApi with backward compatibility."""
    if YouTubeTranscriptApi is None:
        raise Exception("YouTubeTranscriptApi not available in this environment.")

    try:
        if hasattr(YouTubeTranscriptApi, "list_transcripts"):
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_transcript([lang])
            data = transcript.fetch()
        else:
            data = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
        text = " ".join([x["text"] for x in data])
        return text
    except TranscriptsDisabled:
        raise Exception("Subtitles are disabled for this video.")
    except Exception as e:
        raise Exception(f"Transcript fetch failed: {e}")

# --------------------------------------------------------
# 🎬 Video Summarizer UI
# --------------------------------------------------------
def video_summarizer_ui():
    st.title("🎬 Video Summarizer — Multilingual AI Highlights")
    st.caption("Summarizes YouTube videos with timestamps and language translation support.")

    # --- Inputs ---
    video_url = st.text_input("📺 Paste YouTube URL", placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    lang_choice = st.selectbox("🌍 Choose summary language", ["English", "Tamil", "Hindi", "Spanish", "French", "German"])

    # --- Main action ---
    if st.button("✨ Summarize Video"):
        if not video_url:
            st.error("Please enter a valid YouTube URL.")
            return

        with st.spinner("Fetching video info and captions..."):
            try:
                yt = YouTube(video_url)
                video_id = yt.video_id
                title = yt.title
                channel = yt.author
                duration = str(timedelta(seconds=yt.length))
                thumb = yt.thumbnail_url

                st.image(thumb, caption=f"🎞️ {title} — {channel} ({duration})")

                # Try to fetch transcript
                try:
                    st.info("Attempting to fetch YouTube transcript...")
                    transcript = get_youtube_transcript(video_id, lang="en")
                    st.success("✅ Transcript fetched successfully.")
                except Exception as e:
                    st.warning(f"Transcript not available: {e}")
                    transcript = None

                if not transcript:
                    st.error("❌ No transcript found — please try a different video with captions.")
                    return

                # Summarize via Groq
                st.info("🧠 Generating AI summary using Groq...")
                summary = summarize_text_groq(transcript, lang_choice)

                # Make timestamps clickable
                summary = re.sub(
                    r'(\b\d{1,2}:\d{2}(?::\d{2})?)',
                    lambda m: f"[{m.group(1)}](https://www.youtube.com/watch?v={video_id}&t={convert_to_seconds(m.group(1))}s)",
                    summary,
                )

                # Display output
                st.subheader("🧠 AI Summary")
                st.markdown(summary)

            except Exception as e:
                st.error(f"❌ Error while summarizing: {e}")

# --------------------------------------------------------
# 🧭 Sidebar Navigation
# --------------------------------------------------------
def main():
    st.sidebar.title("🧭 My Smart Agent Menu")
    choice = st.sidebar.radio(
        "Choose a module",
        [
            "Dashboard",
            "Daily Planner (AI)",
            "Finance Tracker",
            "Health & Habits",
            "LearnMate",
            "Memory",
            "Video Summarizer",
        ],
    )

    if choice == "Video Summarizer":
        video_summarizer_ui()
    else:
        st.info("🚧 Other modules (Planner, Finance, etc.) are under development.")

if __name__ == "__main__":
    main()

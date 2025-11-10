# streamlit_app.py — My Smart Agent (Robust Video Summarizer)

import os, re, tempfile
import streamlit as st
from pytube import YouTube
from groq import Groq
import imageio_ffmpeg
from datetime import timedelta

# ✅ Try importing YouTube transcript API safely
try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
except ImportError:
    YouTubeTranscriptApi = None
    TranscriptsDisabled = Exception

# ✅ Register ffmpeg for Streamlit Cloud
os.environ["PATH"] += os.pathsep + os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
st.success(f"✅ FFmpeg binary ready: {imageio_ffmpeg.get_ffmpeg_exe()}")

# -------------------------------
# 🧠 Groq API setup
# -------------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", None)
if not GROQ_API_KEY:
    st.warning("⚠️ Please set your GROQ_API_KEY in Streamlit → Settings → Secrets")
client = Groq(api_key=GROQ_API_KEY)

# -------------------------------
# 🔢 Helper: Convert timestamp
# -------------------------------
def convert_to_seconds(time_str):
    parts = list(map(int, time_str.split(":")))
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    else:
        return 0
    return h * 3600 + m * 60 + s

# -------------------------------
# 🧩 Groq Summarization
# -------------------------------
def summarize_text_groq(text, language="English"):
    try:
        prompt = f"Summarize this YouTube video transcript in {language}. Include timestamps:\n\n{text[:6000]}"
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=900
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Groq summarization error: {e}"

# -------------------------------
# 🧾 Transcript Extraction
# -------------------------------
def get_youtube_transcript(video_id, lang="en"):
    if YouTubeTranscriptApi is None:
        raise Exception("YouTubeTranscriptApi not available.")

    try:
        # ✅ Try the latest method first
        if hasattr(YouTubeTranscriptApi, "list_transcripts"):
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_transcript([lang])
            data = transcript.fetch()
        else:
            # ✅ Compatibility for older versions
            data = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
        text = " ".join([x["text"] for x in data])
        return text
    except TranscriptsDisabled:
        raise Exception("Subtitles are disabled for this video.")
    except Exception as e:
        raise Exception(f"Transcript fetch failed: {e}")

# -------------------------------
# 🧠 Video Summarizer
# -------------------------------
def video_summarizer_ui():
    st.title("🎬 Video Summarizer — AI Highlights with Clickable Timestamps")
    st.info("Paste a YouTube link to generate smart highlights and summaries in your chosen language.")

    video_url = st.text_input("📺 Paste YouTube URL", placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    lang_choice = st.selectbox("🌍 Summary Language", ["English", "Tamil", "Hindi", "Spanish", "French", "German"])

    if st.button("✨ Summarize Video"):
        if not video_url:
            st.error("Please enter a valid YouTube URL.")
            return

        with st.spinner("Fetching video details..."):
            try:
                yt = YouTube(video_url)
                video_id = yt.video_id
                title = yt.title
                channel = yt.author
                duration = str(timedelta(seconds=yt.length))
                thumb = yt.thumbnail_url

                st.image(thumb, caption=f"🎞️ {title} — {channel} ({duration})")

                try:
                    st.info("Attempting to fetch YouTube transcript...")
                    transcript = get_youtube_transcript(video_id, lang="en")
                except Exception as e:
                    st.warning(f"Transcript not available: {e}")
                    transcript = None

                if not transcript:
                    st.error("❌ No transcript found — try a different video.")
                    return

                summary = summarize_text_groq(transcript, lang_choice)

                # Make timestamps clickable
                summary = re.sub(
                    r'(\b\d{1,2}:\d{2}(?::\d{2})?)',
                    lambda m: f"[{m.group(1)}](https://www.youtube.com/watch?v={video_id}&t={convert_to_seconds(m.group(1))}s)",
                    summary
                )

                st.subheader("🧠 AI Summary")
                st.markdown(summary)

            except Exception as e:
                st.error(f"❌ Error while summarizing: {e}")

# -------------------------------
# 🚀 Main App
# -------------------------------
def main():
    st.sidebar.title("🧭 My Smart Agent Menu")
    choice = st.sidebar.radio(
        "Choose a module",
        ["Dashboard", "Daily Planner (AI)", "Finance Tracker", "Health & Habits", "LearnMate", "Memory", "Video Summarizer"]
    )

    if choice == "Video Summarizer":
        video_summarizer_ui()
    else:
        st.info("🚧 Other modules (Planner, Finance, etc.) are in development.")

if __name__ == "__main__":
    main()

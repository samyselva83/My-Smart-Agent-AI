# streamlit_app.py — My Smart Agent (Video Summarizer fixed version)

import os, re, tempfile
import streamlit as st
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from groq import Groq
import imageio_ffmpeg
from datetime import timedelta

# -------------------------------
# ✅ Auto-register ffmpeg path
# -------------------------------
os.environ["PATH"] += os.pathsep + os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
st.success(f"✅ FFmpeg registered: {imageio_ffmpeg.get_ffmpeg_exe()}")

# -------------------------------
# 🧠 Groq API setup
# -------------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", None)
if not GROQ_API_KEY:
    st.warning("⚠️ Please set your GROQ_API_KEY in Streamlit → Settings → Secrets")
client = Groq(api_key=GROQ_API_KEY)

# -------------------------------
# 🧮 Utility: Convert timestamp
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
# 🧩 Summarization via Groq
# -------------------------------
def summarize_text_groq(text, language="English"):
    try:
        prompt = f"Summarize this YouTube video transcript in {language}. Include clickable timestamps where appropriate:\n\n{text[:6000]}"
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=800
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Groq summarization error: {e}"

# -------------------------------
# 🎬 Extract clean YouTube ID
# -------------------------------
def extract_video_id(url):
    pattern = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    raise ValueError("Invalid YouTube URL format. Please check and try again.")

# -------------------------------
# 📜 Get transcript
# -------------------------------
def get_youtube_transcript(video_id, lang="en"):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript([lang])
        data = transcript.fetch()
        text = " ".join([x["text"] for x in data])
        return text
    except TranscriptsDisabled:
        raise Exception("Transcripts are disabled for this video.")
    except Exception as e:
        raise Exception(f"Transcript fetch failed: {e}")

# -------------------------------
# 🎥 Video Summarizer UI
# -------------------------------
def video_summarizer_ui():
    st.title("🎬 Video Summarizer — Multilingual AI Highlights with Clickable Timestamps")
    st.info("Paste a YouTube link or upload a local video file to summarize.")

    col1, col2 = st.columns(2)
    with col1:
        video_url = st.text_input("📺 Paste YouTube URL", placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    with col2:
        upload_file = st.file_uploader("📤 Or upload a local video (.mp4/.mkv)", type=["mp4", "mkv"])

    lang_choice = st.selectbox("🌍 Summary language", ["English", "Spanish", "French", "German", "Tamil", "Hindi"])

    if st.button("✨ Summarize Video"):
        with st.spinner("Processing video... please wait ⏳"):
            try:
                if upload_file:
                    st.warning("Local video summarization (Whisper) under development on Streamlit Cloud.")
                    return

                if not video_url:
                    st.error("Please provide a valid YouTube link.")
                    return

                clean_url = video_url.strip().split("&")[0]  # remove tracking params
                video_id = extract_video_id(clean_url)

                try:
                    yt = YouTube(clean_url)
                    title = yt.title
                    author = yt.author
                    duration = str(timedelta(seconds=yt.length))
                    thumbnail = yt.thumbnail_url
                    st.image(thumbnail, caption=f"🎞️ {title} — {author} ({duration})")
                except Exception as e:
                    st.warning(f"⚠️ Could not load video metadata: {e}")

                # Get transcript
                st.info("Attempting to fetch captions...")
                transcript = get_youtube_transcript(video_id, lang="en")

                st.success("✅ Captions fetched successfully!")

                summary = summarize_text_groq(transcript, language=lang_choice)

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
    st.sidebar.markdown("🌐 Language")
    st.sidebar.selectbox("", ["English", "Spanish", "French", "Tamil", "Hindi"])

    if choice == "Video Summarizer":
        video_summarizer_ui()
    else:
        st.info("🚧 Other modules (Planner, Finance, etc.) are under development.")

if __name__ == "__main__":
    main()

# streamlit_app.py — My Smart Agent (Video Summarizer Version)

import os
import tempfile
import streamlit as st
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from groq import Groq
import imageio_ffmpeg
import openai
from datetime import timedelta

# -------------------------------
# ✅ Auto-register ffmpeg path
# -------------------------------
os.environ["PATH"] += os.pathsep + os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
st.success(f"✅ FFmpeg binary registered: {imageio_ffmpeg.get_ffmpeg_exe()}")

# -------------------------------
# 🧠 Groq API setup (replace with your valid key)
# -------------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", None)
if not GROQ_API_KEY:
    st.warning("⚠️ Please add your GROQ_API_KEY in Streamlit → Settings → Secrets")
client = Groq(api_key=GROQ_API_KEY)

# -------------------------------
# 🎬 YouTube transcript fetcher
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
# 🧩 Helper: Summarize text via Groq
# -------------------------------
def summarize_text_groq(text, language="English"):
    try:
        prompt = f"Summarize this YouTube video in {language}. Include timestamps if possible:\n\n{text[:6000]}"
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
# 🎥 Main Video Summarizer logic
# -------------------------------
def video_summarizer_ui():
    st.title("🎬 Video Summarizer — Multilingual AI Highlights with Clickable Timestamps")
    st.info("Paste a YouTube link or upload a video file to generate an AI-based summary with highlights.")

    col1, col2 = st.columns(2)
    with col1:
        video_url = st.text_input("📺 Paste YouTube URL (example: https://www.youtube.com/watch?v=dQw4w9WgXcQ)")
    with col2:
        upload_file = st.file_uploader("📤 Or upload a local video (.mp4/.mkv)", type=["mp4", "mkv"])

    lang_choice = st.selectbox("🌍 Select language for summary", ["English", "Spanish", "French", "German", "Tamil", "Hindi"])

    if st.button("✨ Summarize Video"):
        with st.spinner("Processing video, please wait..."):
            try:
                # 🎞️ If user uploaded a file
                if upload_file:
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                    temp_file.write(upload_file.read())
                    st.video(temp_file.name)
                    text = "Transcription for local videos under development (Whisper not yet enabled on Streamlit Cloud)."
                    st.warning(text)
                    return

                # 🎞️ If YouTube URL given
                if video_url:
                    yt = YouTube(video_url)
                    video_id = yt.video_id
                    title = yt.title
                    author = yt.author
                    length = str(timedelta(seconds=yt.length))
                    thumb = yt.thumbnail_url

                    st.image(thumb, caption=f"🎥 {title} — {author} ({length})")
                    st.write("Attempting to fetch captions...")

                    transcript = get_youtube_transcript(video_id, lang="en")
                    if not transcript:
                        st.warning("No captions found — fallback to Whisper will be added later.")
                        return

                    st.success("✅ Captions fetched successfully!")

                    # Summarize using Groq
                    summary = summarize_text_groq(transcript, language=lang_choice)

                    # 🕒 Add clickable timestamps (pattern like 00:01:23 → link)
                    summary = re.sub(
                        r'(\b\d{1,2}:\d{2}(?::\d{2})?)',
                        lambda m: f"[{m.group(1)}](https://www.youtube.com/watch?v={video_id}&t={convert_to_seconds(m.group(1))}s)",
                        summary
                    )

                    st.subheader("🧠 AI Summary")
                    st.markdown(summary)

                else:
                    st.error("Please provide a YouTube link or upload a file.")

            except Exception as e:
                st.error(f"❌ Error while summarizing: {e}")

# -------------------------------
# 🧮 Time helper
# -------------------------------
import re
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
# 🚀 Main App
# -------------------------------
def main():
    st.sidebar.title("🧭 My Smart Agent Menu")
    modules = [
        "Dashboard",
        "Daily Planner (AI)",
        "Finance Tracker",
        "Health & Habits",
        "LearnMate",
        "Memory",
        "Video Summarizer"
    ]
    choice = st.sidebar.radio("Choose a module", modules)
    st.sidebar.markdown("🌐 Language")
    st.sidebar.selectbox("", ["English", "Spanish", "French", "Tamil", "Hindi"])

    if choice == "Video Summarizer":
        video_summarizer_ui()
    else:
        st.info("🚧 Other modules (Planner, Finance, etc.) under development.")

# Run app
if __name__ == "__main__":
    main()

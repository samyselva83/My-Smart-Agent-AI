import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import yt_dlp
import re

st.set_page_config(page_title="🎯 YouTube Timestamp Extractor", page_icon="🎬", layout="centered")

st.title("🎯 YouTube Timestamp Extractor")
st.write("Paste a YouTube video URL below — this tool extracts caption timestamps if available.")

# Input URL
url = st.text_input("📺 Paste YouTube URL (full link):", placeholder="https://www.youtube.com/watch?v=VIDEO_ID")

def extract_video_id(link):
    match = re.search(r"(?:v=|be/)([0-9A-Za-z_-]{11})", link)
    return match.group(1) if match else None

# When user submits
if st.button("🔍 Get timestamps"):
    if not url.strip():
        st.warning("Please paste a valid YouTube URL.")
    else:
        video_id = extract_video_id(url)
        if not video_id:
            st.error("Invalid YouTube URL — cannot extract video ID.")
        else:
            st.info(f"Fetching video details for ID: `{video_id}` ...")

            # --- Step 1: Try fetching metadata safely ---
            try:
                ydl_opts = {'quiet': True, 'skip_download': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                    title = info.get("title", "Unknown Title")
                    uploader = info.get("uploader", "Unknown Channel")
                    duration = info.get("duration", 0)
                    thumbnail = info.get("thumbnail", None)
            except Exception as e:
                title, uploader, duration, thumbnail = "Unknown Title", "Unknown Channel", 0, None
                st.warning(f"⚠️ Could not fetch full metadata: {e}")

            # --- Display video info ---
            st.subheader("🎥 Video Details")
            st.markdown(f"**Title:** {title}")
            st.markdown(f"**Uploader:** {uploader}")
            st.markdown(f"**Duration:** {duration//60}:{duration%60:02d} mins")
            if thumbnail:
                st.image(thumbnail, use_container_width=True)

            # --- Step 2: Try fetching captions ---
            st.info("🗒️ Attempting to fetch captions (English preferred)...")

            try:
                transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
                transcript = None
                for tr in transcripts:
                    if tr.language_code.startswith("en"):
                        transcript = tr.fetch()
                        break
                if not transcript:
                    transcript = transcripts.find_manually_created_transcript(["en"]).fetch()

                # --- Step 3: Display timestamps ---
                st.success("✅ Captions fetched successfully!")
                st.subheader("🕒 Caption Segments with Clickable Timestamps")

                for seg in transcript:
                    start = int(seg['start'])
                    text = seg['text']
                    link = f"https://www.youtube.com/watch?v={video_id}&t={start}s"
                    st.markdown(f"[{start//60}:{start%60:02d}] → [{text}]({link})")

            except (TranscriptsDisabled, NoTranscriptFound):
                st.error("❌ Captions not available for this video.")
            except Exception as e:
                st.error(f"⚠️ Transcript fetch failed: {e}")
    

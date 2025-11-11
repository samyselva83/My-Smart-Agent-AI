import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import yt_dlp
import re

st.set_page_config(page_title="🎯 YouTube Timestamp Extractor", page_icon="🎬", layout="centered")

st.title("🎯 YouTube Timestamp Extractor")
st.write(
    "Paste a YouTube video URL below — if captions are available, "
    "this tool will list caption segments with clickable timestamps."
)

# Input URL
url = st.text_input("📺 Paste YouTube URL (full link):", placeholder="https://www.youtube.com/watch?v=VIDEO_ID")

def extract_video_id(link):
    """Extract YouTube video ID from URL"""
    match = re.search(r"(?:v=|be/)([0-9A-Za-z_-]{11})", link)
    return match.group(1) if match else None


if st.button("🔍 Get timestamps"):
    if not url.strip():
        st.warning("Please paste a valid YouTube URL.")
    else:
        video_id = extract_video_id(url)
        if not video_id:
            st.error("Invalid YouTube URL — cannot extract video ID.")
        else:
            st.info(f"Fetching details for video ID: `{video_id}` ...")

            # Step 1: Metadata using yt_dlp
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
                st.warning(f"⚠️ Could not fetch some metadata: {str(e)[:200]}")

            # Display video details
            st.subheader("🎥 Video Details")
            st.markdown(f"**Title:** {title}")
            st.markdown(f"**Uploader:** {uploader}")
            st.markdown(f"**Duration:** {duration//60}:{duration%60:02d} mins")
            if thumbnail:
                st.image(thumbnail, use_container_width=True)

            # Step 2: Try fetching captions
            st.info("🗒️ Attempting to fetch captions (English preferred)...")

            try:
                transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
                transcript = None

                # Prefer English captions
                for tr in transcripts:
                    if "en" in tr.language_code:
                        transcript = tr.fetch()
                        break

                if not transcript:
                    st.warning("⚠️ No English captions found. Trying any available language...")
                    transcript = transcripts.find_transcript(transcripts._manually_created_transcripts.keys()).fetch()

                # Step 3: Display clickable timestamps
                if transcript:
                    st.success("✅ Captions fetched successfully!")
                    st.subheader("🕒 Caption Segments with Clickable Timestamps")

                    for seg in transcript:
                        start = int(seg["start"])
                        text = seg["text"]
                        link = f"https://www.youtube.com/watch?v={video_id}&t={start}s"
                        st.markdown(f"[{start//60}:{start%60:02d}] → [{text}]({link})")
                else:
                    st.error("❌ No captions found for this video.")

            except (TranscriptsDisabled, NoTranscriptFound):
                st.error("❌ This video has no captions available (disabled or auto-subtitles not public).")
            except Exception as e:
                if "no element found" in str(e):
                    st.error("⚠️ Could not fetch captions: Captions may be disabled or the API cannot access this video.")
                else:
                    st.error(f"❌ Transcript fetch failed: {str(e)[:200]}")
                        

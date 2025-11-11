# video_timestamps_app.py
# Minimal reliable YouTube details + timestamp extractor (Streamlit)
import re
import streamlit as st
from pytube import YouTube
import datetime

# Try import of youtube_transcript_api with compatibility handling
try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
except Exception:
    YouTubeTranscriptApi = None
    TranscriptsDisabled = Exception

st.set_page_config(page_title="YouTube Timestamp Extractor", layout="wide")
st.title("🎯 YouTube Timestamp Extractor")

st.markdown(
    "Paste a YouTube watch URL and — if captions are available — "
    "this tool will list caption segments and timestamps (click to open YouTube at that time)."
)

# Input
video_url = st.text_input("Paste YouTube URL (full watch link):", placeholder="https://www.youtube.com/watch?v=VIDEO_ID")
fetch_btn = st.button("Get timestamps")

def extract_video_id(url: str):
    """Extract a YouTube video id from common URL formats."""
    if not url:
        return None
    # remove parameters after & and fragments
    url = url.strip()
    # try several patterns
    patterns = [
        r"(?:v=)([0-9A-Za-z_-]{11})",    # watch?v=
        r"(?:be/)([0-9A-Za-z_-]{11})",   # youtu.be/
        r"(?:embed/)([0-9A-Za-z_-]{11})",# embed/
        r"(?:shorts/)([0-9A-Za-z_-]{11})",# shorts/
        r"^([0-9A-Za-z_-]{11})$"         # raw id
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    # fallback: try to parse after last /
    parts = url.split("/")
    last = parts[-1]
    if len(last) >= 11:
        return last[:11]
    return None

def seconds_to_hms(s: float) -> str:
    s = int(round(s))
    return str(datetime.timedelta(seconds=s))

def fetch_captions(video_id: str, lang_priority: list = ["en"]):
    """
    Attempt to fetch captions with compatibility for different youtube_transcript_api versions.
    Returns list of segments: [{'start': float, 'duration': float, 'text': str}, ...]
    Raises Exception with message if cannot fetch.
    """
    if YouTubeTranscriptApi is None:
        raise Exception("youtube_transcript_api library not installed in environment.")
    # try modern API first, otherwise fallback to older methods
    try:
        # prefer list_transcripts if available
        if hasattr(YouTubeTranscriptApi, "list_transcripts"):
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            # try to find transcript in preferred languages
            for lang in lang_priority:
                try:
                    t = transcript_list.find_transcript([lang])
                    segs = t.fetch()
                    return segs
                except Exception:
                    continue
            # if no preferred languages found, try first available
            try:
                first = transcript_list.find_transcript(transcript_list._transcripts.keys())
                return first.fetch()
            except Exception:
                # last resort: list_transcripts returns transcripts but fetch failed
                pass
        # fallback: older method
        try:
            segs = YouTubeTranscriptApi.get_transcript(video_id)
            return segs
        except Exception as e:
            raise Exception(f"Could not retrieve transcript: {e}")
    except TranscriptsDisabled:
        raise Exception("Subtitles are disabled for this video.")
    except Exception as e:
        raise Exception(f"Transcript fetch failed: {e}")

if fetch_btn:
    if not video_url:
        st.error("Please paste a YouTube watch URL.")
    else:
        vid = extract_video_id(video_url)
        if not vid:
            st.error("Could not extract a video id from the provided URL. Please check the URL.")
        else:
            st.info(f"Video ID: `{vid}` — fetching metadata...")
            # fetch metadata via pytube (safe)
            try:
                yt = YouTube(f"https://www.youtube.com/watch?v={vid}")
                st.subheader("Video details")
                st.write("**Title:**", yt.title)
                st.write("**Channel:**", yt.author)
                try:
                    st.write("**Duration:**", f"{yt.length//60}m {yt.length%60}s")
                except Exception:
                    pass
                # show thumbnail if available
                try:
                    st.image(yt.thumbnail_url, width=480)
                except Exception:
                    pass
            except Exception as e:
                st.warning(f"Could not fetch some metadata: {e}")

            st.info("Attempting to fetch captions (English preferred)...")
            try:
                segments = fetch_captions(vid, lang_priority=["en", "en-US", "en-GB"])
                if not segments or len(segments) == 0:
                    st.warning("No caption segments returned.")
                else:
                    st.success(f"Found {len(segments)} caption segments. Showing first 200 segments (if any).")
                    # show as a table with clickable links
                    rows = []
                    for i, seg in enumerate(segments[:200]):  # limit to 200 segments for UI safety
                        start = float(seg.get("start", 0.0))
                        dur = float(seg.get("duration", 0.0))
                        text = seg.get("text", "").strip()
                        hms = seconds_to_hms(start)
                        # link to YouTube with t=seconds
                        link = f"https://www.youtube.com/watch?v={vid}&t={int(start)}s"
                        rows.append((i+1, hms, f"{int(dur)}s", text, link))
                    # display as interactive
                    st.markdown("### Caption segments (click timestamp to open YouTube at that moment)")
                    for idx, hms, dur, text, link in rows:
                        st.markdown(f"- [{hms}]({link}) — ({dur})  —  {st.write(text) if False else text}")
                    # also provide downloadable CSV
                    import csv, io
                    csv_buf = io.StringIO()
                    writer = csv.writer(csv_buf)
                    writer.writerow(["index","start_hms","duration_s","text","youtube_link"])
                    for r in rows:
                        writer.writerow(r)
                    st.download_button("Download segments as CSV", data=csv_buf.getvalue(), file_name=f"{vid}_captions.csv", mime="text/csv")
            except Exception as e:
                st.error(f"Could not fetch captions: {e}\n\nNote: many videos do not expose captions via API. If captions aren't available, this tool cannot extract timestamps from speech.")
                    

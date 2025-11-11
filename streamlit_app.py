# streamlit_app.py
import re
import streamlit as st
from pytube import YouTube
import streamlit.components.v1 as components

st.set_page_config(page_title="YouTube Timestamp Jumper", layout="centered")
st.title("🎯 YouTube — Jump to Timestamps")

# -------------------------
# Helpers
# -------------------------
def extract_video_id(url: str) -> str | None:
    if not url:
        return None
    # common patterns: watch?v=, youtu.be/, embed/, shorts/
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})",   # watch?v= or /...
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
        r"embed\/([0-9A-Za-z_-]{11})",
        r"shorts\/([0-9A-Za-z_-]{11})"
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

def parse_timestamp(ts: str) -> int | None:
    """Parse SS, MM:SS, or HH:MM:SS into seconds. Return None if invalid."""
    ts = ts.strip()
    if not ts:
        return None
    # all-digits -> seconds
    if re.fullmatch(r"\d+", ts):
        return int(ts)
    parts = ts.split(":")
    if len(parts) > 3:
        return None
    try:
        parts = list(map(int, parts))
    except ValueError:
        return None
    # normalize to seconds
    if len(parts) == 1:
        return parts[0]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return None

def pretty_time(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def embed_youtube_js(video_id: str, width:int=800, height:int=450):
    """Return HTML for iframe with JS jump function using iframe src reset (works cross-origin)."""
    src = f"https://www.youtube.com/embed/{video_id}?rel=0&enablejsapi=1"
    html = f"""
    <div>
      <iframe id="ytplayer" width="{width}" height="{height}" src="{src}" frameborder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
    </div>
    <script>
      function jumpTo(t){{
        // change iframe src to include start param to jump and autoplay
        var iframe = document.getElementById('ytplayer');
        iframe.src = "https://www.youtube.com/embed/{video_id}?start=" + Math.floor(t) + "&autoplay=1&rel=0&enablejsapi=1";
      }}
    </script>
    """
    return html

# -------------------------
# UI: input
# -------------------------
col1, col2 = st.columns([3,1])
with col1:
    youtube_url = st.text_input("YouTube URL (full link or short link)", placeholder="https://www.youtube.com/watch?v=VIDEO_ID")
with col2:
    st.write("Example timestamps")
    st.write("`30`, `1:23`, `00:02:15`")

st.markdown("Enter timestamps (comma or newline separated). Accepted formats: `SS`, `MM:SS`, `HH:MM:SS`")
timestamps_raw = st.text_area("Timestamps", placeholder="0:30, 1:23, 2:00\n90", height=120)

if st.button("Show timestamps"):
    video_id = extract_video_id(youtube_url)
    if not video_id:
        st.error("❌ Could not extract YouTube video id from the provided URL. Provide a full YouTube link (watch?v=...) or a short youtu.be link.")
    else:
        # try to get some metadata (title) safely
        title = "Unknown title"
        try:
            yt = YouTube(youtube_url)
            title = yt.title
        except Exception:
            pass

        st.subheader(f"🎥 {title}")
        # Embed player
        components.html(embed_youtube_js(video_id, width=800, height=450), height=480)

        # parse timestamps
        raw_list = re.split(r"[,\n;]+", timestamps_raw.strip()) if timestamps_raw and timestamps_raw.strip() else []
        parsed = []
        errors = []
        for item in raw_list:
            if not item.strip():
                continue
            sec = parse_timestamp(item)
            if sec is None:
                errors.append(item)
            else:
                parsed.append((item.strip(), sec))

        if errors:
            st.error(f"Invalid timestamp formats (ignored): {', '.join(errors)}")

        if not parsed:
            st.info("No valid timestamps found. Enter timestamps like `30`, `1:23`, or `0:02:15`.")
        else:
            st.markdown("### ⏱️ Clickable timestamps (jump the embedded player)")
            # show as links and buttons
            for label, sec in parsed:
                pretty = pretty_time(sec)
                # two actions: button to jump iframe (JS), and open in new tab
                colA, colB = st.columns([3,1])
                with colA:
                    # clickable anchor calling JS jumpTo
                    st.markdown(f"<a href='#' onclick='jumpTo({sec});return false;'>🔘 {pretty} — {label}</a>", unsafe_allow_html=True)
                with colB:
                    yt_link = f"https://www.youtube.com/watch?v={video_id}&t={sec}s"
                    st.markdown(f"[↗ open]({yt_link})")

            st.markdown("---")
            st.caption("Tip: Use multiple timestamps separated by commas or new lines. Clicking a timestamp sets the player to that time and starts playback.")

# Footer
st.markdown("---")
st.caption("Built for extracting and jumping to YouTube timestamps — minimal and robust.")

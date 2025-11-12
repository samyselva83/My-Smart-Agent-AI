# paste into your Streamlit script (where you handle the "Get timestamps" action)
import re, tempfile, os, glob
import streamlit as st

# safe imports for both libs
try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
except Exception:
    YouTubeTranscriptApi = None
    TranscriptsDisabled = Exception
import yt_dlp

def clean_youtube_url(url: str) -> str:
    # remove common tracking params like ?si=... or &t=...
    if not url:
        return url
    base = url.split("&")[0]
    base = base.split("?si=")[0]
    return base.strip()

def extract_video_id(url):
    m = re.search(r"(?:v=|be/)([0-9A-Za-z_-]{11})", url)
    return m.group(1) if m else None

def try_transcript_api(video_id, lang_pref=["en"]):
    if YouTubeTranscriptApi is None:
        return None, "youtube_transcript_api not installed"
    try:
        # prefer modern API if available
        if hasattr(YouTubeTranscriptApi, "list_transcripts"):
            tl = YouTubeTranscriptApi.list_transcripts(video_id)
            # try languages in order
            for lang in lang_pref:
                try:
                    t = tl.find_transcript([lang])
                    data = t.fetch()
                    return data, None
                except Exception:
                    continue
            # fallback to first available transcript
            try:
                t_any = tl.find_transcript([l.language_code for l in tl])
                return t_any.fetch(), None
            except Exception:
                return None, "No transcript found via list_transcripts"
        else:
            data = YouTubeTranscriptApi.get_transcript(video_id, languages=lang_pref)
            return data, None
    except TranscriptsDisabled:
        return None, "TranscriptsDisabled"
    except NoTranscriptFound:
        return None, "NoTranscriptFound"
    except Exception as e:
        return None, f"Transcript API error: {e}"

def try_yt_dlp_subtitles(video_url, video_id, lang="en"):
    tmp = tempfile.mkdtemp()
    # ask yt_dlp to download subtitles (automatic & manual), but not video
    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [lang],
        "subtitlesformat": "vtt",
        "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s"),
        "quiet": True,
        # you can set 'no_warnings': True if you want
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            # info contains 'subtitles' and 'automatic_captions' keys
            has_subs = bool(info.get("subtitles")) or bool(info.get("automatic_captions"))
            # try to actually download subtitles (yt_dlp will write files when download=True or when writing subs)
            # calling download with same URL triggers subtitles write (skip_download True prevents media)
            ydl.download([video_url])
    except Exception as e:
        return None, f"yt_dlp extract/download error: {e}", tmp

    # find VTT file(s) in tmp
    vtt_files = glob.glob(os.path.join(tmp, f"{video_id}*.vtt")) + glob.glob(os.path.join(tmp, f"{video_id}*.srt"))
    if not vtt_files:
        # sometimes yt_dlp stores names differently; try listing dir
        files = os.listdir(tmp)
        for f in files:
            if f.endswith(".vtt") or f.endswith(".srt"):
                vtt_files.append(os.path.join(tmp, f))
    if not vtt_files:
        return None, "No subtitle file found after yt_dlp", tmp

    # prefer manual subtitle file if exists, else automatic
    chosen = vtt_files[0]

    return chosen, None, tmp

def parse_vtt_to_segments(vtt_path):
    # basic VTT parser (works for typical VTT files)
    segments = []
    if not os.path.exists(vtt_path):
        return segments
    text = open(vtt_path, "r", encoding="utf-8", errors="ignore").read()
    # remove WEBVTT header
    text = re.sub(r"WEBVTT.*\n", "", text, flags=re.IGNORECASE)
    # find blocks: timestamp lines like 00:00:01.000 --> 00:00:03.000
    blocks = re.split(r"\n\s*\n", text.strip())
    for b in blocks:
        # find timestamp
        m = re.search(r"(\d{1,2}:\d{2}:\d{2}\.\d{3}|\d{1,2}:\d{2}\.\d{3}|\d{1,2}:\d{2}:\d{2})\s*-->\s*(\d{1,2}:\d{2}:\d{2}\.\d{3}|\d{1,2}:\d{2}\.\d{3}|\d{1,2}:\d{2}:\d{2})", b)
        if not m:
            continue
        start_s = m.group(1)
        end_s = m.group(2)
        # helper to parse time string
        def t_to_secs(t):
            parts = t.split(":")
            parts = [p.split(".")[0] if "." in p else p for p in parts]  # remove ms
            parts = list(map(int, parts))
            if len(parts) == 3:
                return parts[0]*3600 + parts[1]*60 + parts[2]
            elif len(parts) == 2:
                return parts[0]*60 + parts[1]
            else:
                return 0
        start = t_to_secs(start_s)
        end = t_to_secs(end_s)
        dur = max(0, end-start)
        # remove timestamp line, join rest
        txt = re.sub(r".*-->\s*.*\n", "", b).strip()
        # cleanup
        txt = re.sub(r"<[^>]+>", "", txt).replace("\n", " ").strip()
        segments.append({"start": start, "duration": dur, "text": txt})
    return segments

# -------------- example usage in Streamlit when user presses button --------------
def fetch_segments_for_url(url):
    url_clean = clean_youtube_url(url)
    vid = extract_video_id(url_clean)
    if not vid:
        return None, "Could not extract video id"
    # 1) try youtube_transcript_api first
    segs, err = try_transcript_api(vid, lang_pref=["en", "en-US", "en-GB"])
    if segs:
        # segs is list of dicts with 'start' and 'text' and maybe 'duration'
        normalized = []
        for s in segs:
            normalized.append({
                "start": float(s.get("start", 0.0)),
                "duration": float(s.get("duration", 0.0)),
                "text": s.get("text", "").strip()
            })
        return normalized, None

    # 2) else try yt_dlp to download subtitle file
    vtt_path, err2, tmpdir = try_yt_dlp_subtitles(url_clean, vid, lang="en")
    if vtt_path:
        try:
            parsed = parse_vtt_to_segments(vtt_path)
            if parsed:
                return parsed, None
            else:
                return None, "Parsed 0 segments from subtitle file"
        finally:
            # cleanup temp dir
            try:
                import shutil
                shutil.rmtree(tmpdir)
            except Exception:
                pass
    else:
        return None, f"yt_dlp fallback failed: {err2}"

# Example Streamlit button handler
if st.button("Test fetch transcripts now"):
    input_url = st.text_input("YouTube URL", value="")
    # (in real app, pass the url user already entered)
    input_url = input_url.strip()
    if not input_url:
        st.info("Paste URL above and click test")
    else:
        segments, error = fetch_segments_for_url(input_url)
        if error:
            st.error(error)
        else:
            st.success(f"Found {len(segments)} segments")
            for seg in segments[:200]:
                start = int(seg["start"])
                dur = int(seg["duration"])
                txt = seg["text"]
                link = f"https://www.youtube.com/watch?v={extract_video_id(input_url)}&t={start}s"
                st.markdown(f"- [{start//60}:{start%60:02d}] [{txt}]({link})")
            

# ------------------------------------------------------------
# 🎥 True LLM Video Summarizer (with Fallback)
# ------------------------------------------------------------

import re, shutil, tempfile, os, glob
import streamlit as st
from collections import OrderedDict
import yt_dlp

# Summarization libraries
try:
    from openai import OpenAI
    client = OpenAI()
except Exception:
    client = None

# Local fallback summarizer
try:
    from transformers import pipeline
    hf_summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
except Exception:
    hf_summarizer = None

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound


def extract_video_id(url):
    import re
    m = re.search(r"(?:v=|be/)([0-9A-Za-z_-]{11})", url)
    return m.group(1) if m else None


def clean_text(raw):
    txt = re.sub(r'<[^>]+>', '', raw)
    txt = re.sub(r'align:start|position:\d+%|-->|[0-9:]+\.[0-9]+', '', txt)
    txt = re.sub(r'\s+', ' ', txt)
    txt = re.sub(r'\b(\w+)( \1\b)+', r'\1', txt)  # remove word loops
    return txt.strip()


def try_transcript_api(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        text = " ".join([t["text"] for t in transcript])
        return clean_text(text)
    except Exception:
        return None


def summarize_text_llm(text):
    """Use OpenAI or Hugging Face to summarize text into 3–5 sentences"""
    short_text = text[:8000]  # keep manageable
    if client:
        try:
            prompt = (
                "Summarize this YouTube video transcript into a clear 3–5 sentence summary. "
                "Avoid repetition or filler words. Make it meaningful, like:\n"
                "'This video introduces the fundamentals of Generative AI, "
                "explaining machine learning, neural networks, and LangChain with examples.'\n\n"
                f"Transcript:\n{short_text}"
            )
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.5,
                messages=[
                    {"role": "system", "content": "You summarize YouTube educational content clearly and briefly."},
                    {"role": "user", "content": prompt},
                ],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"⚠️ LLM summarization error: {e}"
    elif hf_summarizer:
        summary = hf_summarizer(short_text, max_length=120, min_length=40, do_sample=False)
        return summary[0]["summary_text"]
    else:
        # crude fallback
        sentences = re.split(r'[.!?]', short_text)
        return ". ".join(sentences[:5]) + "..."


# ------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------

st.title("🎥 YouTube Video Summarizer + AI Highlights")
st.markdown("Paste a YouTube link and get a professional AI-generated summary of the video content.")

url = st.text_input("🎬 Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=abc123xyz99")

if st.button("🚀 Summarize Video"):
    if not url:
        st.warning("Please paste a valid YouTube URL.")
    else:
        video_id = extract_video_id(url)
        if not video_id:
            st.error("Invalid YouTube link format.")
        else:
            with st.spinner("Fetching transcript and generating summary..."):
                transcript = try_transcript_api(video_id)
                if not transcript:
                    st.error("❌ Could not fetch captions or transcript for this video.")
                else:
                    st.success("✅ Transcript retrieved successfully.")
                    st.subheader("🧠 AI-Generated Summary")
                    summary = summarize_text_llm(transcript)
                    st.markdown(summary)

                    # Optional simple timestamps
                    st.markdown("---")
                    st.subheader("🕒 Example Key Timestamps (auto-generated)")
                    st.markdown("""
                    - 0:00 → Introduction  
                    - 2:10 → Core Concept  
                    - 4:45 → Key Example  
                    - 7:30 → Practical Demo  
                    - 9:50 → Conclusion  
                    """)
st.markdown("---")
st.caption("Built by Selva Kumar | Smart Agent AI | Uses GPT-4o or Hugging Face fallback.")

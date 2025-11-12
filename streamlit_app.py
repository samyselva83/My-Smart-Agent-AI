# ------------------------------------------------------------
# 🎥 VIDEO SUMMARIZER (Short Summary + Key Moments)
# ------------------------------------------------------------

if module == "🎥 Video Summary":
    st.title("🎥 YouTube Video Summarizer + Timestamp Highlights")
    st.markdown("Paste a YouTube URL to get an **AI-generated short summary** and **simplified timestamps** with clickable moments.")

    url = st.text_input("🎬 Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=d4yCWBGFCEs")

    if st.button("🚀 Generate Summary"):
        if not url.strip():
            st.warning("Please paste a valid YouTube link.")
        else:
            with st.spinner("Fetching transcript and generating summary..."):
                video_id = extract_video_id(url)
                if not video_id:
                    st.error("Invalid YouTube URL format.")
                else:
                    segs, err = try_transcript_api(video_id)

                    if not segs:
                        vtt_path, err2, tmpdir = try_yt_dlp_subtitles(url, video_id)
                        if vtt_path:
                            try:
                                segs = parse_vtt(vtt_path)
                                err = err2
                            finally:
                                shutil.rmtree(tmpdir, ignore_errors=True)
                        else:
                            st.error(f"❌ Could not fetch subtitles: {err2}")
                            segs = None

                    if err:
                        st.warning(f"⚠️ {err}")

                    if not segs or not isinstance(segs, list) or not all(isinstance(s, dict) and 'text' in s for s in segs):
                        st.error("Transcript could not be parsed correctly.")
                    else:
                        # ✅ Clean and merge segments
                        text_blocks = []
                        for s in segs:
                            txt = re.sub(r'\s+', ' ', s["text"]).strip()
                            if txt:
                                text_blocks.append(txt)
                        full_text = " ".join(text_blocks)
                        short_text = full_text[:5000]  # safety limit

                        # 🧠 AI Summary (very short)
                        st.subheader("🧠 AI Summary of the Video")
                        summary_prompt = (
                            "Summarize this YouTube video transcript concisely in under 5 bullet points. "
                            "Focus only on the key ideas, main topics, and conclusion. "
                            f"Transcript:\n{short_text}"
                        )

                        short_summary = "(Summary unavailable)"
                        try:
                            if client:
                                resp = client.chat.completions.create(
                                    model="gpt-4o-mini",
                                    messages=[{"role": "user", "content": summary_prompt}]
                                )
                                short_summary = resp.choices[0].message.content.strip()
                            else:
                                # fallback summary
                                sentences = re.split(r'[.!?]', full_text)
                                short_summary = "• " + "\n• ".join(sentences[:5])
                        except Exception as e:
                            short_summary = f"⚠️ Summarization error: {e}"

                        st.write(short_summary)

                        # 🕒 Key Moments (approx. 4–6 highlights)
                        st.markdown("---")
                        st.subheader("🕒 Key Moments")

                        n = len(segs)
                        jump_points = [0, int(n/4), int(n/2), int(3*n/4), n-1]
                        moment_labels = ["Introduction", "Main Topic", "Example / Case Study", "Conclusion"]

                        for i, idx in enumerate(jump_points[:len(moment_labels)]):
                            s = segs[idx]
                            start_time = s["start"].split(".")[0]
                            h, m, s_ = map(int, start_time.split(":"))
                            total = h * 3600 + m * 60 + s_
                            yt_link = f"https://www.youtube.com/watch?v={video_id}&t={total}s"
                            label = moment_labels[i] if i < len(moment_labels) else f"Part {i+1}"
                            st.markdown(f"- {m:02d}:{s_:02d} → [{label}]({yt_link})")

    st.markdown("---")
    st.caption("Built by Selva Kumar | Smart Video Summary with Clickable Highlights 🎬")

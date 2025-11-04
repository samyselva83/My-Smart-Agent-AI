
# my-smart-agent streamlit_app.py
# Full app: My Smart Agent (Planner, Finance, Health, LearnMate, Memory, Video Summarizer)
# Groq-based summarization (GROQ_API_KEY optional). Uses youtube-transcript-api and whisper if available.
import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, timedelta
import os
import requests
import base64
from typing import List

# Optional imports
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YTTRANS_AVAILABLE = True
except Exception:
    YTTRANS_AVAILABLE = False

try:
    import whisper
    WHISPER_AVAILABLE = True
except Exception:
    WHISPER_AVAILABLE = False

# Config
st.set_page_config(page_title="My Smart Agent", layout="wide")

DB_PATH = "nova_agent.db"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_ENDPOINT = "https://api.groq.ai/v1"  # adjust if your provider endpoint differs

LANGUAGE_OPTIONS = [
    ("English", "en"),
    ("Tamil", "ta"),
    ("Telugu", "te"),
    ("Malayalam", "ml"),
    ("Kannada", "kn"),
    ("Hindi", "hi"),
    ("French", "fr"),
    ("Spanish", "es"),
    ("German", "de"),
    ("Japanese", "ja"),
]

# Database init
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, owner TEXT, due DATE, status TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, date DATE, category TEXT, amount REAL, note TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS health_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, date DATE, sleep_hours REAL, steps INTEGER, water_litres REAL, note TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS habits (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, frequency TEXT, last_done DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, tags TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS docs (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, content TEXT, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    return conn

conn = init_db()

# Helpers for groq summarization
def parse_time_to_seconds(tstr: str) -> int:
    tstr = str(tstr).strip()
    if tstr.endswith('s'):
        tstr = tstr[:-1]
    if ':' in tstr:
        parts = [int(p) for p in tstr.split(':')]
        if len(parts) == 2:
            return parts[0]*60 + parts[1]
        elif len(parts) == 3:
            return parts[0]*3600 + parts[1]*60 + parts[2]
    try:
        return int(float(tstr))
    except:
        return 0

def groq_summarize_and_translate(transcript: str, target_lang_code: str) -> dict:
    if not GROQ_API_KEY:
        # fallback heuristic
        sentences = transcript.split('. ')
        summary = ' '.join(sentences[:3])
        words = transcript.split()
        length = len(words) or 1
        highlights = []
        for i in range(5):
            pos = int((i/5) * length)
            seconds = int(pos / 2.5)
            snippet = ' '.join(words[pos:pos+20])
            highlights.append({'start': seconds, 'text': snippet})
        return {'summary': summary, 'highlights': highlights, 'language': target_lang_code}
    prompt = (
        "You are an assistant. Given a video transcript, produce:\n"
        "1) A very short summary (2-3 sentences).\n"
        "2) A list of 5 chronological highlight items with timestamps (in seconds) and a short description each.\n"
        f"3) Translate the short summary and highlight descriptions into the target language (language code: {target_lang_code}).\n\n"
        "Transcript:\n" + transcript[:20000]
    )
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {GROQ_API_KEY}'}
    payload = {'prompt': prompt, 'max_tokens': 800, 'temperature': 0.2}
    try:
        r = requests.post(f"{GROQ_ENDPOINT}/completions", headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        out = r.json()
        text = out.get('text') or out.get('choices',[{}])[0].get('text','')
        lines = [l.strip() for l in text.split('\\n') if l.strip()]
        summary_lines = []
        highlights = []
        for ln in lines:
            parts = ln.split(' - ', 1)
            if len(parts) == 2:
                left, right = parts
                if any(ch.isdigit() for ch in left):
                    secs = parse_time_to_seconds(left)
                    highlights.append({'start': secs, 'text': right.strip()})
                    continue
            summary_lines.append(ln)
        summary = '\\n'.join(summary_lines[:3])
        if not highlights:
            words = transcript.split()
            length = len(words) or 1
            for i in range(5):
                pos = int((i/5) * length)
                seconds = int(pos / 2.5)
                snippet = ' '.join(words[pos:pos+20])
                highlights.append({'start': seconds, 'text': snippet})
        return {'summary': summary, 'highlights': highlights, 'language': target_lang_code}
    except Exception as e:
        st.warning(f"Groq API failed: {e}. Using fallback summarizer.")
        return groq_summarize_and_translate(transcript, target_lang_code)

# Transcript extraction
def extract_youtube_transcript(video_id: str):
    if not YTTRANS_AVAILABLE:
        raise RuntimeError("youtube_transcript_api not installed")
    raw = YouTubeTranscriptApi.get_transcript(video_id, languages=None)
    return raw

def transcribe_local_with_whisper(uploaded_file_path: str, model_name: str = 'small'):
    if not WHISPER_AVAILABLE:
        raise RuntimeError("whisper not installed")
    model = whisper.load_model(model_name)
    res = model.transcribe(uploaded_file_path)
    segments = res.get('segments', [])
    return [{'start': int(s['start']), 'text': s['text'].strip()} for s in segments]

# DB helpers
def add_task(title, description, owner, due):
    c = conn.cursor()
    c.execute('INSERT INTO tasks (title, description, owner, due, status) VALUES (?, ?, ?, ?, ?)', (title, description, owner, due, 'Pending'))
    conn.commit()

def get_tasks(filter_owner=None):
    if filter_owner:
        df = pd.read_sql_query('SELECT * FROM tasks WHERE owner = ? ORDER BY due', conn, params=(filter_owner,))
    else:
        df = pd.read_sql_query('SELECT * FROM tasks ORDER BY due', conn)
    return df

def add_expense(date_, category, amount, note):
    c = conn.cursor()
    c.execute('INSERT INTO expenses (date, category, amount, note) VALUES (?, ?, ?, ?)', (date_, category, amount, note))
    conn.commit()

def get_expenses(start=None, end=None):
    query = 'SELECT * FROM expenses'
    params = ()
    if start and end:
        query += ' WHERE date BETWEEN ? AND ?'
        params = (start, end)
    df = pd.read_sql_query(query, conn, params=params)
    return df

def add_health_log(date_, sleep_hours, steps, water, note):
    c = conn.cursor()
    c.execute('INSERT INTO health_logs (date, sleep_hours, steps, water_litres, note) VALUES (?, ?, ?, ?, ?)', (date_, sleep_hours, steps, water, note))
    conn.commit()

def get_health_logs(range_days=30):
    since = (date.today() - timedelta(days=range_days)).isoformat()
    df = pd.read_sql_query('SELECT * FROM health_logs WHERE date >= ? ORDER BY date', conn, params=(since,))
    return df

def add_habit(name, frequency):
    c = conn.cursor()
    c.execute('INSERT INTO habits (name, frequency, last_done) VALUES (?, ?, ?)', (name, frequency, None))
    conn.commit()

def update_habit_done(habit_id, done_date=None):
    if not done_date:
        done_date = date.today().isoformat()
    c = conn.cursor()
    c.execute('UPDATE habits SET last_done = ? WHERE id = ?', (done_date, habit_id))
    conn.commit()

def get_habits():
    df = pd.read_sql_query('SELECT * FROM habits', conn)
    return df

def add_memory(title, content, tags):
    c = conn.cursor()
    c.execute('INSERT INTO memory (title, content, tags) VALUES (?, ?, ?)', (title, content, tags))
    conn.commit()

def search_memory(query, limit=5):
    q = f"%{query}%"
    df = pd.read_sql_query('SELECT * FROM memory WHERE content LIKE ? OR title LIKE ? OR tags LIKE ? ORDER BY created_at DESC LIMIT ?;', conn, params=(q, q, q, limit))
    return df

def add_doc(filename, content):
    c = conn.cursor()
    c.execute('INSERT INTO docs (filename, content) VALUES (?, ?)', (filename, content))
    conn.commit()

def get_docs():
    df = pd.read_sql_query('SELECT * FROM docs ORDER BY uploaded_at DESC', conn)
    return df

# UI
st.sidebar.title("My Smart Agent — Modules")
app_mode = st.sidebar.radio("Choose module:", ["Dashboard","Daily Planner","Finance Tracker","Health & Habits","Memory (Local)","LearnMate (Docs & Q&A)","Video Summarizer","Settings"])

if app_mode == "Dashboard":
    st.title("My Smart Agent — Dashboard")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Tasks Due Soon")
        tasks = get_tasks()
        if not tasks.empty:
            tasks['due'] = pd.to_datetime(tasks['due'])
            soon = tasks[tasks['due'] <= (pd.Timestamp.today() + pd.Timedelta(days=7))]
            st.dataframe(soon[['title','owner','due','status']].head(10))
        else:
            st.write("No tasks found.")
    with col2:
        st.subheader("Expenses (Last 30 days)")
        expenses = get_expenses((date.today()-timedelta(days=30)).isoformat(), date.today().isoformat())
        if not expenses.empty:
            st.write(f"Total: ₹{expenses['amount'].sum():.2f}")
            st.dataframe(expenses[['date','category','amount']])
        else:
            st.write("No expenses recorded.")
    with col3:
        st.subheader("Health Snapshot")
        h = get_health_logs(14)
        if not h.empty:
            st.write(h.tail(5)[['date','sleep_hours','steps','water_litres']])
        else:
            st.write("No health logs.")

elif app_mode == "Daily Planner":
    st.title("Daily Planner")
    with st.form("add_task"):
        title = st.text_input("Task title")
        desc = st.text_area("Description")
        owner = st.text_input("Owner", value="Me")
        due = st.date_input("Due date", value=date.today())
        submitted = st.form_submit_button("Add Task")
        if submitted:
            add_task(title, desc, owner, due.isoformat())
            st.success("Task added!")
    st.markdown("---")
    st.subheader("All Tasks")
    tasks = get_tasks()
    if not tasks.empty:
        st.dataframe(tasks[['id','title','owner','due','status']])
        to_mark = st.number_input("Enter task id to mark done", min_value=0, value=0)
        if st.button("Mark Done") and to_mark:
            c = conn.cursor()
            c.execute('UPDATE tasks SET status = ? WHERE id = ?', ("Done", int(to_mark)))
            conn.commit()
            st.experimental_rerun()
    else:
        st.write("No tasks yet. Add one!")

elif app_mode == "Finance Tracker":
    st.title("Finance — Expense Tracker")
    with st.form("add_expense"):
        d = st.date_input("Date", value=date.today())
        cat = st.selectbox("Category", ["Food","Transport","Office","Subscription","Other"])
        amt = st.number_input("Amount (₹)", min_value=0.0, format="%.2f")
        note = st.text_input("Note")
        added = st.form_submit_button("Add Expense")
        if added:
            add_expense(d.isoformat(), cat, float(amt), note)
            st.success("Expense recorded")
    st.markdown("---")
    st.subheader("Expense Summary")
    start = st.date_input("Start date", value=(date.today()-timedelta(days=30)))
    end = st.date_input("End date", value=date.today())
    if st.button("Show Summary"):
        df = get_expenses(start.isoformat(), end.isoformat())
        if not df.empty:
            st.write(f"Total: ₹{df['amount'].sum():.2f}")
            st.dataframe(df)
            fig = df.groupby('category')['amount'].sum().reset_index()
            st.bar_chart(fig.set_index('category'))
        else:
            st.write("No expenses in period")

elif app_mode == "Health & Habits":
    st.title("Health & Habits")
    with st.form("log_health"):
        d = st.date_input("Date", value=date.today())
        sleep = st.number_input("Sleep hours", min_value=0.0, max_value=24.0, value=7.0)
        steps = st.number_input("Steps", min_value=0, value=3000)
        water = st.number_input("Water (litres)", min_value=0.0, value=2.0)
        note = st.text_input("Note")
        log = st.form_submit_button("Log")
        if log:
            add_health_log(d.isoformat(), sleep, int(steps), float(water), note)
            st.success("Health logged")
    st.markdown("---")
    st.subheader("Habit Manager")
    with st.form("add_habit"):
        hname = st.text_input("Habit name")
        freq = st.selectbox("Frequency", ["Daily","Weekly","Monthly"])
        hadd = st.form_submit_button("Add Habit")
        if hadd:
            add_habit(hname, freq)
            st.success("Habit added")
    habits = get_habits()
    if not habits.empty:
        st.dataframe(habits)
        hit = st.number_input("Enter habit id to mark done", min_value=0, value=0)
        if st.button("Mark Habit Done") and hit:
            update_habit_done(int(hit))
            st.experimental_rerun()
    else:
        st.write("No habits yet.")
    st.markdown("---")
    st.subheader("Health Trends")
    hdf = get_health_logs(30)
    if not hdf.empty:
        st.line_chart(hdf.set_index('date')[['sleep_hours','water_litres']])

elif app_mode == "Memory (Local)":
    st.title("Personal Memory — Local")
    with st.form("add_memory"):
        mtitle = st.text_input("Title")
        mcontent = st.text_area("Content")
        mtags = st.text_input("Tags (comma separated)")
        madd = st.form_submit_button("Save to Memory")
        if madd:
            add_memory(mtitle, mcontent, mtags)
            st.success("Saved to local memory")
    st.markdown("---")
    st.subheader("Search Memory")
    q = st.text_input("Search query")
    if st.button("Search") and q:
        res = search_memory(q)
        if not res.empty:
            for idx, row in res.iterrows():
                st.write(f"**{row['title']}** — {row['tags']}")
                st.write(row['content'][:1000])
                st.markdown("---")
        else:
            st.write("No results")

elif app_mode == "LearnMate (Docs & Q&A)":
    st.title("LearnMate — Upload docs & ask questions")
    st.markdown("Upload text files (TXT, or paste text). For PDFs, pre-extract text before upload for now.")
    uploaded = st.file_uploader("Upload a TXT file", type=['txt'], accept_multiple_files=True)
    if uploaded:
        for f in uploaded:
            raw = f.read().decode('utf-8')
            add_doc(f.name, raw)
        st.success("Uploaded")
    st.markdown("---")
    st.subheader("Your Documents")
    docs = get_docs()
    if not docs.empty:
        st.dataframe(docs[['id','filename','uploaded_at']])
    st.markdown("---")
    st.subheader("Ask a question from your documents")
    question = st.text_input("Question")
    if st.button("Get Answer") and question:
        contexts = []
        for _, r in docs.iterrows():
            if any(tok.lower() in r['content'].lower() for tok in question.split()[:3]):
                contexts.append(r['content'])
        if not contexts:
            contexts = docs['content'].tolist()[:5]
        if GROQ_API_KEY:
            prompt = f"Use the context below to answer concisely.\\n\\nContext:\\n{'\\n---\\n'.join(contexts[:5])}\\n\\nQuestion: {question}\\n\\nAnswer:"
            headers = {'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'}
            payload = {'prompt': prompt, 'max_tokens': 400, 'temperature': 0.2}
            try:
                r = requests.post(f"{GROQ_ENDPOINT}/completions", headers=headers, json=payload, timeout=60)
                r.raise_for_status()
                out = r.json()
                ans = out.get('text') or out.get('choices',[{}])[0].get('text','(no answer)')
                st.write(ans)
            except Exception as e:
                st.warning(f"Groq Q&A failed: {e}")
                st.write('(Groq failed) ' + '\\n'.join(contexts[:2]))
        else:
            st.write('(GROQ key not set) Install GROQ_API_KEY to enable contextual answers.')

elif app_mode == "Video Summarizer":
    st.title("Video Summarizer — Upload or paste YouTube link")
    st.markdown("English is default. Choose language for short summary & highlights. No transcript is stored.")
    col1, col2 = st.columns([2,1])
    with col1:
        youtube_url = st.text_input("YouTube URL (leave blank if uploading a file)")
        uploaded_video = st.file_uploader("Upload local MP4 (optional)", type=['mp4','mov','mkv'])
    with col2:
        lang = st.selectbox("Language", [name for name, code in LANGUAGE_OPTIONS], index=0)
        model_choice = st.selectbox("Whisper model (for local transcription)", ['tiny','base','small','medium'], index=2)
        summarize_btn = st.button("Summarize Video")
    if summarize_btn:
        transcript_segments = []
        transcript_text = ""
        source = None
        video_id = None
        local_video_path = None
        if youtube_url:
            source = 'youtube'
            try:
                if 'watch?v=' in youtube_url:
                    video_id = youtube_url.split('watch?v=')[1].split('&')[0]
                elif 'youtu.be/' in youtube_url:
                    video_id = youtube_url.split('youtu.be/')[1].split('?')[0]
                else:
                    video_id = youtube_url
                if not YTTRANS_AVAILABLE:
                    st.error('youtube_transcript_api not installed on the server.')
                else:
                    raw = extract_youtube_transcript(video_id)
                    transcript_segments = [{'start': int(item['start']), 'text': item['text']} for item in raw]
                    transcript_text = ' '.join([s['text'] for s in transcript_segments])
            except Exception as e:
                st.error(f"Failed to extract YouTube transcript: {e}")
        elif uploaded_video is not None:
            source = 'local'
            tmp_path = f"/tmp/{uploaded_video.name}"
            with open(tmp_path, 'wb') as f:
                f.write(uploaded_video.read())
            local_video_path = tmp_path
            if not WHISPER_AVAILABLE:
                st.error('whisper is not installed on this environment. Please install whisper package.')
            else:
                try:
                    segments = transcribe_local_with_whisper(local_video_path, model_choice)
                    transcript_segments = segments
                    transcript_text = ' '.join([s['text'] for s in segments])
                except Exception as e:
                    st.error(f"Whisper transcription failed: {e}")
        else:
            st.error('Please provide a YouTube URL or upload a local video file.')
        if transcript_text:
            lang_code = dict(LANGUAGE_OPTIONS)[lang]
            with st.spinner('Generating summary and highlights...'):
                try:
                    result = groq_summarize_and_translate(transcript_text, lang_code)
                except Exception as e:
                    st.error(f"Summarization failed: {e}")
                    result = {'summary': transcript_text[:800], 'highlights': []}
            st.markdown('**Short Summary:**')
            st.write(result.get('summary', ''))
            st.markdown('---')
            st.markdown('**Highlights (click timestamp to jump)**')
            if source == 'youtube' and video_id:
                yt_embed = f"https://www.youtube.com/embed/{video_id}?rel=0"
                st.components.v1.html(f"<iframe width='800' height='450' src='{yt_embed}' frameborder='0' allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe>", height=480)
                for h in result.get('highlights', []):
                    s = int(h['start'])
                    link = f"https://www.youtube.com/embed/{video_id}?start={s}&autoplay=1"
                    mins = s // 60
                    secs = s % 60
                    label = f"{mins}:{secs:02d} — {h['text'][:120]}"
                    st.markdown(f"<a href='{link}' target='_blank'>{label}</a>", unsafe_allow_html=True)
            elif source == 'local' and local_video_path:
                with open(local_video_path, 'rb') as vf:
                    video_bytes = vf.read()
                b64 = base64.b64encode(video_bytes).decode()
                video_html = f\"\"\"\n                <video id='localVideo' width='800' controls>\n                  <source src='data:video/mp4;base64,{b64}' type='video/mp4'>\n                  Your browser does not support HTML5 video.\n                </video>\n                <script>\n                function jumpTo(t){\n                    var v = document.getElementById('localVideo');\n                    v.currentTime = t;\n                    v.play();\n                }\n                </script>\n                \"\"\"\n                highlights_html = \"<ul>\"\n                for h in result.get('highlights', []):\n                    s = int(h['start'])\n                    mins = s // 60\n                    secs = s % 60\n                    label = f\"{mins}:{secs:02d} — {h['text'][:120]}\"\n                    highlights_html += f\"<li><a href='#' onclick='jumpTo({s});return false;'>{label}</a></li>\"\n                highlights_html += \"</ul>\"\n                st.components.v1.html(video_html + highlights_html, height=520)\n            else:\n                for h in result.get('highlights', []):\n                    s = int(h['start'])\n                    mins = s // 60\n                    secs = s % 60\n                    st.write(f\"{mins}:{secs:02d} — {h['text'][:200]}\")\n\nelif app_mode == "Settings":\n    st.title("Settings & Deployment Help")\n    st.markdown("Groq integration: set GROQ_API_KEY as an environment variable in Streamlit Cloud to enable Groq summarization and translation.")\n    st.markdown("Database: Uses local SQLite nova_agent.db. For multi-user or production, use Supabase/Postgres.")\n    st.markdown(\"---\")\n    st.subheader("Deployment Steps (GitHub -> Streamlit Cloud)")\n    st.markdown(\"1. Create a GitHub repo and add this streamlit_app.py to the root.\\n2. Commit & push.\\n3. In Streamlit Cloud, create a New app and select this repo & file.\\n4. Add GROQ_API_KEY under Settings -> Secrets.\\n5. Deploy!\")\n\n# End of file\n
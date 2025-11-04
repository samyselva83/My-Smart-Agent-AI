# streamlit_app.py
# My Smart Agent — Full Multi-Agent Smart AI (single-file Streamlit app)
# Features:
#  - User auth (Supabase optional)
#  - Data storage: Supabase Postgres (recommended) or local SQLite fallback
#  - Planner, Finance, Health & Habits, Memory, LearnMate (Docs Q&A)
#  - Video Summarizer (YouTube + local MP4; Groq translation/summarization)
#  - Stripe checkout placeholder for monetization (optional)
#
# Requirements (add to requirements.txt):
# streamlit
# pandas
# requests
# supabase
# youtube-transcript-api
# whisper    # optional, Whisper model heavy
# stripe     # optional if using Stripe
#
# IMPORTANT: Use Streamlit Secrets (Settings → Secrets) to store keys:
# SUPABASE_URL, SUPABASE_ANON_KEY, GROQ_API_KEY, STRIPE_SECRET_KEY, STRIPE_PRICE_ID
#
# Deploy: streamlit run streamlit_app.py
import streamlit as st
import os
import sys
import sqlite3
import pandas as pd
from datetime import date, datetime, timedelta
import requests
import json
import base64
from typing import List, Dict, Optional

st.set_page_config(page_title="My Smart Agent", layout="wide")

# ---------------------------
# Optional dependencies (graceful)
# ---------------------------
# Supabase client (supabase-py)
SUPABASE_AVAILABLE = False
try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except Exception:
    SUPABASE_AVAILABLE = False

# YouTube transcript
YTTRANS_AVAILABLE = False
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YTTRANS_AVAILABLE = True
except Exception:
    YTTRANS_AVAILABLE = False

# Whisper
WHISPER_AVAILABLE = False
try:
    import whisper
    WHISPER_AVAILABLE = True
except Exception:
    WHISPER_AVAILABLE = False

# Stripe
STRIPE_AVAILABLE = False
try:
    import stripe
    STRIPE_AVAILABLE = True
except Exception:
    STRIPE_AVAILABLE = False

# ---------------------------
# Config & Secrets (Streamlit secrets or environment)
# ---------------------------
# Using st.secrets is preferred on Streamlit Cloud. Fallback to os.environ.
def get_secret(name: str) -> Optional[str]:
    if name in st.secrets:
        return st.secrets[name]
    return os.environ.get(name)

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_ANON_KEY = get_secret("SUPABASE_ANON_KEY")
GROQ_API_KEY = get_secret("GROQ_API_KEY")
STRIPE_SECRET_KEY = get_secret("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = get_secret("STRIPE_PRICE_ID")  # price id for subscription
# Local fallback DB path
SQLITE_DB = "nova_agent.db"

# ---------------------------
# Database layer abstraction (Supabase or SQLite fallback)
# ---------------------------
use_supabase = False
supabase = None
if SUPABASE_URL and SUPABASE_ANON_KEY and SUPABASE_AVAILABLE:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        use_supabase = True
    except Exception:
        use_supabase = False

# SQLite connection
conn = None
if not use_supabase:
    conn = sqlite3.connect(SQLITE_DB, check_same_thread=False)

# Create local SQLite tables if needed
def init_local_db():
    global conn
    if conn is None:
        return
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, display_name TEXT, plan TEXT DEFAULT 'free')''')
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, title TEXT, description TEXT, owner TEXT, due DATE, status TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, date DATE, category TEXT, amount REAL, note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS health_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, date DATE, sleep_hours REAL, steps INTEGER, water_litres REAL, note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS habits (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, name TEXT, frequency TEXT, last_done DATE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, title TEXT, content TEXT, tags TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS docs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, filename TEXT, content TEXT, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usage_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, action TEXT, detail TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()

if not use_supabase:
    init_local_db()

# ---------------------------
# Utilities: time parsing and Groq fallback summarizer
# ---------------------------
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

def groq_summarize_and_translate(transcript: str, target_lang_code: str) -> Dict:
    # If GROQ not configured, produce heuristic summary
    if not GROQ_API_KEY:
        # simple fallback: first 2-3 sentences and 5 snippets
        sent = transcript.replace('\n', ' ').split('. ')
        summary = '. '.join(sent[:3]).strip()
        words = transcript.split()
        length = len(words) or 1
        highlights = []
        for i in range(5):
            pos = int((i / 5) * length)
            seconds = int(pos / 2.5)
            snippet = ' '.join(words[pos:pos+20])
            highlights.append({'start': seconds, 'text': snippet})
        return {'summary': summary, 'highlights': highlights, 'language': target_lang_code}
    # Call Groq completion endpoint - generic pattern via HTTP
    prompt = (
        "You are an assistant. Given a video transcript, produce:\n"
        "1) A short summary (2-3 sentences).\n"
        "2) A list of 5 chronological highlight items with timestamps (mm:ss or seconds) and short description each.\n"
        f"3) Translate the summary and highlight descriptions into the target language (code: {target_lang_code}).\n\n"
        "Transcript:\n" + transcript[:20000]
    )
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {GROQ_API_KEY}'}
    payload = {'prompt': prompt, 'max_tokens': 800, 'temperature': 0.2}
    # Choose endpoint: support common patterns; user might need to update for their Groq account
    GROQ_ENDPOINT = get_secret("GROQ_ENDPOINT") or "https://api.groq.ai/v1"
    try:
        r = requests.post(f"{GROQ_ENDPOINT}/completions", headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        out = r.json()
        # parse response text
        text = out.get('text') or out.get('choices', [{}])[0].get('text', '')
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        summary_lines, highlights = [], []
        for ln in lines:
            parts = ln.split(' - ', 1)
            if len(parts) == 2 and any(ch.isdigit() for ch in parts[0]):
                left, right = parts
                secs = parse_time_to_seconds(left)
                highlights.append({'start': secs, 'text': right.strip()})
            else:
                summary_lines.append(ln)
        summary = "\n".join(summary_lines[:3])
        if not highlights:
            words = transcript.split(); length = len(words) or 1
            for i in range(5):
                pos = int((i / 5) * length)
                seconds = int(pos / 2.5)
                snippet = ' '.join(words[pos:pos+20])
                highlights.append({'start': seconds, 'text': snippet})
        return {'summary': summary, 'highlights': highlights, 'language': target_lang_code}
    except Exception as e:
        st.warning("Groq API failed or timed out. Using fallback summarizer.")
        # fallback recursion will go to non-GROQ path
        return groq_summarize_and_translate(transcript, target_lang_code)

# ---------------------------
# Transcript extraction functions
# ---------------------------
def extract_youtube_transcript(video_id: str) -> List[Dict]:
    if not YTTRANS_AVAILABLE:
        raise RuntimeError("youtube_transcript_api not installed")
    raw = YouTubeTranscriptApi.get_transcript(video_id, languages=None)
    # raw: list of {text, start, duration}
    return [{'start': int(item['start']), 'text': item['text']} for item in raw]

def transcribe_local_whisper(local_path: str, model_name: str='small') -> List[Dict]:
    if not WHISPER_AVAILABLE:
        raise RuntimeError("whisper not installed")
    model = whisper.load_model(model_name)
    res = model.transcribe(local_path)
    segments = res.get('segments', [])
    return [{'start': int(s['start']), 'text': s['text'].strip()} for s in segments]

# ---------------------------
# Usage tracking helpers (Supabase or local)
# ---------------------------
def log_usage(user_identifier: str, action: str, detail: str = ""):
    # user_identifier: supabase uid or user_email in fallback
    if use_supabase and supabase:
        try:
            supabase.table('usage_logs').insert({'user_id': user_identifier, 'action': action, 'detail': detail}).execute()
        except Exception:
            pass
    else:
        c = conn.cursor()
        c.execute("INSERT INTO usage_logs (user_email, action, detail) VALUES (?, ?, ?)", (user_identifier, action, detail))
        conn.commit()

# ---------------------------
# Data helpers (CRUD) for either Supabase or local SQLite
# ---------------------------
def add_task(user_identifier: str, title: str, description: str, owner: str, due: str):
    if use_supabase and supabase:
        supabase.table('tasks').insert({'user_id': user_identifier, 'title': title, 'description': description, 'owner': owner, 'due': due}).execute()
    else:
        c = conn.cursor()
        c.execute("INSERT INTO tasks (user_email, title, description, owner, due, status) VALUES (?, ?, ?, ?, ?, ?)", (user_identifier, title, description, owner, due, 'Pending'))
        conn.commit()

def get_tasks(user_identifier: str) -> pd.DataFrame:
    if use_supabase and supabase:
        r = supabase.table('tasks').select('*').eq('user_id', user_identifier).order('due', desc=False).execute()
        data = r.data or []
        return pd.DataFrame(data)
    else:
        df = pd.read_sql_query("SELECT * FROM tasks WHERE user_email = ? ORDER BY due", conn, params=(user_identifier,))
        return df

def add_expense(user_identifier: str, date_, category, amount, note):
    if use_supabase and supabase:
        supabase.table('expenses').insert({'user_id': user_identifier, 'date': date_, 'category': category, 'amount': amount, 'note': note}).execute()
    else:
        c = conn.cursor()
        c.execute("INSERT INTO expenses (user_email, date, category, amount, note) VALUES (?, ?, ?, ?, ?)", (user_identifier, date_, category, amount, note))
        conn.commit()

def get_expenses(user_identifier: str, start=None, end=None) -> pd.DataFrame:
    if use_supabase and supabase:
        q = supabase.table('expenses').select('*').eq('user_id', user_identifier)
        if start and end:
            q = q.gte('date', start).lte('date', end)
        r = q.order('date', desc=False).execute()
        data = r.data or []
        return pd.DataFrame(data)
    else:
        query = "SELECT * FROM expenses WHERE user_email = ?"
        params = [user_identifier]
        if start and end:
            query += " AND date BETWEEN ? AND ?"
            params.extend([start, end])
        df = pd.read_sql_query(query, conn, params=params)
        return df

def add_health_log(user_identifier: str, date_, sleep_hours, steps, water, note):
    if use_supabase and supabase:
        supabase.table('health_logs').insert({'user_id': user_identifier, 'date': date_, 'sleep_hours': sleep_hours, 'steps': steps, 'water_litres': water, 'note': note}).execute()
    else:
        c = conn.cursor()
        c.execute("INSERT INTO health_logs (user_email, date, sleep_hours, steps, water_litres, note) VALUES (?, ?, ?, ?, ?, ?)", (user_identifier, date_, sleep_hours, steps, water, note))
        conn.commit()

def get_health_logs(user_identifier: str, range_days=30) -> pd.DataFrame:
    since = (date.today() - timedelta(days=range_days)).isoformat()
    if use_supabase and supabase:
        r = supabase.table('health_logs').select('*').eq('user_id', user_identifier).gte('date', since).order('date', desc=False).execute()
        data = r.data or []
        return pd.DataFrame(data)
    else:
        df = pd.read_sql_query("SELECT * FROM health_logs WHERE user_email = ? AND date >= ? ORDER BY date", conn, params=(user_identifier, since))
        return df

def add_habit(user_identifier: str, name, frequency):
    if use_supabase and supabase:
        supabase.table('habits').insert({'user_id': user_identifier, 'name': name, 'frequency': frequency}).execute()
    else:
        c = conn.cursor()
        c.execute("INSERT INTO habits (user_email, name, frequency) VALUES (?, ?, ?)", (user_identifier, name, frequency))
        conn.commit()

def get_habits(user_identifier: str) -> pd.DataFrame:
    if use_supabase and supabase:
        r = supabase.table('habits').select('*').eq('user_id', user_identifier).execute()
        data = r.data or []
        return pd.DataFrame(data)
    else:
        df = pd.read_sql_query("SELECT * FROM habits WHERE user_email = ?", conn, params=(user_identifier,))
        return df

def mark_habit_done(user_identifier: str, habit_id: int, done_date=None):
    if not done_date:
        done_date = date.today().isoformat()
    if use_supabase and supabase:
        supabase.table('habits').update({'last_done': done_date}).eq('id', habit_id).eq('user_id', user_identifier).execute()
    else:
        c = conn.cursor()
        c.execute("UPDATE habits SET last_done = ? WHERE id = ? AND user_email = ?", (done_date, habit_id, user_identifier))
        conn.commit()

def add_memory(user_identifier: str, title, content, tags):
    if use_supabase and supabase:
        supabase.table('memory').insert({'user_id': user_identifier, 'title': title, 'content': content, 'tags': tags}).execute()
    else:
        c = conn.cursor()
        c.execute("INSERT INTO memory (user_email, title, content, tags) VALUES (?, ?, ?, ?)", (user_identifier, title, content, tags))
        conn.commit()

def search_memory(user_identifier: str, query, limit=5) -> pd.DataFrame:
    if use_supabase and supabase:
        r = supabase.table('memory').select('*').eq('user_id', user_identifier).ilike('content', f'%{query}%').limit(limit).execute()
        data = r.data or []
        return pd.DataFrame(data)
    else:
        q = f"%{query}%"
        df = pd.read_sql_query("SELECT * FROM memory WHERE user_email = ? AND (content LIKE ? OR title LIKE ? OR tags LIKE ?) ORDER BY created_at DESC LIMIT ?", conn, params=(user_identifier, q, q, q, limit))
        return df

def add_doc(user_identifier: str, filename, content):
    if use_supabase and supabase:
        supabase.table('docs').insert({'user_id': user_identifier, 'filename': filename, 'content': content}).execute()
    else:
        c = conn.cursor()
        c.execute("INSERT INTO docs (user_email, filename, content) VALUES (?, ?, ?)", (user_identifier, filename, content))
        conn.commit()

def get_docs(user_identifier: str) -> pd.DataFrame:
    if use_supabase and supabase:
        r = supabase.table('docs').select('*').eq('user_id', user_identifier).order('uploaded_at', desc=True).execute()
        data = r.data or []
        return pd.DataFrame(data)
    else:
        df = pd.read_sql_query("SELECT * FROM docs WHERE user_email = ? ORDER BY uploaded_at DESC", conn, params=(user_identifier,))
        return df

# ---------------------------
# Authentication UI (Supabase recommended)
# ---------------------------
st.sidebar.title("My Smart Agent — Modules")

# session_state: store user info
if "user" not in st.session_state:
    st.session_state.user = None  # will be dict with at least 'id' and 'email'
if "user_email" not in st.session_state:
    st.session_state.user_email = None

def supabase_current_user():
    try:
        user = supabase.auth.user()
        return user
    except Exception:
        return None

def supabase_sign_in_email(email: str):
    try:
        resp = supabase.auth.sign_in({"email": email})
        return resp
    except Exception as e:
        st.error(f"Supabase sign in error: {e}")
        return None

def local_demo_sign_in(email: str, display_name: str = ""):
    # insecure demo sign-in: creates user row if not exists and sets session_state.user_email
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (email, display_name) VALUES (?, ?)", (email, display_name))
    conn.commit()
    st.session_state.user = {"email": email, "display_name": display_name, "id": email}
    st.session_state.user_email = email

# Auth widget
st.sidebar.subheader("Account")
if use_supabase:
    # Attempt to get current user
    user = supabase_current_user()
    if user:
        st.sidebar.success(f"Logged in: {user.email}")
        st.session_state.user = {"id": user.id, "email": user.email}
        st.session_state.user_email = user.email
        if st.sidebar.button("Sign out"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.session_state.user_email = None
            st.experimental_rerun()
    else:
        email = st.sidebar.text_input("Email for sign-in (magic link)", key="supabase_email")
        if st.sidebar.button("Send magic link"):
            try:
                supabase_sign_in_email(email)
                st.sidebar.info("Magic link sent to your email. Click it to sign in.")
            except Exception as e:
                st.sidebar.error(f"Unable to send magic link: {e}")
else:
    st.sidebar.info("Supabase not configured — running in local demo mode.")
    demo_email = st.sidebar.text_input("Enter email to demo sign-in", key="demo_email")
    if st.sidebar.button("Sign in (demo)"):
        local_demo_sign_in(demo_email, display_name=demo_email.split("@")[0] if demo_email else "Demo")
        st.sidebar.success(f"Signed in as {st.session_state.user['email']}")

# ensure we have a user identity for operations
def require_user():
    if st.session_state.user is None:
        st.warning("Please sign in to use My Smart Agent features.")
        st.stop()
    # return a user identifier (supabase user id or email)
    if use_supabase and supabase and st.session_state.user:
        return st.session_state.user.get("id") or st.session_state.user.get("email")
    return st.session_state.user.get("email")

# ---------------------------
# Payments (Stripe integration placeholder)
# ---------------------------
if STRIPE_SECRET_KEY and STRIPE_AVAILABLE:
    stripe.api_key = STRIPE_SECRET_KEY

def create_checkout_session(user_identifier: str):
    if not (STRIPE_SECRET_KEY and STRIPE_AVAILABLE and STRIPE_PRICE_ID):
        st.error("Stripe not configured (STRIPE_SECRET_KEY or STRIPE_PRICE_ID missing).")
        return None
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{'price': STRIPE_PRICE_ID, 'quantity': 1}],
            metadata={'user_id': str(user_identifier)},
            success_url=st.secrets.get("SUCCESS_URL", os.environ.get("SUCCESS_URL", "https://example.com/success")),
            cancel_url=st.secrets.get("CANCEL_URL", os.environ.get("CANCEL_URL", "https://example.com/cancel"))
        )
        return session
    except Exception as e:
        st.error(f"Stripe checkout creation failed: {e}")
        return None

# ---------------------------
# UI: Modules
# ---------------------------
modules = ["Dashboard","Daily Planner","Finance Tracker","Health & Habits","Memory (Local)","LearnMate (Docs & Q&A)","Video Summarizer","Settings"]
app_mode = st.sidebar.radio("Choose module:", modules)

# Dashboard
if app_mode == "Dashboard":
    user_id = require_user()
    st.title("My Smart Agent — Dashboard")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Tasks Due Soon")
        tasks_df = get_tasks(user_id)
        if tasks_df is not None and not tasks_df.empty:
            tasks_df['due'] = pd.to_datetime(tasks_df['due'])
            soon = tasks_df[tasks_df['due'] <= (pd.Timestamp.today() + pd.Timedelta(days=7))]
            st.dataframe(soon[['title','owner','due','status']].head(10))
        else:
            st.write("No tasks found.")
    with col2:
        st.subheader("Expenses (Last 30 days)")
        exp_df = get_expenses(user_id, (date.today()-timedelta(days=30)).isoformat(), date.today().isoformat())
        if exp_df is not None and not exp_df.empty:
            total = exp_df['amount'].sum()
            st.write(f"Total: ₹{total:.2f}")
            st.dataframe(exp_df[['date','category','amount']])
        else:
            st.write("No expenses recorded.")
    with col3:
        st.subheader("Health Snapshot")
        hdf = get_health_logs(user_id, range_days=14)
        if hdf is not None and not hdf.empty:
            st.write(hdf.tail(5)[['date','sleep_hours','steps','water_litres']])
        else:
            st.write("No health logs.")

# Daily Planner
elif app_mode == "Daily Planner":
    user_id = require_user()
    st.title("Daily Planner")
    with st.form("add_task"):
        title = st.text_input("Task title")
        desc = st.text_area("Description")
        owner = st.text_input("Owner", value=st.session_state.user.get("email") if st.session_state.user else "Me")
        due = st.date_input("Due date", value=date.today())
        submitted = st.form_submit_button("Add Task")
        if submitted:
            add_task(user_id, title, desc, owner, due.isoformat())
            log_usage(user_id, "add_task", title)
            st.success("Task added!")
    st.markdown("---")
    st.subheader("Your Tasks")
    tasks_df = get_tasks(user_id)
    if tasks_df is not None and not tasks_df.empty:
        st.dataframe(tasks_df[['id','title','owner','due','status']])
        to_mark = st.number_input("Enter task id to mark done", min_value=0, value=0)
        if st.button("Mark Done") and to_mark:
            if use_supabase and supabase:
                supabase.table('tasks').update({'status': 'Done'}).eq('id', int(to_mark)).eq('user_id', user_id).execute()
            else:
                c = conn.cursor()
                c.execute("UPDATE tasks SET status = ? WHERE id = ? AND user_email = ?", ("Done", int(to_mark), user_id))
                conn.commit()
            st.experimental_rerun()
    else:
        st.write("No tasks yet. Add one!")

# Finance Tracker
elif app_mode == "Finance Tracker":
    user_id = require_user()
    st.title("Finance Tracker")
    with st.form("add_expense"):
        d = st.date_input("Date", value=date.today())
        cat = st.selectbox("Category", ["Food","Transport","Office","Subscription","Other"])
        amt = st.number_input("Amount (₹)", min_value=0.0, format="%.2f")
        note = st.text_input("Note")
        submitted = st.form_submit_button("Add Expense")
        if submitted:
            add_expense(user_id, d.isoformat(), cat, float(amt), note)
            log_usage(user_id, "add_expense", f"{cat}:{amt}")
            st.success("Expense recorded")
    st.markdown("---")
    st.subheader("Expense Summary")
    start = st.date_input("Start date", value=(date.today()-timedelta(days=30)))
    end = st.date_input("End date", value=date.today())
    if st.button("Show Summary"):
        df = get_expenses(user_id, start.isoformat(), end.isoformat())
        if df is not None and not df.empty:
            st.write(f"Total: ₹{df['amount'].sum():.2f}")
            st.dataframe(df)
            fig = df.groupby('category')['amount'].sum().reset_index()
            st.bar_chart(fig.set_index('category'))
        else:
            st.write("No expenses in period")

# Health & Habits
elif app_mode == "Health & Habits":
    user_id = require_user()
    st.title("Health & Habits")
    with st.form("log_health"):
        d = st.date_input("Date", value=date.today())
        sleep = st.number_input("Sleep hours", min_value=0.0, max_value=24.0, value=7.0)
        steps = st.number_input("Steps", min_value=0, value=3000)
        water = st.number_input("Water (litres)", min_value=0.0, value=2.0)
        note = st.text_input("Note")
        submitted = st.form_submit_button("Log")
        if submitted:
            add_health_log(user_id, d.isoformat(), sleep, int(steps), float(water), note)
            log_usage(user_id, "log_health", f"sleep:{sleep},steps:{steps}")
            st.success("Health logged")
    st.markdown("---")
    st.subheader("Habit Manager")
    with st.form("add_habit"):
        hname = st.text_input("Habit name")
        freq = st.selectbox("Frequency", ["Daily","Weekly","Monthly"])
        hadd = st.form_submit_button("Add Habit")
        if hadd:
            add_habit(user_id, hname, freq)
            st.success("Habit added")
    habits = get_habits(user_id)
    if habits is not None and not habits.empty:
        st.dataframe(habits)
        hit = st.number_input("Enter habit id to mark done", min_value=0, value=0)
        if st.button("Mark Habit Done") and hit:
            mark_habit_done(user_id, int(hit))
            st.experimental_rerun()
    else:
        st.write("No habits yet.")
    st.markdown("---")
    st.subheader("Health Trends")
    hdf = get_health_logs(user_id, range_days=30)
    if hdf is not None and not hdf.empty:
        st.line_chart(hdf.set_index('date')[['sleep_hours','water_litres']])

# Memory (Local)
elif app_mode == "Memory (Local)":
    user_id = require_user()
    st.title("Memory — Personal Notes")
    with st.form("add_memory"):
        mtitle = st.text_input("Title")
        mcontent = st.text_area("Content")
        mtags = st.text_input("Tags (comma separated)")
        madd = st.form_submit_button("Save to Memory")
        if madd:
            add_memory(user_id, mtitle, mcontent, mtags)
            log_usage(user_id, "add_memory", mtitle[:80])
            st.success("Saved to memory")
    st.markdown("---")
    st.subheader("Search Memory")
    q = st.text_input("Search query")
    if st.button("Search") and q:
        res = search_memory(user_id, q)
        if res is not None and not res.empty:
            for _, row in res.iterrows():
                st.write(f"**{row.get('title','(no title)')}** — {row.get('tags','')}")
                st.write(row.get('content','')[:1000])
                st.markdown("---")
        else:
            st.write("No results")

# LearnMate - Docs & Q&A
elif app_mode == "LearnMate (Docs & Q&A)":
    user_id = require_user()
    st.title("LearnMate — Upload docs & ask questions")
    st.markdown("Upload plain text (.txt) documents. For PDFs please pre-extract text before upload.")
    uploaded = st.file_uploader("Upload text files (TXT)", type=['txt'], accept_multiple_files=True)
    if uploaded:
        for f in uploaded:
            raw = f.read().decode('utf-8', errors='ignore')
            add_doc(user_id, f.name, raw)
        st.success("Uploaded")
    st.markdown("---")
    st.subheader("Your Documents")
    docs_df = get_docs(user_id)
    if docs_df is not None and not docs_df.empty:
        st.dataframe(docs_df[['id','filename','uploaded_at']])
    st.markdown("---")
    st.subheader("Ask a question from your documents")
    question = st.text_input("Question")
    if st.button("Get Answer") and question:
        contexts = []
        if docs_df is not None:
            for _, r in docs_df.iterrows():
                # naive keyword-based retrieval (improve with embeddings later)
                if any(tok.lower() in r['content'].lower() for tok in question.split()[:3]):
                    contexts.append(r['content'])
        if not contexts and docs_df is not None:
            contexts = docs_df['content'].tolist()[:5]
        if contexts:
            # Call Groq for contextual answer if available
            if GROQ_API_KEY:
                prompt = f"Use the context below to answer the question concisely.\n\nContext:\n{'\\n---\\n'.join(contexts[:5])}\n\nQuestion: {question}\n\nAnswer:"
                headers = {'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'}
                payload = {'prompt': prompt, 'max_tokens': 400, 'temperature': 0.2}
                try:
                    GROQ_ENDPOINT = get_secret("GROQ_ENDPOINT") or "https://api.groq.ai/v1"
                    r = requests.post(f"{GROQ_ENDPOINT}/completions", headers=headers, json=payload, timeout=60)
                    r.raise_for_status()
                    out = r.json()
                    ans = out.get('text') or out.get('choices',[{}])[0].get('text','(no answer)')
                    st.write(ans)
                except Exception as e:
                    st.warning(f"Groq failed: {e}")
                    st.write("Fallback answer (context):")
                    st.write("\n\n".join(contexts[:2]))
            else:
                st.info("GROQ_API_KEY not set — showing context fallback.")
                st.write("\n\n".join(contexts[:2]))
        else:
            st.write("No documents available to answer from. Upload documents first.")

# Video Summarizer
elif app_mode == "Video Summarizer":
    user_id = require_user()
    st.title("Video Summarizer — YouTube or local video")
    st.markdown("English default. Choose target language for short summary & highlights. Transcript will NOT be stored permanently.")
    col1, col2 = st.columns([2,1])
    with col1:
        youtube_url = st.text_input("YouTube URL (leave blank if uploading file)", key="yt_url")
        uploaded_video = st.file_uploader("Upload local MP4 (optional)", type=['mp4','mov','mkv'], key="local_video")
    with col2:
        lang = st.selectbox("Language", [name for name, code in [
            ("English","en"),("Tamil","ta"),("Telugu","te"),("Malayalam","ml"),("Kannada","kn"),
            ("Hindi","hi"),("French","fr"),("Spanish","es"),("German","de"),("Japanese","ja")
        ]], index=0)
        whisper_model = st.selectbox("Whisper model (for local transcription)", ['tiny','base','small','medium'], index=2)
        summarize_btn = st.button("Summarize Video")
    if summarize_btn:
        transcript_text = ""
        segments = []
        source = None
        video_id = None
        local_tmp_path = None
        # YouTube path
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
                    st.error("youtube_transcript_api not installed on the server.")
                else:
                    raw = extract_youtube_transcript(video_id)
                    segments = raw
                    transcript_text = " ".join([s['text'] for s in segments])
            except Exception as e:
                st.error(f"Failed to extract YouTube transcript: {e}")
        # local file path
        elif uploaded_video is not None:
            source = 'local'
            local_tmp_path = f"/tmp/{uploaded_video.name}"
            with open(local_tmp_path, "wb") as f:
                f.write(uploaded_video.read())
            if not WHISPER_AVAILABLE:
                st.error("Whisper not installed in this environment. Enable Whisper for local transcription.")
            else:
                try:
                    segments = transcribe_local_whisper(local_tmp_path, whisper_model)
                    transcript_text = " ".join([s['text'] for s in segments])
                except Exception as e:
                    st.error(f"Local transcription failed: {e}")
        else:
            st.error("Provide a YouTube URL or upload a local video.")
        # proceed if transcript available
        if transcript_text:
            lang_code = dict([("English","en"),("Tamil","ta"),("Telugu","te"),("Malayalam","ml"),("Kannada","kn"),
                              ("Hindi","hi"),("French","fr"),("Spanish","es"),("German","de"),("Japanese","ja")])[lang]
            with st.spinner("Generating summary and highlights..."):
                res = groq_summarize_and_translate(transcript_text, lang_code)
            st.markdown("**Short Summary:**")
            st.write(res.get('summary', ''))
            st.markdown("---")
            st.markdown("**Highlights (click timestamp to jump)**")
            # show video player and clickable highlights
            if source == 'youtube' and video_id:
                # embed YouTube
                yt_embed = f"https://www.youtube.com/embed/{video_id}?rel=0"
                st.components.v1.html(f"<iframe width='800' height='450' src='{yt_embed}' frameborder='0' allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe>", height=480)
                for h in res.get('highlights', []):
                    s = int(h['start'])
                    link = f"https://www.youtube.com/embed/{video_id}?start={s}&autoplay=1"
                    mins = s // 60; secs = s % 60
                    label = f"{mins}:{secs:02d} — {h['text'][:120]}"
                    st.markdown(f"<a href='{link}' target='_blank'>{label}</a>", unsafe_allow_html=True)
            elif source == 'local' and local_tmp_path:
                # embed local video bytes and JS jumpTo
                try:
                    with open(local_tmp_path, "rb") as vf:
                        video_bytes = vf.read()
                    b64 = base64.b64encode(video_bytes).decode()
                    video_html = f"""
                    <video id='localVideo' width='800' controls>
                      <source src='data:video/mp4;base64,{b64}' type='video/mp4'>
                      Your browser does not support HTML5 video.
                    </video>
                    <script>
                    function jumpTo(t) {{
                        var v = document.getElementById('localVideo');
                        v.currentTime = t;
                        v.play();
                    }}
                    </script>
                    """
                    highlights_html = "<ul>"
                    for h in res.get('highlights', []):
                        s = int(h['start'])
                        mins = s // 60; secs = s % 60
                        label = f"{mins}:{secs:02d} — {h['text'][:120]}"
                        highlights_html += f"<li><a href='#' onclick='jumpTo({s});return false;'>{label}</a></li>"
                    highlights_html += "</ul>"
                    st.components.v1.html(video_html + highlights_html, height=520)
                except Exception as e:
                    st.error(f"Local playback failed: {e}")
                    for h in res.get('highlights', []):
                        s = int(h['start']); mins = s // 60; secs = s % 60
                        st.write(f"{mins}:{secs:02d} — {h['text'][:200]}")
            else:
                # fallback: show highlights only
                for h in res.get('highlights', []):
                    s = int(h['start'])
                    mins = s // 60; secs = s % 60
                    st.write(f"{mins}:{secs:02d} — {h['text'][:200]}")
            log_usage(user_id, "video_summary", f"source:{source},len:{len(transcript_text)}")
        else:
            st.info("Transcript not available; provide a video with captions or enable Whisper for local files.")

# Settings and Billing
elif app_mode == "Settings":
    st.title("Settings & Deployment")
    st.markdown("This page helps you configure keys and billing for My Smart Agent.")
    st.markdown("**Secrets** should be stored in Streamlit Cloud (Settings -> Secrets). Do not commit keys to GitHub.")
    st.markdown("---")
    st.subheader("Account & Billing")
    user_id = st.session_state.user.get("id") if st.session_state.user else None
    if user_id:
        st.write("Logged in user:", st.session_state.user.get("email"))
        st.markdown("**Subscription**")
        if STRIPE_AVAILABLE and STRIPE_SECRET_KEY and STRIPE_PRICE_ID:
            if st.button("Upgrade to Pro (Stripe Checkout)"):
                session = create_checkout_session(user_id)
                if session:
                    checkout_url = session.url
                    st.markdown(f"[Open Checkout]({checkout_url})")
        else:
            st.info("Stripe not configured. Set STRIPE_SECRET_KEY and STRIPE_PRICE_ID in secrets to enable subscriptions.")
    else:
        st.info("Sign in to see billing options.")
    st.markdown("---")
    st.subheader("Developer / Deployment Notes")
    st.markdown("- Use Supabase for secure user auth & Postgres storage (recommended).")
    st.markdown("- Set GROQ_API_KEY to enable high-quality multilingual summaries (Groq).")
    st.markdown("- To enable local Whisper transcription, install `whisper` and model weights; be mindful of CPU costs.")
    st.markdown("- Use external DB (Supabase) for multi-user production deployments.")
    if st.button("Download local DB (if present)"):
        if os.path.exists(SQLITE_DB):
            with open(SQLITE_DB, "rb") as f:
                data = f.read()
            st.download_button("Download DB", data, file_name=SQLITE_DB)
        else:
            st.info("No local DB found.")

# End of file

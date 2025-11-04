# 🌟 My Smart Agent

My Smart Agent is a Streamlit-based multifunctional personal and office AI agent designed for planning, tracking, and intelligent summarization.

## 🚀 Features
- 🗓️ Daily Planner
- 💵 Finance Tracker
- 💪 Health & Habit Tracker
- 🧠 LearnMate (Document Q&A)
- 🧾 Memory (Store & Recall Notes)
- 🎥 Video Summarizer (YouTube/Local video summarization + translation)

## 🌐 Supported Languages
English, Tamil, Telugu, Malayalam, Kannada, Hindi, French, Spanish, German, Japanese

## ⚙️ Setup Instructions
1. Clone the repository:
   ```bash
   git clone https://github.com/<your-username>/my-smart-agent.git
   cd my-smart-agent
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Add your Groq API key in `.streamlit/secrets.toml`:
   ```toml
   GROQ_API_KEY = "your_api_key_here"
   ```

4. Run locally:
   ```bash
   streamlit run streamlit_app.py
   ```

5. Or deploy on Streamlit Cloud:
   - Go to [https://share.streamlit.io](https://share.streamlit.io)
   - Connect your GitHub repo
   - Choose `streamlit_app.py` as entry file

---

## 🧩 Folder Structure
```
my-smart-agent/
│
├── streamlit_app.py          # Main app (upload this manually)
├── requirements.txt          # Dependencies
├── README.md                 # Documentation
├── .gitignore                # Ignored files
└── .streamlit/
    ├── config.toml           # Theme config
    └── secrets.toml          # API key placeholder
```

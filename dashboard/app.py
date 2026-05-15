import streamlit as st
from pathlib import Path
from datetime import datetime
from tools.sqlite_tracker import DatabaseManager
from tools.telegram_notifier import TelegramNotifier
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(layout="wide", page_title="HuntFlow", page_icon="target")

GRADE_COLORS = {
    "A+": "#00D4AA", "A": "#00D4AA", "B+": "#FFD166", "B": "#FFD166",
    "C+": "#FF9F1C", "C": "#FF9F1C", "D": "#EF233C",
}

@st.cache_resource
def get_db():
    return DatabaseManager()

def format_number(n):
    return f"{n:,}"

def page_overview():
    st.title("Pipeline Overview")
    db = get_db()
    stats = db.get_daily_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Discovered Today", format_number(stats.get("new_count", 0)))
    with col2:
        a, b = stats.get("a_count", 0), stats.get("b_count", 0)
        st.metric("Grade A+B", format_number(a + b))
    with col3:
        st.metric("Applied", format_number(stats.get("applied", 0)))
    with col4:
        st.metric("Reply Rate", f"{stats.get('reply_rate', 0):.1f}%")
    
    st.divider()
    
    pipeline = stats.get("pipeline_status", {})
    funnel_counts = [
        pipeline.get("discovered", 0),
        pipeline.get("applied", 0),
        pipeline.get("replied", 0),
        pipeline.get("interviewing", 0),
        pipeline.get("offer", 0),
    ]
    
    fig = go.Figure(data=[go.Funnel(
        y=["Discovered", "Applied", "Replied", "Interviewing", "Offer"],
        x=funnel_counts,
        marker=dict(color=["#00D4AA", "#FFD166", "#FF9F1C", "#4ECDC4", "#95E1D3"]),
    )])
    fig.update_layout(height=400, title="Pipeline Funnel")
    st.plotly_chart(fig, use_container_width=True)

def page_jobs():
    st.title("Job Board")
    db = get_db()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        grades = st.multiselect("Grade", ["A+", "A", "B+", "B"], default=["A+", "A"])
    with col2:
        min_ats = st.slider("Min ATS", 0, 100, 60)
    with col3:
        search = st.text_input("Search")
    
    try:
        jobs = db.get_jobs(limit=100)
        if grades:
            jobs = [j for j in jobs if j.grade in grades]
        if min_ats > 0:
            jobs = [j for j in jobs if j.score >= min_ats]
        if search:
            jobs = [j for j in jobs if search.lower() in (j.company or "").lower()]
        
        st.info(f"Found {len(jobs)} jobs")
        for job in jobs[:30]:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{job.company}** - {job.title}")
            with col2:
                color = GRADE_COLORS.get(job.grade, "#FFF")
                st.markdown(f"<span style='color:{color}'>**{job.grade}**</span> ({job.score}%)", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error: {e}")

def page_outreach():
    st.title("Outreach Drafts")
    st.warning("WARNING: Human review required before sending")
    
    path = Path("data/outreach")
    if path.exists():
        files = sorted(path.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files[:15]:
            with st.expander(f.stem):
                st.markdown(f.read_text())
    else:
        st.info("No drafts yet")

def page_prep():
    st.title("Interview Prep")
    
    path = Path("data/prep")
    if path.exists():
        files = sorted(path.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files[:10]:
            with st.expander(f.stem):
                st.markdown(f.read_text())
    
    st.divider()
    st.subheader("Generate New")
    col1, col2 = st.columns(2)
    with col1:
        company = st.text_input("Company")
    with col2:
        title = st.text_input("Title")
    if st.button("Generate"):
        st.info(f"Generating for {company}...")

def page_settings():
    st.title("Settings")
    
    st.subheader("Configuration")
    import os
    st.text_input("LLM Provider", value=os.getenv("LLM_PROVIDER", "N/A"), disabled=True)
    st.text_input("DB Path", value=os.getenv("SQLITE_DB_PATH", "./data/huntflow.db"), disabled=True)
    
    st.divider()
    st.subheader("Manual Triggers")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Run Discovery"):
            st.info("Running...")
    with col2:
        if st.button("Run Outreach"):
            st.info("Running...")
    with col3:
        if st.button("Send Digest"):
            st.info("Running...")
    with col4:
        if st.button("Test Telegram"):
            notifier = TelegramNotifier()
            if notifier.test_connection():
                st.success("Telegram OK")
            else:
                st.error("Telegram failed")
    
    st.divider()
    st.subheader("Database Stats")
    try:
        db = get_db()
        stats = db.get_daily_stats()
        col1, col2 = st.columns(2)
        with col1:
            st.json(stats.get("pipeline_status", {}))
        with col2:
            st.json(stats.get("by_source", {}))
    except Exception as e:
        st.error(f"Error: {e}")

def main():
    st.sidebar.title("HuntFlow")
    
    pages = {
        "Pipeline": page_overview,
        "Jobs": page_jobs,
        "Outreach": page_outreach,
        "Interview Prep": page_prep,
        "Settings": page_settings,
    }
    
    selected = st.sidebar.radio("Navigation", list(pages.keys()))
    st.sidebar.divider()
    st.sidebar.caption(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    pages[selected]()

if __name__ == "__main__":
    main()

import streamlit as st
import datetime
import json
import pandas as pd
from PIL import Image

from database import (
    create_tables, get_available_session_dates, get_speeches_for_session,
    get_party_summaries, get_word_metrics, insert_session
)
from analysis import generate_wordcloud_image
from scraper import fetch_and_process_date

# Page Config
st.set_page_config(
    page_title="OpenQueensPark — Ontario Legislature Overview",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Civic Tech Aesthetic & Party Badges
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1A202C;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4A5568;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F7FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .party-pc { color: #003366; font-weight: bold; }
    .party-ndp { color: #FF6600; font-weight: bold; }
    .party-lib { color: #FF0000; font-weight: bold; }
    .party-gpo { color: #009933; font-weight: bold; }
    .speech-box {
        background-color: #FFFFFF;
        border-left: 4px solid #CBD5E0;
        border-radius: 4px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .word-of-day-badge {
        background-color: #EBF8FF;
        color: #2B6CB0;
        border: 1px solid #BEE3F8;
        padding: 0.4rem 1rem;
        border-radius: 20px;
        font-size: 1.2rem;
        font-weight: 600;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# Ensure database tables exist
create_tables()

# Sidebar Setup
st.sidebar.image("https://www.ola.org/sites/default/files/common/image/Wordmark%20Asymmetrical%20Colour_English.svg", width=220)
st.sidebar.title("🏛️ OpenQueensPark")
st.sidebar.markdown("*Automated Ontario Legislature Analytics & AI Summaries*")
st.sidebar.divider()

# Fetch Available Dates
available_dates = get_available_session_dates()

if not available_dates:
    st.sidebar.warning("No Hansard records currently stored.")
    st.info("👋 Welcome to OpenQueensPark! Click below to fetch recent Ontario Legislature Hansard data.")
    if st.button("📥 Fetch Latest Hansard (June 2, 2026 Sample)"):
        with st.spinner("Scraping and analyzing Hansard data from OLA..."):
            fetch_and_process_date("2026-06-02", force_reprocess=True)
            st.rerun()
    st.stop()

# Convert available dates to date objects for Streamlit Calendar
date_objects = [datetime.datetime.strptime(d, "%Y-%m-%d").date() for d in available_dates]
default_date = date_objects[0]

st.sidebar.subheader("📅 Calendar Navigation")
selected_date = st.sidebar.date_input(
    "Select Sitting Date",
    value=default_date,
    min_value=min(date_objects),
    max_value=max(date_objects)
)

selected_date_str = selected_date.strftime("%Y-%m-%d")

# Fetch data for selected date
speeches = get_speeches_for_session(selected_date_str)
summaries = get_party_summaries(selected_date_str)
metrics = get_word_metrics(selected_date_str)

st.sidebar.divider()
st.sidebar.subheader("⚙️ System Status")
st.sidebar.success("Raspberry Pi Node: Online")
st.sidebar.info("Ollama LLM Engine: Local (Llama-3)")

# Trigger manual fetch in sidebar
with st.sidebar.expander("🔄 Scrape Specific Date"):
    custom_date_input = st.date_input("Fetch Date", value=datetime.date(2026, 6, 2))
    if st.button("Fetch & Analyze"):
        with st.spinner(f"Fetching Hansard for {custom_date_input}..."):
            res = fetch_and_process_date(custom_date_input.strftime("%Y-%m-%d"), force_reprocess=True)
            if res:
                st.success("Successfully fetched & analyzed!")
                st.rerun()
            else:
                st.error("Could not fetch Hansard for this date.")

# Main Interface Header
st.markdown(f"<div class='main-header'>Ontario Legislature — {selected_date.strftime('%B %d, %Y')}</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>Daily Proceedings Overview • Parliament 44, Session 1</div>", unsafe_allow_html=True)

# Overview Metric Columns
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("🗣️ Total Speeches", len(speeches) if speeches else 0)

with col2:
    active_mpps = len(set(s['speaker_name'] for s in speeches)) if speeches else 0
    st.metric("🏛️ Active MPPs / Speakers", active_mpps)

with col3:
    wotd = metrics['word_of_the_day'] if metrics else "N/A"
    st.markdown("### 💡 Word of the Day")
    st.markdown(f"<div class='word-of-day-badge'>{wotd}</div>", unsafe_allow_html=True)

st.divider()

# Tabbed Navigation
tab1, tab2, tab3, tab4 = st.tabs([
    "🤖 Neutral AI Summaries",
    "☁️ Word Cloud & N-Grams",
    "📜 Hansard Speech Browser",
    "ℹ️ About OpenQueensPark"
])

# TAB 1: AI Summaries
with tab1:
    st.subheader("Daily Party-by-Party Summaries")
    st.caption("Generated on-device via local LLM (Ollama) to ensure neutral, objective parliamentary oversight.")

    if summaries:
        party_colors = {
            "Progressive Conservative": "#003366",
            "New Democratic Party": "#FF6600",
            "Liberal": "#FF0000",
            "Green Party": "#009933",
            "Independent": "#718096"
        }

        # Render each party summary in an expander / card
        for summ in summaries:
            party_name = summ['party_name']
            summary_text = summ['summary']
            color = party_colors.get(party_name, "#4A5568")

            with st.expander(f"🏛️ {party_name} — Summary", expanded=True):
                st.markdown(f"<h4 style='color: {color}; margin-bottom: 0.5rem;'>{party_name}</h4>", unsafe_allow_html=True)
                st.markdown(summary_text)
    else:
        st.info("No party summaries generated for this date yet. Check back or run the analysis engine.")

# TAB 2: Word Cloud & N-Grams
with tab2:
    st.subheader("Provincial Discourse Tokenization & Visualizations")
    col_wc, col_ngrams = st.columns([1.2, 1])

    with col_wc:
        st.write("**Daily Speech Word Cloud**")
        if speeches:
            combined_text = " ".join([s['text'] for s in speeches])
            img_buf = generate_wordcloud_image(combined_text)
            st.image(img_buf, use_container_width=True)
        else:
            st.info("No speech text available for Word Cloud.")

    with col_ngrams:
        st.write("**Top N-Grams (`ngram_iterator`)**")
        if metrics and metrics.get('top_ngrams'):
            df_ngrams = pd.DataFrame(metrics['top_ngrams'])
            df_ngrams.columns = ["Phrase / Token", "Relative Score", "N-Gram Type"]
            st.dataframe(df_ngrams, use_container_width=True, hide_index=True)
        else:
            st.info("No n-gram metrics available.")

# TAB 3: Hansard Speech Browser
with tab3:
    st.subheader("Browse Daily Speeches & Transcripts")

    if speeches:
        # Filters
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            parties_list = ["All Parties"] + sorted(list(set(s['party_name'] or 'Independent' for s in speeches)))
            selected_party = st.selectbox("Filter by Party", parties_list)

        with f_col2:
            speakers_list = ["All Speakers"] + sorted(list(set(s['speaker_name'] for s in speeches)))
            selected_speaker = st.selectbox("Filter by Speaker", speakers_list)

        with f_col3:
            sections_list = ["All Sections"] + sorted(list(set(s['h2_heading'] for s in speeches if s['h2_heading'])))
            selected_section = st.selectbox("Filter by Section", sections_list)

        # Apply Filters
        filtered_speeches = speeches
        if selected_party != "All Parties":
            filtered_speeches = [s for s in filtered_speeches if (s['party_name'] or 'Independent') == selected_party]
        if selected_speaker != "All Speakers":
            filtered_speeches = [s for s in filtered_speeches if s['speaker_name'] == selected_speaker]
        if selected_section != "All Sections":
            filtered_speeches = [s for s in filtered_speeches if s['h2_heading'] == selected_section]

        st.caption(f"Showing {len(filtered_speeches)} of {len(speeches)} speeches")

        for sp in filtered_speeches[:50]: # Paginate first 50
            party_str = sp['party_name'] or 'Independent'
            h2 = sp['h2_heading'] or 'General'
            h3 = f" → {sp['h3_heading']}" if sp['h3_heading'] else ""

            with st.container():
                st.markdown(f"""
                <div class='speech-box'>
                    <strong>{sp['speaker_name']}</strong> ({party_str}) — <em>{sp['constituency'] or 'Ontario'}</em><br/>
                    <small style='color: #718096;'>Section: {h2}{h3} | Time: {sp['timestamp'] or 'N/A'}</small>
                    <p style='margin-top: 0.5rem;'>{sp['text'][:400]}{'...' if len(sp['text']) > 400 else ''}</p>
                </div>
                """, unsafe_allow_html=True)
                if len(sp['text']) > 400:
                    with st.expander("Read full speech"):
                        st.write(sp['text'])
    else:
        st.info("No speeches available for the selected date.")

# TAB 4: About
with tab4:
    st.subheader("About OpenQueensPark")
    st.markdown("""
    **OpenQueensPark** is an open-source civic-tech platform modeled after the federal [openparliament.ca](https://openparliament.ca).
    
    ### Key Features:
    - **Local Hosting**: Runs autonomously on a local Raspberry Pi node.
    - **No Paid APIs**: Utilizes on-device **Ollama** LLMs (`llama3`) for zero-cost, neutral daily summaries.
    - **Custom Tokenization**: Custom `ngram_iterator` for daily n-gram analysis and "Word of the Day" metrics.
    - **Secure Exposure**: Exposed securely to the web via **Cloudflare Tunnel** (`openqueenspark.ca`).
    - **Public Transparency**: Tracks political discourse in the Ontario Legislature with zero commercial tracking.
    """)

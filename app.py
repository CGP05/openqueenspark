import datetime
import os

import pandas as pd
import streamlit as st

from src.analysis import generate_wordcloud_image
from src.database import (
    create_tables,
    get_available_session_dates,
    get_party_summaries,
    get_speeches_for_session,
    get_word_metrics,
    search_speeches,
    search_bills,
    get_bills_for_session,
)
from src.scraper import fetch_and_process_date

# Ontario party seat counts (approximate current composition)
PARTY_SEATS = {
    "Progressive Conservative": 83,
    "New Democratic Party": 28,
    "Liberal": 8,
    "Green Party": 2,
    "Independent": 1,
}

# Page Config
st.set_page_config(
    page_title="OpenQueensPark — Ontario Legislature Overview",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for OpenParliament-style layout
st.markdown(
    """
<style>
    /* GLOBAL OVERRIDES */
    * {
        background-color: transparent !important;
    }
    
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        background-color: #FFFFFF !important;
    }
    
    /* Hide Streamlit header and toolbar */
    [data-testid="stAppHeader"],
    [data-testid="stToolbar"],
    header,
    .stDecoration {
        display: none !important;
    }
    
    /* Hide sidebar completely and reclaim space */
    [data-testid="stSidebar"],
    [data-testid="stSidebarNav"],
    .sidebar,
    .st-emotion-cache-1wmy9hl {
        display: none !important;
        width: 0 !important;
    }
    
    /* Main container - full width, white background */
    [data-testid="stMainBlockContainer"] {
        background-color: #FFFFFF !important;
        width: 100% !important;
        max-width: 100% !important;
        padding: 2rem 3rem !important;
    }
    
    /* Streamlit text, buttons, etc. */
    .stText, .stMarkdown, .stMetric {
        background-color: transparent !important;
    }
    
    /* Remove Streamlit's default margins and padding */
    .st-emotion-cache-1y4p8pa {
        padding: 0 !important;
    }
    
    /* Navigation bar - Streamlit compatible */
    .navbar {
        background: linear-gradient(90deg, #2C5282 0%, #2D5A8C 100%) !important;
        padding: 1rem 2rem !important;
        margin: 0 -3rem 2rem -3rem !important;
        margin-left: calc(-100vw / 2 + 100% / 2) !important;
        margin-right: calc(-100vw / 2 + 100% / 2) !important;
        width: 100vw !important;
        color: #FFFFFF !important;
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
    }
    
    .navbar-brand {
        font-size: 1.3rem !important;
        font-weight: 800 !important;
        letter-spacing: -0.5px !important;
        color: #FFFFFF !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    .navbar-menu {
        display: flex !important;
        gap: 2rem !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        color: #FFFFFF !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    .navbar-menu span {
        color: #FFFFFF !important;
        background-color: transparent !important;
    }
    
    /* Content area - white background */
    .content-wrapper {
        background: #FFFFFF !important;
        color: #1A202C !important;
        padding: 0 2rem !important;
    }
    
    /* Headers */
    .main-header {
        font-size: 2.8rem !important;
        font-weight: 800 !important;
        color: #1A202C !important;
        margin: 2rem 0 0.25rem 0 !important;
        letter-spacing: -0.8px !important;
    }
    
    .sub-header {
        font-size: 1.1rem !important;
        color: #718096 !important;
        margin-bottom: 2.5rem !important;
        font-weight: 400 !important;
    }
    
    .tagline {
        font-size: 2rem !important;
        font-weight: 700 !important;
        color: #1A202C !important;
        margin: 2.5rem 0 2rem 0 !important;
        text-align: center !important;
    }
    
    /* Disclaimer box - matches openparliament */
    .disclaimer {
        background: #FEF2F2 !important;
        border: 1px solid #FECACA !important;
        border-left: 5px solid #DC2626 !important;
        border-radius: 6px !important;
        padding: 1.25rem 1.5rem !important;
        margin: 2rem 0 2.5rem 0 !important;
        font-size: 0.95rem !important;
        color: #7F1D1D !important;
        line-height: 1.6 !important;
    }
    
    .disclaimer strong {
        font-weight: 700 !important;
    }
    
    /* Stats cards */
    .stat-card {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 2rem 1.5rem !important;
        text-align: center !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08) !important;
        transition: all 0.2s ease !important;
    }
    
    .stat-card:hover {
        border-color: #2C5282 !important;
        box-shadow: 0 4px 12px rgba(44, 82, 130, 0.1) !important;
    }
    
    .stat-value {
        font-size: 2.8rem !important;
        font-weight: 800 !important;
        color: #2C5282 !important;
        margin: 0.5rem 0 !important;
        letter-spacing: -0.5px !important;
    }
    
    .stat-label {
        font-size: 0.75rem !important;
        color: #718096 !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 1.5px !important;
    }
    
    /* Word of the day section */
    .word-of-day-section {
        background: linear-gradient(135deg, #2C5282 0%, #4A90A4 100%) !important;
        color: white !important;
        padding: 2rem 1.5rem !important;
        border-radius: 12px !important;
        text-align: center !important;
        box-shadow: 0 4px 16px rgba(44, 82, 130, 0.25) !important;
        transition: box-shadow 0.2s ease !important;
    }
    
    .word-of-day-section:hover {
        box-shadow: 0 6px 20px rgba(44, 82, 130, 0.35) !important;
    }
    
    .word-of-day-label {
        font-size: 0.8rem !important;
        font-weight: 700 !important;
        opacity: 0.95 !important;
        margin-bottom: 0.75rem !important;
        letter-spacing: 1.5px !important;
        text-transform: uppercase !important;
        color: white !important;
    }
    
    .word-of-day-badge {
        font-size: 2.2rem !important;
        font-weight: 800 !important;
        letter-spacing: 0.5px !important;
        color: white !important;
    }
    
    /* Divider */
    .divider {
        height: 2px !important;
        background: linear-gradient(90deg, transparent, #E2E8F0, transparent) !important;
        margin: 3rem 0 !important;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.6rem !important;
        font-weight: 800 !important;
        color: #1A202C !important;
        border-bottom: 3px solid #2C5282 !important;
        padding-bottom: 1rem !important;
        margin: 3rem 0 2rem 0 !important;
    }
    
    .subsection-header {
        font-size: 1.25rem;
        font-weight: 700;
        color: #2D3748;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid #E2E8F0;
    }
    
    /* Party blocks */
    .party-block {
        margin: 1.25rem 0 !important;
        padding: 1.5rem !important;
        border-radius: 8px !important;
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-left: 5px solid !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
    }
    
    .party-block:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
    }
    
    .party-name {
        font-weight: 800 !important;
        font-size: 1.1rem !important;
        margin-bottom: 1rem !important;
    }
    
    .party-text {
        font-size: 0.95rem !important;
        line-height: 1.7 !important;
        color: #2D3748 !important;
    }
    
    /* Speech items */
    .speech-item {
        margin: 1rem 0 !important;
        padding: 1.25rem !important;
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 6px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
    }
    
    .speech-item:hover {
        border-color: #2C5282 !important;
        box-shadow: 0 4px 12px rgba(44, 82, 130, 0.15) !important;
    }
    
    .speech-meta {
        font-size: 0.85rem !important;
        color: #718096 !important;
        margin-bottom: 0.75rem !important;
        font-weight: 500 !important;
    }
    
    .speaker-name {
        font-weight: 800 !important;
        color: #1A202C !important;
    }
    
    .speech-text {
        font-size: 0.95rem !important;
        line-height: 1.7 !important;
        color: #2D3748 !important;
    }
    
    /* Word cloud section */
    .wordcloud-section {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 2rem !important;
        text-align: center !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08) !important;
        transition: box-shadow 0.2s ease !important;
    }
    
    .wordcloud-section:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.12) !important;
    }
    
    .wordcloud-title {
        font-size: 1.15rem !important;
        font-weight: 800 !important;
        color: #1A202C !important;
        margin-bottom: 1.5rem !important;
        letter-spacing: -0.3px !important;
    }
    
    /* Footer */
    .footer {
        background: #2C5282 !important;
        color: white !important;
        padding: 2.5rem 2rem !important;
        margin: 4rem 0 0 0 !important;
        font-size: 0.9rem !important;
        border-top: 1px solid #1E40AF !important;
        border-radius: 8px !important;
    }
    
    .footer-content {
        max-width: 1200px !important;
        margin: 0 auto !important;
    }
    
    .footer a {
        color: #93C5FD !important;
        text-decoration: none !important;
    }
    
    .footer a:hover {
        text-decoration: underline !important;
    }
    
    /* Divider */
    .divider {
        height: 2px;
        background: linear-gradient(90deg, transparent, #E2E8F0, transparent);
        margin: 2rem 0;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Ensure database tables exist
create_tables()  # type: ignore

# Navigation Header
st.markdown(
    """
<div class="navbar">
    <div class="navbar-brand">openqueenspark.ca</div>
    <div class="navbar-menu">
        <span>MPPs</span>
        <span>Bills</span>
        <span>Debates</span>
        <span>Committees</span>
        <span>About</span>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# Sidebar Setup
st.sidebar.title("OpenQueensPark")
st.sidebar.markdown("*Ontario Legislature Daily Proceedings*")
st.sidebar.divider()

# Sidebar API Keys Configuration
with st.sidebar.expander("LLM API Settings", expanded=False):
    gemini_input = st.text_input(
        "Google AI Studio API Key",
        type="password",
        value=os.getenv("GEMINI_API_KEY", ""),
    )
    openrouter_input = st.text_input(
        "OpenRouter API Key", type="password", value=os.getenv("OPENROUTER_API_KEY", "")
    )

    if gemini_input:
        os.environ["GEMINI_API_KEY"] = gemini_input
    if openrouter_input:
        os.environ["OPENROUTER_API_KEY"] = openrouter_input

    if gemini_input or openrouter_input:
        st.success("API Key Active!")

    # Fetch Available Dates
    available_dates = get_available_session_dates()

if not available_dates:
    st.sidebar.warning("No Hansard records currently stored.")
    st.info(
        "Welcome to OpenQueensPark! Click below to fetch recent Ontario Legislature Hansard data."
    )
    if st.button("Fetch Latest Hansard (June 2, 2026 Sample)"):
        with st.spinner("Scraping and analyzing Hansard data from OLA..."):
            fetch_and_process_date("2026-06-02", force_reprocess=True)
            st.rerun()
    st.stop()

# Convert available dates to date objects for Streamlit Calendar
date_objects = [
    datetime.datetime.strptime(d, "%Y-%m-%d")
    .replace(tzinfo=datetime.timezone.utc)
    .date()
    for d in available_dates
]
default_date = date_objects[0]

st.sidebar.subheader("Calendar Navigation")
selected_date = st.sidebar.date_input(
    "Select Sitting Date",
    value=default_date,
    min_value=min(date_objects),
    max_value=max(date_objects),
)

selected_date_str = selected_date.strftime("%Y-%m-%d")

# Fetch data for selected date
speeches = get_speeches_for_session(selected_date_str)  # type: ignore
summaries = get_party_summaries(selected_date_str)  # type: ignore
metrics = get_word_metrics(selected_date_str)  # type: ignore

st.sidebar.divider()
st.sidebar.subheader("System Status")
st.sidebar.success("Database Status: Online")

active_engine = "Rule-based Fallback"
if os.getenv("GEMINI_API_KEY"):
    active_engine = "Google AI Studio (Gemini 2.0)"
elif os.getenv("OPENROUTER_API_KEY"):
    active_engine = "OpenRouter AI"
st.sidebar.info(f"AI Engine: {active_engine}")

# Trigger manual fetch in sidebar
with st.sidebar.expander("Scrape Specific Date"):
    custom_date_input = st.date_input("Fetch Date", value=datetime.date(2026, 6, 2))
    if st.button("Fetch & Analyze"):
        with st.spinner(f"Fetching Hansard for {custom_date_input}..."):
            res = fetch_and_process_date(
                custom_date_input.strftime("%Y-%m-%d"), force_reprocess=True
            )
            if res:
                st.success("Successfully fetched & analyzed!")
                st.rerun()
            else:
                st.error("Could not fetch Hansard for this date.")

# Main Interface Header
st.markdown(
    "<div class='main-header'>Ontario Legislature</div>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<div class='sub-header'>{selected_date.strftime('%B %d, %Y')} • Daily Proceedings</div>",
    unsafe_allow_html=True,
)

st.markdown(
    "<div class='tagline'>Keep tabs on Parliament.</div>",
    unsafe_allow_html=True,
)

# Disclaimer notice like OpenParliament
st.markdown(
    """
<div class='disclaimer'>
<strong>Computer-Generated Summary</strong> — Usually accurate, but every now and then it'll contain inaccuracies or total fabrications.
</div>
""",
    unsafe_allow_html=True,
)

# Navigation Tabs
tab_speeches, tab_bills, tab_search = st.tabs(["📜 Daily Proceedings", "📋 Bills & Legislation", "🔍 Search"])

with tab_speeches:
    with tab_bills:
        st.markdown("""
        <div style='text-align: center; margin: 2rem 0 1.5rem 0;'>
            <h2 style='font-size: 1.8rem; font-weight: 700; color: #1A202C; margin: 0;'>Bills &amp; Legislation</h2>
            <p style='color: #718096; margin-top: 0.5rem;'>Bills mentioned in today's proceedings.</p>
        </div>
        """, unsafe_allow_html=True)
        # Fetch bills for this session
        session_bills = []
        if session_id:
            session_bills = get_bills_for_session(session_id)
        if session_bills:
            for bill in session_bills:
                bill_num = bill.get("bill_number", "Unknown Bill")
                sponsor = bill.get("sponsor_name") or "Unknown Sponsor"
                stage = bill.get("stage") or "Introduced"
                st.markdown(f"""
                <div style='background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.5rem; margin: 1rem 0;'>
                    <div style='font-size: 1.2rem; font-weight: 700; color: #003366;'>{bill_num}</div>
                    <div style='color: #718096; font-size: 0.9rem; margin-top: 0.5rem;'>
                        Sponsor: {sponsor} | Stage: {stage}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No bills recorded for this session yet. Run the scraper to extract bill mentions from Hansard transcripts.")
    
        # Search bills database
        st.markdown("<hr style='margin: 2rem 0; border-color: #E2E8F0;'>", unsafe_allow_html=True)
        st.markdown("<h3 style='color: #1A202C;'>Search Bills Database</h3>", unsafe_allow_html=True)
        bill_search_query = st.text_input("Search bills by number, name, or sponsor:", key="bill_search")
        if bill_search_query and st.button("Search Bills", key="search_bills_btn"):
            results = search_bills(bill_search_query)
            if results:
                st.write(f"Found {len(results)} bill(s):")
                for b in results[:10]:
                    st.markdown(f"**{b.get('bill_number', 'N/A')}** — {b.get('bill_name', 'N/A')} (Sponsor: {b.get('sponsor_name', 'N/A')})")
            else:
                st.info("No bills found matching your search.")
    
    with tab_search:
        st.markdown("""
        <div style='text-align: center; margin: 2rem 0 1.5rem 0;'>
            <h2 style='font-size: 1.8rem; font-weight: 700; color: #1A202C; margin: 0;'>Search Hansard</h2>
            <p style='color: #718096; margin-top: 0.5rem;'>Search across all speeches using full-text search.</p>
        </div>
        """, unsafe_allow_html=True)
        speech_search_query = st.text_input("Search speeches:", key="speech_search")
        if speech_search_query and st.button("Search", key="search_speeches_btn"):
            results = search_speeches(speech_search_query, limit=20, session_date=selected_date)
            if results:
                st.write(f"Found {len(results)} speech(es):")
                for sp in results[:10]:
                    snippet = sp.get("snippet", sp.get("text", ""))[:300]
                    speaker = sp.get("speaker_name", "Unknown")
                    party = sp.get("party_name", "Independent")
                    st.markdown(f"""
                    <div style='background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1rem; margin: 0.5rem 0;'>
                        <div style='font-weight: 600; color: #003366;'>{speaker} ({party})</div>
                        <div style='color: #4A5568; font-size: 0.9rem;'>...{snippet}...</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No speeches found matching your search.")
    
    # Overview Stats Row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f"""
        <div class='stat-card'>
            <div class='stat-value'>{len(speeches) if speeches else 0}</div>
            <div class='stat-label'>Total Speeches</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col2:
        active_mpps = len({s["speaker_name"] for s in speeches}) if speeches else 0
        st.markdown(
            f"""
        <div class='stat-card'>
            <div class='stat-value'>{active_mpps}</div>
            <div class='stat-label'>Active MPPs</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col3:
        wotd = metrics["word_of_the_day"] if metrics else "Parliament"
        st.markdown(
            f"""
        <div class='word-of-day-section'>
            <div class='word-of-day-label'>WORD OF THE DAY</div>
            <div class='word-of-day-badge'>{wotd}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    
    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    
    
    # Helper: Organize speeches by section (h2_heading) then by party
    def organize_by_section_and_party(speeches):
        """Group speeches by h2_heading (section), then by party."""
        sections = {}
        for sp in speeches:
            section = sp.get("h2_heading", "General Proceedings")
            party = sp.get("party_name", "Independent")
            if section not in sections:
                sections[section] = {}
            if party not in sections[section]:
                sections[section][party] = []
            sections[section][party].append(sp)
        return sections
    
    
    # Party colors for OpenParliament-style display
    PARTY_COLORS = {
        "Progressive Conservative": "#003366",
        "New Democratic Party": "#FF6600",
        "Liberal": "#FF0000",
        "Green Party": "#009933",
        "Independent": "#718096",
        "Non-Partisan / Presiding Officer": "#4A5568",
    }
    
    PARTY_DISPLAY_ORDER = [
        "Progressive Conservative",
        "New Democratic Party",
        "Liberal",
        "Green Party",
        "Independent",
        "Non-Partisan / Presiding Officer",
    ]
    
    # Main content heading
    st.markdown(
        """
    <div style='text-align: center; margin: 2.5rem 0 2rem 0;'>
        <h2 style='font-size: 1.8rem; font-weight: 700; color: #1A202C; margin: 0;'>What They're Talking About</h2>
        <p style='color: #718096; margin-top: 0.5rem;'>The latest House transcript from {}, showing what's being debated.</p>
    </div>
    """.format(selected_date.strftime("%B %d")),
        unsafe_allow_html=True,
    )
    
    # Main content area - OpenParliament style: Section → Topic → Party breakdown
    if speeches:
        sections = organize_by_section_and_party(speeches)
    
        for section_name in sorted(sections.keys()):
            if section_name.strip() and section_name.lower() != "general proceedings":
                st.markdown(
                    f"<div class='section-header'>{section_name}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<div class='section-header'>Proceedings</div>", unsafe_allow_html=True
                )
    
            # For each section, show party breakdowns
            section_parties = sections[section_name]
    
            # Sort parties by seat count order
            sorted_parties = sorted(
                section_parties.keys(),
                key=lambda x: (
                    PARTY_DISPLAY_ORDER.index(x) if x in PARTY_DISPLAY_ORDER else 999
                ),
            )
    
            for party_name in sorted_parties:
                party_speeches = section_parties[party_name]
                if not party_speeches:
                    continue
    
                color = PARTY_COLORS.get(party_name, "#4A5568")
                short_name = party_name.replace("Progressive Conservative", "PC").replace(
                    "New Democratic Party", "NDP"
                )
    
                # Party header with colored left border
                st.markdown(
                    f"""
                <div class='party-block' style='border-left-color: {color};'>
                    <div class='party-name' style='color: {color};'>{short_name}</div>
                """,
                    unsafe_allow_html=True,
                )
    
                # Show first few speeches as topic summaries
                for idx, sp in enumerate(party_speeches[:3]):
                    h3 = sp.get("h3_heading", "")
                    topic = h3 if h3 else "Remarks"
                    speaker = sp.get("speaker_name", "MPP")
                    text_preview = sp.get("text", "")[:300]
    
                    st.markdown(
                        f"""
                    <div class='speech-item'>
                        <div class='speech-meta'>
                            <span class='speaker-name'>{speaker}</span> — {topic}
                        </div>
                        <div>{text_preview}{"..." if len(sp["text"]) > 300 else ""}</div>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
    
                if len(party_speeches) > 3:
                    with st.expander(
                        f"Show {len(party_speeches) - 3} more from {short_name}"
                    ):
                        for sp in party_speeches[3:]:
                            h3 = sp.get("h3_heading", "")
                            topic = h3 if h3 else "Remarks"
                            speaker = sp.get("speaker_name", "MPP")
    
                            st.markdown(
                                f"""
                            <div class='speech-item'>
                                <div class='speech-meta'>
                                    <span class='speaker-name'>{speaker}</span> — {topic}
                                </div>
                                <div>{sp["text"][:400]}{"..." if len(sp["text"]) > 400 else ""}</div>
                            </div>
                            """,
                                unsafe_allow_html=True,
                            )
    
                st.markdown("</div>", unsafe_allow_html=True)
    
    # Bills / Legislation Section (extract from h3_headings that look like bills)
    bill_speeches = [
        s
        for s in speeches
        if s.get("h3_heading")
        and (
            "bill" in s.get("h3_heading", "").lower()
            or "act" in s.get("h3_heading", "").lower()
        )
    ]
    if bill_speeches:
        st.markdown(
            "<div class='section-header'>Bills & Legislation</div>", unsafe_allow_html=True
        )
    
        # Group bills by bill name
        bills = {}
        for sp in bill_speeches:
            bill_name = sp.get("h3_heading", "Unknown Bill")
            party = sp.get("party_name", "Independent")
            if bill_name not in bills:
                bills[bill_name] = {}
            if party not in bills[bill_name]:
                bills[bill_name][party] = []
            bills[bill_name][party].append(sp)
    
        for bill_name in sorted(bills.keys()):
            st.markdown(
                f"<div class='topic-header'>{bill_name}</div>", unsafe_allow_html=True
            )
    
            for party_name in sorted(
                bills[bill_name].keys(),
                key=lambda x: (
                    PARTY_DISPLAY_ORDER.index(x) if x in PARTY_DISPLAY_ORDER else 999
                ),
            ):
                party_speeches = bills[bill_name][party_name]
                color = PARTY_COLORS.get(party_name, "#4A5568")
                short_name = party_name.replace("Progressive Conservative", "PC").replace(
                    "New Democratic Party", "NDP"
                )
    
                st.markdown(
                    f"""
                <div class='party-block' style='border-left-color: {color};'>
                    <div class='party-name' style='color: {color};'>{short_name}</div>
                """,
                    unsafe_allow_html=True,
                )
    
                for sp in party_speeches[:2]:
                    speaker = sp.get("speaker_name", "MPP")
                    text = sp.get("text", "")[:250]
                    st.markdown(
                        f"<div class='party-text'><strong>{speaker}:</strong> {text}...</div>",
                        unsafe_allow_html=True,
                    )
    
                st.markdown("</div>", unsafe_allow_html=True)
    
    # Petitions & Matters of Privilege Section
    petition_speeches = [
        s
        for s in speeches
        if s.get("h3_heading")
        and any(
            kw in s.get("h3_heading", "").lower()
            for kw in ["petition", "privilege", "matter"]
        )
    ]
    if petition_speeches:
        st.markdown(
            "<div class='section-header'>Petitions & Matters</div>", unsafe_allow_html=True
        )
        for sp in petition_speeches[:10]:
            speaker = sp.get("speaker_name", "MPP")
            party = sp.get("party_name", "Independent")
            topic = sp.get("h3_heading", "")
            color = PARTY_COLORS.get(party, "#4A5568")
            st.markdown(
                f"""
            <div class='speech-item'>
                <div class='speech-meta'>
                    <span class='speaker-name' style='color: {color};'>{speaker}</span> ({party}) — {topic}
                </div>
                <div>{sp["text"][:300]}{"..." if len(sp["text"]) > 300 else ""}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )
    
    # Speech Browser (collapsible)
    with st.expander("Browse All Speeches (Searchable)"):
        if speeches:
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                parties_list = ["All Parties"] + sorted(
                    {s["party_name"] or "Independent" for s in speeches}
                )
                selected_party = st.selectbox("Filter by Party", parties_list)
            with f_col2:
                speakers_list = ["All Speakers"] + sorted(
                    {s["speaker_name"] for s in speeches}
                )
                selected_speaker = st.selectbox("Filter by Speaker", speakers_list)
            with f_col3:
                sections_list = ["All Sections"] + sorted(
                    {s["h2_heading"] for s in speeches if s["h2_heading"]}
                )
                selected_section = st.selectbox("Filter by Section", sections_list)
    
            filtered_speeches = speeches
            if selected_party != "All Parties":
                filtered_speeches = [
                    s
                    for s in filtered_speeches
                    if (s["party_name"] or "Independent") == selected_party
                ]
            if selected_speaker != "All Speakers":
                filtered_speeches = [
                    s for s in filtered_speeches if s["speaker_name"] == selected_speaker
                ]
            if selected_section != "All Sections":
                filtered_speeches = [
                    s for s in filtered_speeches if s["h2_heading"] == selected_section
                ]
    
            st.caption(f"Showing {len(filtered_speeches)} of {len(speeches)} speeches")
    
            for sp in filtered_speeches[:50]:
                party_str = sp["party_name"] or "Independent"
                h2 = sp["h2_heading"] or "General"
                h3 = f" → {sp['h3_heading']}" if sp["h3_heading"] else ""
                color = PARTY_COLORS.get(party_str, "#4A5568")
    
                st.markdown(
                    f"""
                <div class='speech-item'>
                    <div class='speech-meta'>
                        <span class='speaker-name' style='color: {color};'>{sp["speaker_name"]}</span> ({party_str}) — <em>{sp["constituency"] or "Ontario"}</em>
                        <br/>Section: {h2}{h3} | Time: {sp["timestamp"] or "N/A"}
                    </div>
                    <div>{sp["text"][:500]}{"..." if len(sp["text"]) > 500 else ""}</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
    
    # Analytics & Visualizations Section
    st.markdown(
        """
    <div style='text-align: center; margin: 3rem 0 2rem 0;'>
        <h2 style='font-size: 1.8rem; font-weight: 700; color: #1A202C; margin: 0;'>What's Being Discussed</h2>
        <p style='color: #718096; margin-top: 0.5rem;'>Top topics and phrases from today's debate.</p>
    </div>
    """,
        unsafe_allow_html=True,
    )
    
    col_wc, col_ngrams = st.columns([1.2, 1])
    with col_wc:
        st.markdown(
            """
        <div class='wordcloud-section'>
            <div class='wordcloud-title'>Daily Speech Word Cloud</div>
        """,
            unsafe_allow_html=True,
        )
        if speeches:
            combined_text = " ".join([s["text"] for s in speeches])
            img_buf = generate_wordcloud_image(combined_text)
            st.image(img_buf, width=600)
        else:
            st.info("No speech text available for Word Cloud.")
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col_ngrams:
        st.markdown(
            """
        <div style='background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 2rem; text-align: left;'>
            <div style='font-size: 1.2rem; font-weight: 700; color: #1A202C; margin-bottom: 1rem;'>Top Phrases</div>
        """,
            unsafe_allow_html=True,
        )
        if metrics and metrics.get("top_ngrams"):
            df_ngrams = pd.DataFrame(metrics["top_ngrams"])
            df_ngrams.columns = ["Phrase", "Score", "Type"]
            st.dataframe(df_ngrams, hide_index=True, use_container_width=True)
        else:
            st.info("No phrase metrics available.")
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    
    st.markdown(
        """
    <div class='footer'>
        <div class='footer-content'>
            <p style='margin-bottom: 1rem;'>
                <strong>OpenQueensPark</strong> is an open-source civic-tech platform tracking Ontario's provincial legislature.
            </p>
            <p style='font-size: 0.85rem; opacity: 0.9;'>
                Automated Ontario Legislature Analytics • Neutral AI Summaries • Computer-Generated Summaries • 
                <a href='https://openparliament.ca'>Inspired by OpenParliament.ca</a>
            </p>
        </div>
    </div>
""",
    unsafe_allow_html=True,
)

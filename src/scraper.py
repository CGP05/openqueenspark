import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import time
import os

from src.database import (
    create_tables, insert_session, insert_speaker, insert_speech,
    save_party_summary, save_word_metrics, get_connection
)
from src.parser import parse_hansard_html
from src.analysis import analyze_speeches
from src.summarizer import generate_all_party_summaries

BASE_URL = "https://www.ola.org"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) OpenQueensPark/1.0 (Civic Tech Project; +https://openqueenspark.ca)'
}
REQUEST_DELAY = 1.5 # Respectful request delay for OLA servers

def construct_hansard_url(date_str, parliament=44, session=1):
    """
    Constructs canonical OLA Hansard URL for a given YYYY-MM-DD date.
    Example: https://www.ola.org/en/legislative-business/house-documents/parliament-44/session-1/2026-06-02/hansard
    """
    return f"{BASE_URL}/en/legislative-business/house-documents/parliament-{parliament}/session-{session}/{date_str}/hansard"

def fetch_and_process_date(date_str, parliament=44, session_number=1, force_reprocess=False):
    """
    Fetches Hansard transcript for a date, parses speeches, runs analysis & Ollama summaries,
    and saves all structured data to SQLite.
    """
    create_tables()
    url = construct_hansard_url(date_str, parliament, session_number)

    # Check if session already exists
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM sessions WHERE session_date = ?', (date_str,))
    existing_session = cursor.fetchone()
    conn.close()

    if existing_session and not force_reprocess:
        print(f"Session for {date_str} already exists in database. Skipping fetch.")
        return existing_session['id']

    print(f"Fetching Hansard from OLA: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        if response.status_code == 404:
            print(f"No Hansard document found for date {date_str} (Legislature was likely not sitting).")
            return None
        response.raise_for_status()

        print(f"Parsing transcript content for {date_str}...")
        parsed = parse_hansard_html(response.content, source_url=url)

        if not parsed['speeches']:
            print(f"Warning: No speeches could be extracted for {date_str}.")
            return None

        # Insert session record
        session_id = insert_session(date_str, parliament, session_number, url)

        # Insert speakers and speeches
        print(f"Inserting {len(parsed['speeches'])} speeches into database...")
        for sp in parsed['speeches']:
            speaker_id = insert_speaker(
                name=sp['speaker_name'],
                party_name=sp['party_name'],
                constituency=sp['constituency'],
                title=sp['title']
            )
            insert_speech(
                speaker_id=speaker_id,
                session_id=session_id,
                text=sp['text'],
                h2_heading=sp['h2_heading'],
                h3_heading=sp['h3_heading'],
                timestamp=sp['timestamp'],
                sequence=sp['sequence']
            )

        # Run text analysis & n-gram generation
        print(f"Running n-gram text analysis for {date_str}...")
        analysis_result = analyze_speeches(parsed['speeches'])
        save_word_metrics(
            session_id=session_id,
            word_of_the_day=analysis_result['word_of_the_day'],
            top_ngrams=analysis_result['top_ngrams']
        )
        print(f"Word of the Day: '{analysis_result['word_of_the_day']}'")

        # Run Ollama party summaries
        print(f"Generating neutral party-by-party summaries...")
        summaries = generate_all_party_summaries(parsed['speeches'])
        for party_name, summary in summaries.items():
            save_party_summary(session_id, party_name, summary, model_used='ollama')

        print(f"Successfully processed and stored Hansard for {date_str}!")
        return session_id

    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def backfill_recent_days(days_back=7):
    """
    Backfills Hansards for the last N days.
    """
    today = datetime.now().date()
    for i in range(days_back):
        target_date = today - timedelta(days=i)
        # Skip weekends (Legislature sits Mon-Thu)
        if target_date.weekday() >= 5:
            continue
        date_str = target_date.strftime('%Y-%m-%d')
        print(f"\nChecking date {date_str}...")
        fetch_and_process_date(date_str)
        time.sleep(REQUEST_DELAY)

if __name__ == "__main__":
    # Test with known sitting date e.g. 2026-06-02
    test_date = "2026-06-02"
    fetch_and_process_date(test_date, force_reprocess=True)

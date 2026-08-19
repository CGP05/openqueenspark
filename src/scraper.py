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
REQUEST_DELAY = 1.0

def construct_hansard_url(date_str, parliament=44, session=1):
    return f"{BASE_URL}/en/legislative-business/house-documents/parliament-{parliament}/session-{session}/{date_str}/hansard"

def fetch_and_process_date(date_str, parliament=44, session_number=1, force_reprocess=False):
    create_tables()
    url = construct_hansard_url(date_str, parliament, session_number)

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
            print(f"No Hansard transcript available for {date_str} (House may not have been sitting).")
            return None
        response.raise_for_status()

        print(f"Parsing transcript content for {date_str}...")
        parsed_data = parse_hansard_html(response.text, source_url=url)
        speeches = parsed_data.get('speeches', [])

        if not speeches:
            print(f"Warning: No speeches could be extracted for {date_str}.")
            return None

        session_id = insert_session(date_str, parliament, session_number, url)

        print(f"Inserting {len(speeches)} speeches into database...")
        for sp in speeches:
            speaker_id = insert_speaker(
                name=sp['speaker_name'],
                party_name=sp['party_name'],
                title=sp['title'],
                constituency=sp['constituency']
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

        print(f"Running n-gram text analysis for {date_str}...")
        metrics = analyze_speeches(speeches)
        save_word_metrics(
            session_id=session_id,
            word_of_the_day=metrics['word_of_the_day'],
            top_ngrams=metrics['top_ngrams']
        )
        print(f"Word of the Day: '{metrics['word_of_the_day']}'")

        print("Generating neutral party-by-party summaries...")
        party_summaries = generate_all_party_summaries(speeches)
        for party_name, summary_text in party_summaries.items():
            save_party_summary(
                session_id=session_id,
                party_name=party_name,
                summary=summary_text,
                model_used="gemini/openrouter/fallback"
            )

        print(f"Successfully processed and stored Hansard for {date_str}!")
        return session_id

    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def backfill_known_dates():
    known_sittings = [
        "2026-06-02",
        "2026-06-01",
        "2026-05-28",
        "2026-05-27",
        "2026-05-26",
        "2026-05-25",
        "2026-05-14",
        "2026-05-13"
    ]
    for d in known_sittings:
        print(f"\nProcessing date {d}...")
        fetch_and_process_date(d)
        time.sleep(REQUEST_DELAY)

if __name__ == "__main__":
    backfill_known_dates()

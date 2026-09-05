import logging
import time

import requests
from bs4 import BeautifulSoup

from src.database import (
    create_tables,
    get_db_connection,
    insert_session,
    insert_speaker,
    insert_speech,
    save_party_summary,
    save_word_metrics,
)
from src.parser import parse_hansard_html
from src.analysis import analyze_speeches
from src.summarizer import generate_all_party_summaries

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://www.ola.org"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) OpenQueensPark/1.0 (Civic Tech Project; +https://openqueenspark.streamlit.app/)'
}
REQUEST_DELAY = 1.0


def construct_hansard_url(date_str, parliament=44, session=1):
    """Construct the official OLA Hansard URL for a given date."""
    return f"{BASE_URL}/en/legislative-business/house-documents/parliament-{parliament}/session-{session}/{date_str}/hansard"


def fetch_and_process_date(date_str, parliament=44, session_number=1, force_reprocess=False):
    """
    Fetch, parse, analyze, and store Hansard data for a given date.

    Returns:
        int: session_id if successful, None otherwise.
    """
    create_tables()
    url = construct_hansard_url(date_str, parliament, session_number)

    # Check if session already exists
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM sessions WHERE session_date = ?', (date_str,))
        existing_session = cursor.fetchone()

    if existing_session and not force_reprocess:
        logger.info(f"Session for {date_str} already exists in database. Skipping fetch.")
        return existing_session['id']

    logger.info(f"Fetching Hansard from OLA: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        if response.status_code == 404:
            logger.info(f"No Hansard transcript available for {date_str} (House may not have been sitting).")
            return None
        response.raise_for_status()

        logger.info(f"Parsing transcript content for {date_str}...")
        parsed_data = parse_hansard_html(response.text, source_url=url)
        speeches = parsed_data.get('speeches', [])

        if not speeches:
            logger.warning(f"No speeches could be extracted for {date_str}.")
            return None

        session_id = insert_session(date_str, parliament, session_number, url)

        logger.info(f"Inserting {len(speeches)} speeches into database...")
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

        logger.info(f"Running n-gram text analysis for {date_str}...")
        metrics = analyze_speeches(speeches)
        save_word_metrics(
            session_id=session_id,
            word_of_the_day=metrics['word_of_the_day'],
            top_ngrams=metrics['top_ngrams']
        )
        logger.info(f"Word of the Day: '{metrics['word_of_the_day']}'")

        logger.info("Generating neutral party-by-party summaries...")
        party_summaries = generate_all_party_summaries(speeches)
        for party_name, summary_text in party_summaries.items():
            save_party_summary(
                session_id=session_id,
                party_name=party_name,
                summary=summary_text,
                model_used="gemini/openrouter/fallback"
            )

        logger.info(f"Successfully processed and stored Hansard for {date_str}!")
        return session_id

    except requests.RequestException as e:
        logger.error(f"Error fetching {url}: {e}")
        return None


def backfill_known_dates():
    """Backfill a list of known sitting dates from the OLA calendar."""
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
        logger.info(f"Processing date {d}...")
        fetch_and_process_date(d)
        time.sleep(REQUEST_DELAY)


if __name__ == "__main__":
    backfill_known_dates()

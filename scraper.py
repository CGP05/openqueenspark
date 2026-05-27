import requests
from bs4 import BeautifulSoup
from database import insert_party, insert_speaker, insert_session, insert_speech
from datetime import datetime
import re
import time

BASE_URL = "https://www.ola.org"
HEADERS = {
    'User-Agent': 'OpenQueensPark/1.0 (Civic Tech Project; +https://openqueenspark.ca)'
}
DELAY = 2  # seconds between requests

def scrape_hansard(url):
    """Fetch list of Hansard documents from a session page."""
    try:
        time.sleep(DELAY)
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        hansard_links = []
        for link in soup.find_all('a'):
            href = link.get('href')
            if href and 'hansard' in href.lower():
                full_url = BASE_URL + href if href.startswith('/') else href
                hansard_links.append(full_url)

        return hansards
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []

def extract_date_from_url(url):
    """Extract date from Hansard URL like /2026-05-14/hansard"""
    match = re.search(r'/(\d{4})-(\d{2})-(\d{2})/hansard', url)
    if match:
        try:
            year, month, day = match.groups()
            return datetime(int(year), int(month), int(day)).date()
        except ValueError:
            return None
    return None

def parse_hansard_page(url):
    """Parse individual Hansard page and extract content."""
    try:
        time.sleep(DELAY)
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        session_date = extract_date_from_url(url)

        # Find the article and get the hansard content body field
        article = soup.find('article', class_='node--type-hansard-document')
        hansard_text = ""

        if article:
            # Get all body fields within the article
            body_fields = article.find_all('div', class_='field--name-body')
            # The second one (index 1) is the actual Hansard content
            if len(body_fields) > 1:
                hansard_text = body_fields[1].get_text(separator='\n', strip=True)

        return session_date, hansard_text
    except requests.RequestException as e:
        print(f"Error parsing {url}: {e}")
        return None, ""

def store_raw_hansard(session_date, hansard_text, url):
    """Store raw Hansard text for later processing."""
    if not session_date or not hansard_text:
        return

    # Create a system speaker for raw content storage
    system_party_id = insert_party("Ontario Legislature", "OLA")
    system_speaker_id = insert_speaker("Official Record", system_party_id)

    session_id = insert_session(session_date, url=url)
    insert_speech(system_speaker_id, session_id, hansard_text)

    print(f"Stored {len(hansard_text)} chars for {session_date}")

def scrape_and_store_session(session_url):
    """Main function: fetch session, scrape all Hansard pages, store data."""
    print(f"Fetching Hansard links from {session_url}")
    hansard_urls = scrape_hansard_list(session_url)
    print(f"Found {len(hansard_urls)} Hansard pages")

    for hansard_url in hansard_urls:
        print(f"Parsing {hansard_url}")
        session_date, hansard_text = parse_hansard_page(hansard_url)
        if hansard_text:
            store_raw_hansard(session_date, hansard_text, hansard_url)

if __name__ == "__main__":
    session_url = "https://www.ola.org/en/legislative-business/house-documents/parliament-{}/session-{}".format(datetime.now().year, datetime.now().year)
    scrape_and_store_session(session_url)


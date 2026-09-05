"""
MPP Data Fetcher for OpenQueensPark.
Fetches ALL 124 current MPPs using the official OLA AJAX API endpoint.
"""
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from src.database import get_db_connection, insert_speaker

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


OLA_BASE = "https://www.ola.org"
OLA_AJAX_URL = "https://www.ola.org/en/views/ajax"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) OpenQueensPark/1.0 (Civic Tech Project; +https://openqueenspark.ca)',
    'X-Requested-With': 'XMLHttpRequest',
    'Content-Type': 'application/x-www-form-urlencoded',
}

PARTY_NAME_MAP = {
    'Progressive Conservative Party of Ontario': 'Progressive Conservative',
    'New Democratic Party of Ontario': 'New Democratic Party',
    'Ontario Liberal Party': 'Liberal',
    'Green Party of Ontario': 'Green Party',
    'Independent': 'Independent',
}


def fetch_current_mpps_via_ajax() -> list[dict]:
    """
    Fetch all 124 current MPPs using the OLA AJAX endpoint.
    This is the same endpoint the website uses to load the current members grid.
    """
    logger.info("Fetching current MPPs via OLA AJAX endpoint...")
    
    # These values come from the page's drupalSettings
    ajax_data = {
        'view_name': 'current_members',
        'view_display_id': 'current_members_list',
        'view_args': '',
        'view_path': '/node/96456',
        'view_base_path': '',
        'view_dom_id': '9c9a57df25fab6d0201b7deb0837d451edfbaf42ab08180ae1f6199e82e2d922',
        'pager_element': 0,
        '_drupal_ajax': '1'
    }
    
    response = requests.post(OLA_AJAX_URL, headers=HEADERS, data=ajax_data, timeout=30)
    response.raise_for_status()
    
    result = response.json()
    
    # Find the 'insert' command with the HTML
    html = None
    for item in result:
        if item.get('command') == 'insert':
            html = item.get('data', '')
            break
    
    if not html:
        logger.error("Could not find HTML in AJAX response")
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find all MPP links - they have /en/members/all/ slug
    links = soup.find_all('a', href=True)
    mpp_links = [l for l in links if '/en/members/all/' in l.get('href', '')]
    
    logger.info(f"Found {len(mpp_links)} current MPPs via AJAX")
    
    mpps = []
    for link in mpp_links:
        href = link.get('href', '')
        name = link.get_text(strip=True)
        
        if not name or name.lower() in ['mpp', 'name', 'vacant seat']:
            continue
        
        profile_url = href if href.startswith('http') else OLA_BASE + href
        
        mpps.append({
            'name': name,
            'profile_url': profile_url,
            'party': 'Unknown',  # Will fetch from profile
            'constituency': 'Ontario',  # Will fetch from profile
            'photo_url': ''
        })
    
    return mpps


def fetch_mpp_profile(mpp: dict) -> dict:
    """
    Fetch detailed profile info for a single MPP.
    """
    profile_url = mpp.get('profile_url', '')
    if not profile_url:
        return mpp
    
    try:
        response = requests.get(profile_url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            logger.warning(f"Failed to fetch profile for {mpp['name']}: HTTP {response.status_code}")
            return mpp
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract party from the profile page
        # The profile page has party info in the card
        text = soup.get_text()
        
        party = 'Independent'
        for full_name, short_name in PARTY_NAME_MAP.items():
            if full_name in text:
                party = short_name
                break
        
        # Extract constituency/riding
        constituency = 'Ontario'
        # Look for riding patterns
        riding_match = re.search(r'(?:Riding|Constituency|for\s+)([^,\n]+)', text, re.IGNORECASE)
        if riding_match:
            constituency = riding_match.group(1).strip()
        else:
            # Try to find in structured data
            for elem in soup.find_all(['p', 'div', 'span']):
                elem_text = elem.get_text(strip=True)
                if 'Party of Ontario' in elem_text:
                    continue
                if elem_text and len(elem_text) > 2 and 'Ontario' not in elem_text:
                    constituency = elem_text
                    break
        
        # Extract photo URL
        photo_url = ''
        img = soup.find('img', alt=re.compile(re.escape(mpp['name']), re.I))
        if not img:
            img = soup.find('img', class_=re.compile(r'photo|headshot|portrait', re.I))
        if img:
            src = img.get('src', '') or img.get('data-src', '')
            if src and not src.startswith('http'):
                src = OLA_BASE + src
            photo_url = src
        
        # Extract email
        email = None
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        if email_match:
            email = email_match.group(0)
        
        # Extract phone
        phone = None
        phone_match = re.search(r'(?:Telephone|Phone|Tel):\s*([\d\-\(\)\s]{10,})', text)
        if phone_match:
            phone = phone_match.group(1).strip()
        
        # Extract website
        website = None
        website_link = soup.find('a', href=re.compile(r'^https?://(?!www\.ola\.org).+'))
        if website_link:
            website = website_link.get('href')
        
        mpp.update({
            'party': party,
            'constituency': constituency,
            'photo_url': photo_url,
            'email': email,
            'phone': phone,
            'website': website
        })
        
    except Exception as e:
        logger.error(f"Error fetching profile for {mpp['name']}: {e}")

    return mpp


def sync_mpps_to_database(mpps: list[dict]) -> int:
    """
    Sync fetched MPPs to the local database.
    """
    count = 0
    for mpp in mpps:
        try:
            insert_speaker(
                name=mpp['name'],
                party_name=mpp['party'],
                constituency=mpp['constituency'],
                website=mpp.get('profile_url'),
                photo_url=mpp.get('photo_url'),
                email=mpp.get('email'),
                phone=mpp.get('phone')
            )
            count += 1
        except Exception as e:
            logger.error(f"Error syncing MPP {mpp['name']}: {e}")

    logger.info(f"Synced {count} MPPs to database successfully.")
    return count


def auto_update_mpps():
    """Main function to fetch and sync all MPP data."""
    logger.info("Step 1: Fetching current MPPs via AJAX...")
    mpps = fetch_current_mpps_via_ajax()
    logger.info(f"Found {len(mpps)} current MPPs")

    if not mpps:
        logger.error("No MPPs fetched!")
        return

    logger.info("Step 2: Fetching detailed profile info...")
    for i, mpp in enumerate(mpps):
        logger.info(f"  [{i+1}/{len(mpps)}] Fetching profile for {mpp['name']}...")
        mpps[i] = fetch_mpp_profile(mpp)
        time.sleep(0.2)  # Be respectful

    logger.info("Step 3: Syncing to database...")
    sync_mpps_to_database(mpps)

    # Print summary
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.name as party, COUNT(s.id) as count
            FROM speakers s
            LEFT JOIN parties p ON s.party_id = p.id
            GROUP BY p.name
            ORDER BY count DESC
        ''')
        for row in cursor.fetchall():
            logger.info(f"  {row['party']}: {row['count']}")


if __name__ == '__main__':
    auto_update_mpps()
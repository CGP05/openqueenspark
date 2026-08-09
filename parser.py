import re
from bs4 import BeautifulSoup
from datetime import datetime

# Common Ontario MPP party lookup heuristics
KNOWN_MPP_PARTIES = {
    "doug ford": ("Progressive Conservative", "Etobicoke Centre"),
    "steve clark": ("Progressive Conservative", "Leeds—Grenville—Thousand Islands and Rideau Lakes"),
    "sylvia jones": ("Progressive Conservative", "Dufferin—Caledon"),
    "peter bethlenfalvy": ("Progressive Conservative", "Pickering—Uxbridge"),
    "paul calandra": ("Progressive Conservative", "Markham—Stouffville"),
    "marit stiles": ("New Democratic Party", "Davenport"),
    "joel harden": ("New Democratic Party", "Ottawa Centre"),
    "bhutila karpoche": ("New Democratic Party", "Parkdale—High Park"),
    "john fraser": ("Liberal", "Ottawa South"),
    "bonnie crombie": ("Liberal", "Mississauga East—Cooksville"),
    "mike schreiner": ("Green Party", "Guelph"),
    "donna skelly": ("Non-Partisan / Presiding Officer", "Flamborough—Glanbrook"),
    "ted arnott": ("Non-Partisan / Presiding Officer", "Wellington—Halton Hills")
}

def clean_speaker_name(raw_name):
    if not raw_name:
        return "Unknown Speaker", None

    text = raw_name.strip()
    if text.endswith(':'):
        text = text[:-1].strip()

    title = None
    if text.startswith("The Speaker"):
        title = "Speaker of the Legislative Assembly"
        match = re.search(r'\((.*?)\)', text)
        if match:
            text = match.group(1).strip()
        else:
            text = "The Speaker"

    cleaned = re.sub(r'^(Hon\.|Mr\.|Mrs\.|Ms\.|Mme\.|Miss)\s+', '', text, flags=re.IGNORECASE).strip()
    return cleaned, title

def infer_party_and_constituency(speaker_name, title=None):
    if title and "Speaker" in title:
        return "Non-Partisan / Presiding Officer", "Ontario Legislature"

    name_lower = speaker_name.lower().strip()
    for known_name, (party, constituency) in KNOWN_MPP_PARTIES.items():
        if known_name in name_lower or name_lower in known_name:
            return party, constituency

    return "Independent", "Ontario"

def parse_hansard_html(html_content, source_url=""):
    """
    Parses full Hansard HTML content from OLA into structured speech records.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Date extraction
    session_date = None
    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', source_url)
    if not date_match:
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc:
            d_match = re.search(r'(\d{4}-\d{2}-\d{2})', meta_desc.get('content', ''))
            if d_match:
                date_match = d_match

    session_date = date_match.group(0) if date_match else datetime.now().strftime('%Y-%m-%d')

    parliament = 44
    session_number = 1
    p_match = re.search(r'parliament-(\d+)', source_url)
    if p_match:
        parliament = int(p_match.group(1))
    s_match = re.search(r'session-(\d+)', source_url)
    if s_match:
        session_number = int(s_match.group(1))

    body_fields = soup.find_all('div', class_='field--name-body')
    main_body = body_fields[1] if len(body_fields) > 1 else (soup.find('article') or soup)

    current_h2 = "General Proceedings"
    current_h3 = ""
    speeches = []
    current_speech = None
    sequence = 0

    for elem in main_body.find_all(['h2', 'h3', 'p']):
        if elem.name == 'h2':
            txt = elem.get_text(strip=True)
            if txt and len(txt) < 150:
                current_h2 = txt
                current_h3 = ""
            continue

        if elem.name == 'h3':
            txt = elem.get_text(strip=True)
            if txt and len(txt) < 200:
                current_h3 = txt
            continue

        if elem.name == 'p':
            classes = elem.get('class', [])
            strong = elem.find('strong')

            # Check if this paragraph starts a new speech
            if 'speakerStart' in classes or strong:
                if strong and strong.get_text(strip=True):
                    raw_speaker = strong.get_text(strip=True)
                    full_text = elem.get_text(strip=True)
                    speech_text = full_text.replace(raw_speaker, '', 1).strip()

                    timestamp_el = elem.find(class_='timeStamp')
                    timestamp_str = timestamp_el.get_text(strip=True) if timestamp_el else None
                    if timestamp_str:
                        speech_text = speech_text.replace(timestamp_str, '', 1).strip()

                    if current_speech and current_speech['text'].strip():
                        speeches.append(current_speech)

                    speaker_name, title = clean_speaker_name(raw_speaker)
                    party_name, constituency = infer_party_and_constituency(speaker_name, title)

                    sequence += 1
                    current_speech = {
                        'raw_speaker': raw_speaker,
                        'speaker_name': speaker_name,
                        'title': title,
                        'party_name': party_name,
                        'constituency': constituency,
                        'h2_heading': current_h2,
                        'h3_heading': current_h3,
                        'text': speech_text,
                        'timestamp': timestamp_str,
                        'sequence': sequence
                    }
                elif current_speech:
                    p_text = elem.get_text(strip=True)
                    if p_text:
                        current_speech['text'] += "\n\n" + p_text
            elif current_speech:
                p_text = elem.get_text(strip=True)
                if p_text:
                    current_speech['text'] += "\n\n" + p_text

    if current_speech and current_speech['text'].strip():
        speeches.append(current_speech)

    return {
        'date': session_date,
        'parliament': parliament,
        'session_number': session_number,
        'url': source_url,
        'speeches': speeches
    }

if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    sample_file = 'hansard_sample.html'
    try:
        with open(sample_file, 'r', encoding='utf-8') as f:
            data = parse_hansard_html(f.read(), source_url="https://www.ola.org/en/legislative-business/house-documents/parliament-44/session-1/2026-05-14/hansard")
            print(f"Parsed {len(data['speeches'])} speeches for date {data['date']}")
            if data['speeches']:
                print("First speech:", data['speeches'][0])
    except FileNotFoundError:
        print("Sample file not found for quick test.")

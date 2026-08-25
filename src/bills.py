"""
Bills tracking module for OpenQueensPark.
Tracks legislative bills through their lifecycle in the Ontario Legislature.
"""
import re
from datetime import datetime
from src.database import (
    get_connection, insert_bill, add_bill_stage, get_bills_for_session,
    get_bill_by_id, index_bill_for_search, rebuild_search_indexes
)

# Ontario Legislature bill status mapping
BILL_STATUS_MAP = {
    'First Reading': 'introduced',
    'Second Reading': 'second_reading',
    'Committee': 'committee',
    'Report Stage': 'report_stage',
    'Third Reading': 'third_reading',
    'Royal Assent': 'royal_assent',
    'Defeated': 'defeated',
    'Withdrawn': 'withdrawn',
}

def extract_bills_from_speeches(speeches, session_id):
    """
    Extract bill references from speeches and create bill records.
    Looks for bill numbers like 'Bill 123', 'Bill C-123', 'Bill S-123'
    """
    bills_found = {}
    
    # Pattern to match Ontario bill references
    # Bill 123, Bill 123, 2023, Bill Pr123 (private), etc.
    bill_pattern = re.compile(
        r'\bBill\s+(?:Pr)?(\d+)(?:\s*,\s*(\d{4}))?\b',
        re.IGNORECASE
    )
    
    # Also match short titles in quotes
    title_pattern = re.compile(
        r'(?:Bill\s+\d+(?:,\s*\d{4})?\s*[,\-]?\s*)?["\']([^"\']+)["\']',
        re.IGNORECASE
    )
    
    for sp in speeches:
        text = sp.get('text', '')
        h3 = sp.get('h3_heading', '')
        
        # Find bill numbers
        matches = bill_pattern.findall(text)
        for match in matches:
            bill_num = f"Bill {match[0]}"
            if match[1]:
                bill_num += f", {match[1]}"
            
            if bill_num not in bills_found:
                bills_found[bill_num] = {
                    'bill_number': bill_num,
                    'mentions': [],
                    'speakers': set(),
                    'parties': set(),
                    'sections': set()
                }
            
            bills_found[bill_num]['mentions'].append({
                'speaker': sp.get('speaker_name'),
                'party': sp.get('party_name'),
                'section': sp.get('h2_heading'),
                'topic': sp.get('h3_heading'),
                'text': text[:500]
            })
            bills_found[bill_num]['speakers'].add(sp.get('speaker_name'))
            bills_found[bill_num]['parties'].add(sp.get('party_name'))
            bills_found[bill_num]['sections'].add(sp.get('h2_heading'))
        
        # Also check h3_heading for bill titles
        if 'bill' in h3.lower():
            # Try to extract bill number from heading
            bill_match = bill_pattern.search(h3)
            if bill_match:
                bill_num = f"Bill {bill_match.group(1)}"
                if bill_match.group(2):
                    bill_num += f", {bill_match.group(2)}"
                
                if bill_num not in bills_found:
                    bills_found[bill_num] = {
                        'bill_number': bill_num,
                        'mentions': [],
                        'speakers': set(),
                        'parties': set(),
                        'sections': set()
                    }
                
                bills_found[bill_num]['mentions'].append({
                    'speaker': sp.get('speaker_name'),
                    'party': sp.get('party_name'),
                    'section': sp.get('h2_heading'),
                    'topic': h3,
                    'text': text[:500]
                })
                bills_found[bill_num]['speakers'].add(sp.get('speaker_name'))
                bills_found[bill_num]['parties'].add(sp.get('party_name'))
                bills_found[bill_num]['sections'].add(sp.get('h2_heading'))
    
    return bills_found


def create_bills_from_hansard(session_id, speeches):
    """
    Create bill records from extracted Hansard mentions.
    """
    bills_found = extract_bills_from_speeches(speeches, session_id)
    
    created_bills = []
    for bill_num, info in bills_found.items():
        # Determine sponsor from first mention (usually government)
        sponsor = list(info['speakers'])[0] if info['speakers'] else None
        sponsor_party = list(info['parties'])[0] if info['parties'] else None
        
        # Determine likely status from section context
        status = 'introduced'
        stage = 'First Reading'
        for mention in info['mentions']:
            section = mention['section'].lower() if mention['section'] else ''
            topic = mention['topic'].lower() if mention['topic'] else ''
            
            if 'second reading' in section or 'second reading' in topic:
                status = 'second_reading'
                stage = 'Second Reading'
            elif 'committee' in section or 'committee' in topic:
                status = 'committee'
                stage = 'Committee'
            elif 'third reading' in section or 'third reading' in topic:
                status = 'third_reading'
                stage = 'Third Reading'
            elif 'royal assent' in section or 'royal assent' in topic:
                status = 'royal_assent'
                stage = 'Royal Assent'
        
        # Generate description from mentions
        description = f"Mentioned by {len(info['speakers'])} speaker(s) across {len(info['sections'])} section(s). "
        if info['parties']:
            description += f"Parties involved: {', '.join(info['parties'])}. "
        if info['sections']:
            description += f"Sections: {', '.join(info['sections'])}."
        
        bill_id = insert_bill(
            bill_number=bill_num,
            bill_name=bill_num,
            sponsor_name=sponsor,
            sponsor_party=sponsor_party,
            status=status,
            stage=stage,
            session_id=session_id,
            description=description
        )
        
        if bill_id:
            add_bill_stage(bill_id, stage, details=f"Mentioned in {len(info['mentions'])} speech(es)")
            index_bill_for_search(bill_id, bill_num, bill_num, bill_num, sponsor, description)
            created_bills.append({
                'bill_id': bill_id,
                'bill_number': bill_num,
                'sponsor': sponsor,
                'stage': stage,
                'mentions': len(info['mentions'])
            })
    
    return created_bills


# Pre-populate known Ontario committees
ONTARIO_COMMITTEES = [
    {
        'name': 'Standing Committee on Estimates',
        'short_name': 'Estimates',
        'type': 'standing',
        'meeting_schedule': 'As required during budget cycle',
        'website': 'https://www.ola.org/en/legislative-business/committees/estimates'
    },
    {
        'name': 'Standing Committee on Finance and Economic Affairs',
        'short_name': 'Finance',
        'type': 'standing',
        'meeting_schedule': 'Weekly during session',
        'website': 'https://www.ola.org/en/legislative-business/committees/finance'
    },
    {
        'name': 'Standing Committee on General Government',
        'short_name': 'General Government',
        'type': 'standing',
        'meeting_schedule': 'Weekly during session',
        'website': 'https://www.ola.org/en/legislative-business/committees/general-government'
    },
    {
        'name': 'Standing Committee on Heritage, Infrastructure and Cultural Policy',
        'short_name': 'Heritage & Infrastructure',
        'type': 'standing',
        'meeting_schedule': 'Weekly during session',
        'website': 'https://www.ola.org/en/legislative-business/committees/heritage'
    },
    {
        'name': 'Standing Committee on Justice Policy',
        'short_name': 'Justice',
        'type': 'standing',
        'meeting_schedule': 'Weekly during session',
        'website': 'https://www.ola.org/en/legislative-business/committees/justice'
    },
    {
        'name': 'Standing Committee on the Legislative Assembly',
        'short_name': 'Legislative Assembly',
        'type': 'standing',
        'meeting_schedule': 'As required',
        'website': 'https://www.ola.org/en/legislative-business/committees/legislative-assembly'
    },
    {
        'name': 'Standing Committee on Public Accounts',
        'short_name': 'Public Accounts',
        'type': 'standing',
        'meeting_schedule': 'Weekly during session',
        'website': 'https://www.ola.org/en/legislative-business/committees/public-accounts'
    },
    {
        'name': 'Standing Committee on Regulations and Private Bills',
        'short_name': 'Regulations & Private Bills',
        'type': 'standing',
        'meeting_schedule': 'As required',
        'website': 'https://www.ola.org/en/legislative-business/committees/regulations'
    },
    {
        'name': 'Standing Committee on Social Policy',
        'short_name': 'Social Policy',
        'type': 'standing',
        'meeting_schedule': 'Weekly during session',
        'website': 'https://www.ola.org/en/legislative-business/committees/social-policy'
    },
]


def populate_committees():
    """Populate default Ontario committees."""
    from src.database import insert_committee
    for comm in ONTARIO_COMMITTEES:
        insert_committee(**comm)
    print(f"Populated {len(ONTARIO_COMMITTEES)} Ontario committees.")


if __name__ == '__main__':
    # Test extraction
    from src.database import create_tables, get_speeches_for_session
    create_tables()
    populate_committees()
    print("Bills module initialized.")
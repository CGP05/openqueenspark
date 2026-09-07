import json
import logging
import os
import sqlite3
from contextlib import contextmanager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.getenv("DB_PATH", os.path.join(PROJECT_ROOT, "database.db"))


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_connection():
    """Legacy function for backward compatibility."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def with_connection(func):
    """Decorator that wraps a function with automatic connection management."""

    def wrapper(*args, **kwargs):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            result = func(conn, *args, **kwargs)
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    return wrapper


@with_connection
def create_tables(conn):
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            abbreviation TEXT,
            color TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS speakers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            party_id INTEGER,
            constituency TEXT,
            title TEXT,
            email TEXT,
            phone TEXT,
            website TEXT,
            photo_url TEXT,
            biography TEXT,
            first_elected DATE,
            FOREIGN KEY (party_id) REFERENCES parties(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date DATE UNIQUE NOT NULL,
            parliament INTEGER,
            session_number INTEGER,
            url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS speeches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            speaker_id INTEGER,
            session_id INTEGER,
            h2_heading TEXT,
            h3_heading TEXT,
            text TEXT NOT NULL,
            timestamp TEXT,
            sequence INTEGER,
            FOREIGN KEY (speaker_id) REFERENCES speakers(id),
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS party_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            party_name TEXT NOT NULL,
            summary TEXT NOT NULL,
            model_used TEXT DEFAULT 'fallback',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            UNIQUE(session_id, party_name)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS word_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER UNIQUE NOT NULL,
            word_of_the_day TEXT,
            top_ngrams_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    # NEW: Bills tracking table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_number TEXT NOT NULL,
            bill_name TEXT,
            short_title TEXT,
            sponsor_name TEXT,
            sponsor_party TEXT,
            status TEXT,
            stage TEXT,
            introduced_date DATE,
            last_activity_date DATE,
            session_id INTEGER,
            parliament INTEGER,
            session_number INTEGER,
            legisinfo_id INTEGER UNIQUE,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(bill_number, session_id)
        )
    """)

    # NEW: Bill stages/history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bill_stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER NOT NULL,
            stage TEXT NOT NULL,
            date DATE,
            details TEXT,
            vote_yes INTEGER,
            vote_no INTEGER,
            vote_abstain INTEGER,
            FOREIGN KEY (bill_id) REFERENCES bills(id)
        )
    """)

    # NEW: Committees table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS committees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            short_name TEXT,
            type TEXT,  -- standing, special, legislative, joint
            chair_name TEXT,
            vice_chair_name TEXT,
            clerk_name TEXT,
            meeting_schedule TEXT,
            website TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # NEW: Committee meetings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS committee_meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            committee_id INTEGER NOT NULL,
            meeting_date DATE,
            meeting_number INTEGER,
            title TEXT,
            evidence_text TEXT,
            witnesses_json TEXT,
            documents_json TEXT,
            source_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (committee_id) REFERENCES committees(id)
        )
    """)

    # NEW: FTS5 search index for speeches
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS speeches_fts USING fts5(
            speech_id UNINDEXED,
            speaker_name,
            party_name,
            text,
            h2_heading,
            h3_heading,
            session_date UNINDEXED,
            tokenize='porter unicode61'
        )
    """)

    # NEW: FTS5 search index for bills
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS bills_fts USING fts5(
            bill_id UNINDEXED,
            bill_number,
            bill_name,
            short_title,
            sponsor_name,
            description,
            tokenize='porter unicode61'
        )
    """)

    conn.commit()

    # Pre-populate default Ontario Political Parties
    default_parties = [
        ("Progressive Conservative", "PC", "#003366"),
        ("New Democratic Party", "NDP", "#FF6600"),
        ("Liberal", "LIB", "#FF0000"),
        ("Green Party", "GPO", "#009933"),
        ("Independent", "IND", "#888888"),
        ("Non-Partisan / Presiding Officer", "SPEAKER", "#4A5568"),
    ]

    for name, abbr, color in default_parties:
        cursor.execute(
            """
            INSERT OR IGNORE INTO parties (name, abbreviation, color)
            VALUES (?, ?, ?)
        """,
            (name, abbr, color),
        )


def insert_party(name, abbreviation=None, color=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM parties WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        conn.close()
        return row["id"]
    cursor.execute(
        """
        INSERT INTO parties (name, abbreviation, color)
        VALUES (?, ?, ?)
    """,
        (name, abbreviation, color or "#888888"),
    )
    conn.commit()
    party_id = cursor.lastrowid
    conn.close()
    return party_id


def insert_speaker(
    name,
    party_name=None,
    constituency=None,
    title=None,
    email=None,
    phone=None,
    website=None,
    photo_url=None,
    biography=None,
    first_elected=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    party_id = None
    if party_name:
        party_id = insert_party(party_name)

    cursor.execute(
        "SELECT id, party_id, constituency, title, email, phone, website, photo_url, biography, first_elected FROM speakers WHERE name = ?",
        (name,),
    )
    row = cursor.fetchone()
    if row:
        speaker_id = row["id"]
        # Update details if provided
        if party_id and not row["party_id"]:
            cursor.execute(
                "UPDATE speakers SET party_id = ? WHERE id = ?", (party_id, speaker_id)
            )
        if constituency and not row["constituency"]:
            cursor.execute(
                "UPDATE speakers SET constituency = ? WHERE id = ?",
                (constituency, speaker_id),
            )
        if title and not row["title"]:
            cursor.execute(
                "UPDATE speakers SET title = ? WHERE id = ?", (title, speaker_id)
            )
        if email and not row["email"]:
            cursor.execute(
                "UPDATE speakers SET email = ? WHERE id = ?", (email, speaker_id)
            )
        if phone and not row["phone"]:
            cursor.execute(
                "UPDATE speakers SET phone = ? WHERE id = ?", (phone, speaker_id)
            )
        if website and not row["website"]:
            cursor.execute(
                "UPDATE speakers SET website = ? WHERE id = ?", (website, speaker_id)
            )
        if photo_url and not row["photo_url"]:
            cursor.execute(
                "UPDATE speakers SET photo_url = ? WHERE id = ?",
                (photo_url, speaker_id),
            )
        if biography and not row["biography"]:
            cursor.execute(
                "UPDATE speakers SET biography = ? WHERE id = ?",
                (biography, speaker_id),
            )
        if first_elected and not row["first_elected"]:
            cursor.execute(
                "UPDATE speakers SET first_elected = ? WHERE id = ?",
                (first_elected, speaker_id),
            )
        conn.commit()
        conn.close()
        return speaker_id

    cursor.execute(
        """
        INSERT INTO speakers (name, party_id, constituency, title, email, phone, website, photo_url, biography, first_elected)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            name,
            party_id,
            constituency,
            title,
            email,
            phone,
            website,
            photo_url,
            biography,
            first_elected,
        ),
    )
    conn.commit()
    speaker_id = cursor.lastrowid
    conn.close()
    return speaker_id


@with_connection
def insert_session(conn, session_date, parliament=44, session_number=1, url=None):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM sessions WHERE session_date = ?", (str(session_date),)
    )
    row = cursor.fetchone()
    if row:
        return row["id"]

    cursor.execute(
        """
        INSERT INTO sessions (session_date, parliament, session_number, url)
        VALUES (?, ?, ?, ?)
    """,
        (str(session_date), parliament, session_number, url),
    )
    return cursor.lastrowid


@with_connection
def insert_speech(
    conn,
    speaker_id,
    session_id,
    text,
    h2_heading=None,
    h3_heading=None,
    timestamp=None,
    sequence=0,
):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO speeches (speaker_id, session_id, text, h2_heading, h3_heading, timestamp, sequence)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (speaker_id, session_id, text, h2_heading, h3_heading, timestamp, sequence),
    )
    return cursor.lastrowid


@with_connection
def save_party_summary(conn, session_id, party_name, summary, model_used="fallback"):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO party_summaries (session_id, party_name, summary, model_used)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(session_id, party_name) DO UPDATE SET
            summary=excluded.summary,
            model_used=excluded.model_used,
            created_at=CURRENT_TIMESTAMP
    """,
        (session_id, party_name, summary, model_used),
    )


@with_connection
def save_word_metrics(conn, session_id, word_of_the_day, top_ngrams):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO word_metrics (session_id, word_of_the_day, top_ngrams_json)
        VALUES (?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            word_of_the_day=excluded.word_of_the_day,
            top_ngrams_json=excluded.top_ngrams_json,
            created_at=CURRENT_TIMESTAMP
    """,
        (session_id, word_of_the_day, json.dumps(top_ngrams)),
    )


@with_connection
def get_available_session_dates(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT session_date FROM sessions ORDER BY session_date DESC")
    rows = cursor.fetchall()
    return [r["session_date"] for r in rows]


@with_connection
def get_speeches_for_session(conn, session_date):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT sp.id, s.name as speaker_name, p.name as party_name, p.abbreviation as party_abbr,
               p.color as party_color, s.constituency, sp.h2_heading, sp.h3_heading,
               sp.text, sp.timestamp, sp.sequence
        FROM speeches sp
        JOIN speakers s ON sp.speaker_id = s.id
        LEFT JOIN parties p ON s.party_id = p.id
        JOIN sessions ss ON sp.session_id = ss.id
        WHERE ss.session_date = ?
        ORDER BY sp.sequence ASC
    """,
        (str(session_date),),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    return rows


@with_connection
def get_party_summaries(conn, session_date):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT ps.party_name, ps.summary, ps.model_used, p.color, p.abbreviation
        FROM party_summaries ps
        JOIN sessions ss ON ps.session_id = ss.id
        LEFT JOIN parties p ON ps.party_name = p.name
        WHERE ss.session_date = ?
    """,
        (str(session_date),),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    return rows


@with_connection
def get_word_metrics(conn, session_date):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT wm.word_of_the_day, wm.top_ngrams_json
        FROM word_metrics wm
        JOIN sessions ss ON wm.session_id = ss.id
        WHERE ss.session_date = ?
    """,
        (str(session_date),),
    )
    row = cursor.fetchone()
    if row:
        return {
            "word_of_the_day": row["word_of_the_day"],
            "top_ngrams": json.loads(row["top_ngrams_json"])
            if row["top_ngrams_json"]
            else [],
        }
    return None


# NEW: Bills functions
def insert_bill(
    bill_number,
    bill_name=None,
    short_title=None,
    sponsor_name=None,
    sponsor_party=None,
    status=None,
    stage=None,
    introduced_date=None,
    last_activity_date=None,
    session_id=None,
    parliament=44,
    session_number=1,
    legisinfo_id=None,
    description=None,
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM bills WHERE bill_number = ? AND session_id = ?",
        (bill_number, session_id),
    )
    row = cursor.fetchone()
    if row:
        # Update existing
        cursor.execute(
            """
            UPDATE bills SET bill_name=?, short_title=?, sponsor_name=?, sponsor_party=?,
                status=?, stage=?, last_activity_date=?, description=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """,
            (
                bill_name,
                short_title,
                sponsor_name,
                sponsor_party,
                status,
                stage,
                last_activity_date,
                description,
                row["id"],
            ),
        )
        conn.commit()
        bill_id = row["id"]
    else:
        cursor.execute(
            """
            INSERT INTO bills (bill_number, bill_name, short_title, sponsor_name, sponsor_party,
                status, stage, introduced_date, last_activity_date, session_id, parliament,
                session_number, legisinfo_id, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                bill_number,
                bill_name,
                short_title,
                sponsor_name,
                sponsor_party,
                status,
                stage,
                introduced_date,
                last_activity_date,
                session_id,
                parliament,
                session_number,
                legisinfo_id,
                description,
            ),
        )
        conn.commit()
        bill_id = cursor.lastrowid
    conn.close()
    return bill_id


def add_bill_stage(
    bill_id,
    stage,
    date=None,
    details=None,
    vote_yes=None,
    vote_no=None,
    vote_abstain=None,
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO bill_stages (bill_id, stage, date, details, vote_yes, vote_no, vote_abstain)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (bill_id, stage, date, details, vote_yes, vote_no, vote_abstain),
    )
    conn.commit()
    stage_id = cursor.lastrowid
    conn.close()
    return stage_id


def get_bills_for_session(session_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT b.*, GROUP_CONCAT(bs.stage || ':' || bs.date) as stages
        FROM bills b
        LEFT JOIN bill_stages bs ON b.id = bs.bill_id
        WHERE b.session_id = ?
        GROUP BY b.id
        ORDER BY b.last_activity_date DESC
    """,
        (session_id,),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_bill_by_id(bill_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bills WHERE id = ?", (bill_id,))
    bill = cursor.fetchone()
    if bill:
        cursor.execute(
            "SELECT * FROM bill_stages WHERE bill_id = ? ORDER BY date", (bill_id,)
        )
        stages = [dict(r) for r in cursor.fetchall()]
        result = dict(bill)
        result["stages"] = stages
    else:
        result = None
    conn.close()
    return result


def search_bills(query, limit=20):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT b.*, bm.rank
        FROM bills_fts bm
        JOIN bills b ON bm.bill_id = b.id
        WHERE bills_fts MATCH ?
        ORDER BY bm.rank
        LIMIT ?
    """,
        (query, limit),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# NEW: Committees functions
def insert_committee(
    name,
    short_name=None,
    type=None,
    chair_name=None,
    vice_chair_name=None,
    clerk_name=None,
    meeting_schedule=None,
    website=None,
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM committees WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        cursor.execute(
            """
            UPDATE committees SET short_name=?, type=?, chair_name=?, vice_chair_name=?,
                clerk_name=?, meeting_schedule=?, website=?
            WHERE id=?
        """,
            (
                short_name,
                type,
                chair_name,
                vice_chair_name,
                clerk_name,
                meeting_schedule,
                website,
                row["id"],
            ),
        )
        conn.commit()
        committee_id = row["id"]
    else:
        cursor.execute(
            """
            INSERT INTO committees (name, short_name, type, chair_name, vice_chair_name,
                clerk_name, meeting_schedule, website)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                name,
                short_name,
                type,
                chair_name,
                vice_chair_name,
                clerk_name,
                meeting_schedule,
                website,
            ),
        )
        conn.commit()
        committee_id = cursor.lastrowid
    conn.close()
    return committee_id


def insert_committee_meeting(
    committee_id,
    meeting_date,
    meeting_number=None,
    title=None,
    evidence_text=None,
    witnesses=None,
    documents=None,
    source_url=None,
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO committee_meetings (committee_id, meeting_date, meeting_number, title,
            evidence_text, witnesses_json, documents_json, source_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            committee_id,
            meeting_date,
            meeting_number,
            title,
            evidence_text,
            json.dumps(witnesses or []),
            json.dumps(documents or []),
            source_url,
        ),
    )
    conn.commit()
    meeting_id = cursor.lastrowid
    conn.close()
    return meeting_id


def get_committees(active_only=True):
    conn = get_connection()
    cursor = conn.cursor()
    if active_only:
        cursor.execute("SELECT * FROM committees WHERE is_active = 1 ORDER BY name")
    else:
        cursor.execute("SELECT * FROM committees ORDER BY name")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_committee_meetings(committee_id, limit=50):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM committee_meetings 
        WHERE committee_id = ? 
        ORDER BY meeting_date DESC 
        LIMIT ?
    """,
        (committee_id, limit),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# NEW: FTS5 Search functions
def index_speech_for_search(
    speech_id, speaker_name, party_name, text, h2_heading, h3_heading, session_date
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO speeches_fts (speech_id, speaker_name, party_name, text, h2_heading, h3_heading, session_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            speech_id,
            speaker_name,
            party_name or "",
            text,
            h2_heading or "",
            h3_heading or "",
            session_date,
        ),
    )
    conn.commit()
    conn.close()


def index_bill_for_search(
    bill_id, bill_number, bill_name, short_title, sponsor_name, description
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO bills_fts (bill_id, bill_number, bill_name, short_title, sponsor_name, description)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            bill_id,
            bill_number,
            bill_name or "",
            short_title or "",
            sponsor_name or "",
            description or "",
        ),
    )
    conn.commit()
    conn.close()


def search_speeches(query, limit=20, session_date=None):
    conn = get_connection()
    cursor = conn.cursor()
    if session_date:
        cursor.execute(
            """
            SELECT s.*, sp.text as snippet
            FROM speeches_fts sp
            JOIN speeches s ON sp.speech_id = s.id
            JOIN sessions ss ON s.session_id = ss.id
            WHERE speeches_fts MATCH ? AND ss.session_date = ?
            ORDER BY sp.rank
            LIMIT ?
        """,
            (query, str(session_date), limit),
        )
    else:
        cursor.execute(
            """
            SELECT s.*, sp.text as snippet
            FROM speeches_fts sp
            JOIN speeches s ON sp.speech_id = s.id
            JOIN sessions ss ON s.session_id = ss.id
            WHERE speeches_fts MATCH ?
            ORDER BY sp.rank
            LIMIT ?
        """,
            (query, limit),
        )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def rebuild_search_indexes():
    """Rebuild FTS5 indexes from existing data."""
    conn = get_connection()
    cursor = conn.cursor()

    # Clear and rebuild speeches index
    cursor.execute("DELETE FROM speeches_fts")
    cursor.execute("""
        SELECT sp.id, s.name as speaker_name, p.name as party_name, sp.text, sp.h2_heading, sp.h3_heading, ss.session_date
        FROM speeches sp
        JOIN speakers s ON sp.speaker_id = s.id
        LEFT JOIN parties p ON s.party_id = p.id
        JOIN sessions ss ON sp.session_id = ss.id
    """)
    for row in cursor.fetchall():
        cursor.execute(
            """
            INSERT INTO speeches_fts (speech_id, speaker_name, party_name, text, h2_heading, h3_heading, session_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                row["id"],
                row["speaker_name"],
                row["party_name"] or "",
                row["text"],
                row["h2_heading"] or "",
                row["h3_heading"] or "",
                row["session_date"],
            ),
        )

    # Clear and rebuild bills index
    cursor.execute("DELETE FROM bills_fts")
    cursor.execute(
        "SELECT id, bill_number, bill_name, short_title, sponsor_name, description FROM bills"
    )
    for row in cursor.fetchall():
        cursor.execute(
            """
            INSERT INTO bills_fts (bill_id, bill_number, bill_name, short_title, sponsor_name, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                row["id"],
                row["bill_number"],
                row["bill_name"] or "",
                row["short_title"] or "",
                row["sponsor_name"] or "",
                row["description"] or "",
            ),
        )

    conn.commit()
    conn.close()
    print("Search indexes rebuilt successfully.")


if __name__ == "__main__":
    create_tables()
    print("Database initialized successfully.")

import sqlite3
import os
import json
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.getenv('DB_PATH', os.path.join(PROJECT_ROOT, 'database.db'))

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            abbreviation TEXT,
            color TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS speakers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            party_id INTEGER,
            constituency TEXT,
            title TEXT,
            FOREIGN KEY (party_id) REFERENCES parties(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date DATE UNIQUE NOT NULL,
            parliament INTEGER,
            session_number INTEGER,
            url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
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
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS party_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            party_name TEXT NOT NULL,
            summary TEXT NOT NULL,
            model_used TEXT DEFAULT 'ollama',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            UNIQUE(session_id, party_name)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS word_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER UNIQUE NOT NULL,
            word_of_the_day TEXT,
            top_ngrams_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    ''')

    conn.commit()

    # Pre-populate default Ontario Political Parties
    default_parties = [
        ("Progressive Conservative", "PC", "#003366"),
        ("New Democratic Party", "NDP", "#FF6600"),
        ("Liberal", "LIB", "#FF0000"),
        ("Green Party", "GPO", "#009933"),
        ("Independent", "IND", "#888888"),
        ("Non-Partisan / Presiding Officer", "SPEAKER", "#4A5568")
    ]

    for name, abbr, color in default_parties:
        cursor.execute('''
            INSERT OR IGNORE INTO parties (name, abbreviation, color)
            VALUES (?, ?, ?)
        ''', (name, abbr, color))

    conn.commit()
    conn.close()

def insert_party(name, abbreviation=None, color=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM parties WHERE name = ?', (name,))
    row = cursor.fetchone()
    if row:
        conn.close()
        return row['id']
    cursor.execute('''
        INSERT INTO parties (name, abbreviation, color)
        VALUES (?, ?, ?)
    ''', (name, abbreviation, color or '#888888'))
    conn.commit()
    party_id = cursor.lastrowid
    conn.close()
    return party_id

def insert_speaker(name, party_name=None, constituency=None, title=None):
    conn = get_connection()
    cursor = conn.cursor()

    party_id = None
    if party_name:
        party_id = insert_party(party_name)

    cursor.execute('SELECT id, party_id, constituency, title FROM speakers WHERE name = ?', (name,))
    row = cursor.fetchone()
    if row:
        speaker_id = row['id']
        # Update details if provided
        if party_id and not row['party_id']:
            cursor.execute('UPDATE speakers SET party_id = ? WHERE id = ?', (party_id, speaker_id))
        if constituency and not row['constituency']:
            cursor.execute('UPDATE speakers SET constituency = ? WHERE id = ?', (constituency, speaker_id))
        if title and not row['title']:
            cursor.execute('UPDATE speakers SET title = ? WHERE id = ?', (title, speaker_id))
        conn.commit()
        conn.close()
        return speaker_id

    cursor.execute('''
        INSERT INTO speakers (name, party_id, constituency, title)
        VALUES (?, ?, ?, ?)
    ''', (name, party_id, constituency, title))
    conn.commit()
    speaker_id = cursor.lastrowid
    conn.close()
    return speaker_id

def insert_session(session_date, parliament=44, session_number=1, url=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM sessions WHERE session_date = ?', (str(session_date),))
    row = cursor.fetchone()
    if row:
        conn.close()
        return row['id']

    cursor.execute('''
        INSERT INTO sessions (session_date, parliament, session_number, url)
        VALUES (?, ?, ?, ?)
    ''', (str(session_date), parliament, session_number, url))
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id

def insert_speech(speaker_id, session_id, text, h2_heading=None, h3_heading=None, timestamp=None, sequence=0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO speeches (speaker_id, session_id, text, h2_heading, h3_heading, timestamp, sequence)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (speaker_id, session_id, text, h2_heading, h3_heading, timestamp, sequence))
    conn.commit()
    speech_id = cursor.lastrowid
    conn.close()
    return speech_id

def save_party_summary(session_id, party_name, summary, model_used='ollama'):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO party_summaries (session_id, party_name, summary, model_used)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(session_id, party_name) DO UPDATE SET
            summary=excluded.summary,
            model_used=excluded.model_used,
            created_at=CURRENT_TIMESTAMP
    ''', (session_id, party_name, summary, model_used))
    conn.commit()
    conn.close()

def save_word_metrics(session_id, word_of_the_day, top_ngrams):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO word_metrics (session_id, word_of_the_day, top_ngrams_json)
        VALUES (?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            word_of_the_day=excluded.word_of_the_day,
            top_ngrams_json=excluded.top_ngrams_json,
            created_at=CURRENT_TIMESTAMP
    ''', (session_id, word_of_the_day, json.dumps(top_ngrams)))
    conn.commit()
    conn.close()

def get_available_session_dates():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT session_date FROM sessions ORDER BY session_date DESC')
    rows = cursor.fetchall()
    conn.close()
    return [r['session_date'] for r in rows]

def get_speeches_for_session(session_date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sp.id, s.name as speaker_name, p.name as party_name, p.abbreviation as party_abbr,
               p.color as party_color, s.constituency, sp.h2_heading, sp.h3_heading,
               sp.text, sp.timestamp, sp.sequence
        FROM speeches sp
        JOIN speakers s ON sp.speaker_id = s.id
        LEFT JOIN parties p ON s.party_id = p.id
        JOIN sessions ss ON sp.session_id = ss.id
        WHERE ss.session_date = ?
        ORDER BY sp.sequence ASC
    ''', (str(session_date),))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_party_summaries(session_date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ps.party_name, ps.summary, ps.model_used, p.color, p.abbreviation
        FROM party_summaries ps
        JOIN sessions ss ON ps.session_id = ss.id
        LEFT JOIN parties p ON ps.party_name = p.name
        WHERE ss.session_date = ?
    ''', (str(session_date),))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_word_metrics(session_date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT wm.word_of_the_day, wm.top_ngrams_json
        FROM word_metrics wm
        JOIN sessions ss ON wm.session_id = ss.id
        WHERE ss.session_date = ?
    ''', (str(session_date),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'word_of_the_day': row['word_of_the_day'],
            'top_ngrams': json.loads(row['top_ngrams_json']) if row['top_ngrams_json'] else []
        }
    return None

if __name__ == '__main__':
    create_tables()
    print("Database initialized successfully.")

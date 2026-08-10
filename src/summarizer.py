import os
import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

SYSTEM_PROMPT = """You are a neutral, objective parliamentary analyst for OpenQueensPark.
Your task is to summarize the daily proceedings of the Legislative Assembly of Ontario.
You must provide a strictly neutral, factual, party-by-party summary without political bias or commentary.
Highlight key legislative proposals, question period inquiries, and major debate points raised by each party.
"""

def group_speeches_by_party(speech_records):
    party_speeches = {}
    for sp in speech_records:
        party = sp.get('party_name') or 'Independent'
        if party not in party_speeches:
            party_speeches[party] = []
        party_speeches[party].append(sp)
    return party_speeches

def generate_summary_gemini(party_name, speech_text, api_key=GEMINI_API_KEY):
    """
    Calls Google AI Studio (Gemini 2.0 Flash) API.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    prompt = f"{SYSTEM_PROMPT}\n\nParty: {party_name}\nSpeeches recorded today:\n{speech_text}\n\nProvide a 3-4 paragraph neutral summary of {party_name}'s key positions, questions, and statements made today in the Ontario Legislature."

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            candidates = data.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                if parts:
                    return parts[0].get('text', '').strip()
        logger.warning(f"Gemini API returned status {response.status_code}: {response.text[:200]}")
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
    return None

def generate_summary_openrouter(party_name, speech_text, api_key=OPENROUTER_API_KEY):
    """
    Calls OpenRouter API (using google/gemini-2.0-flash-001 or meta-llama/llama-3.3-70b-instruct).
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://openqueenspark.ca",
        "X-Title": "OpenQueensPark",
        "Content-Type": "application/json"
    }

    prompt = f"{SYSTEM_PROMPT}\n\nParty: {party_name}\nSpeeches recorded today:\n{speech_text}\n\nProvide a 3-4 paragraph neutral summary of {party_name}'s key positions, questions, and statements made today in the Ontario Legislature."

    payload = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            choices = data.get('choices', [])
            if choices:
                return choices[0].get('message', {}).get('content', '').strip()
        logger.warning(f"OpenRouter API status {response.status_code}: {response.text[:200]}")
    except Exception as e:
        logger.error(f"OpenRouter API error: {e}")
    return None

def generate_summary_ollama(party_name, speech_text, model=DEFAULT_OLLAMA_MODEL):
    """
    Calls local Ollama API.
    """
    prompt = f"{SYSTEM_PROMPT}\n\nParty: {party_name}\nSpeeches recorded today:\n{speech_text}\n\nProvide a 3-4 paragraph neutral summary of {party_name}'s key positions, questions, and statements made today in the Ontario Legislature."

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3}
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=15)
        if response.status_code == 200:
            return response.json().get('response', '').strip()
    except Exception:
        pass
    return None

def generate_fallback_summary(party_name, speeches):
    total_speeches = len(speeches)
    speakers = set(sp.get('speaker_name', 'MPP') for sp in speeches)
    sections = set(sp.get('h2_heading', '') for sp in speeches if sp.get('h2_heading'))

    summary = f"**Daily Overview for {party_name}:**\n\n"
    summary += f"Members of {party_name} delivered {total_speeches} statement(s)/speech(es) across key proceedings including: {', '.join(list(sections)[:4])}.\n\n"
    summary += f"Active speakers included: {', '.join(list(speakers)[:6])}.\n\n"

    summary += "**Key Points Raised:**\n"
    for sp in speeches[:4]:
        text_snippet = sp.get('text', '')[:200]
        summary += f"- **{sp.get('speaker_name')}** ({sp.get('h2_heading', 'Floor')}): \"{text_snippet}...\"\n"

    return summary

def generate_party_summary(party_name, speeches):
    if not speeches:
        return "No speeches recorded for this party on this date."

    # Format text context
    speech_text = ""
    for sp in speeches:
        speaker = sp.get('speaker_name', 'MPP')
        h2 = sp.get('h2_heading', '')
        text = sp.get('text', '')[:1000]
        speech_text += f"\n- {speaker} ({h2}): {text}\n"

    # Priority 1: Google AI Studio
    if GEMINI_API_KEY:
        logger.info(f"Generating summary for {party_name} via Google AI Studio...")
        res = generate_summary_gemini(party_name, speech_text, GEMINI_API_KEY)
        if res:
            return res

    # Priority 2: OpenRouter
    if OPENROUTER_API_KEY:
        logger.info(f"Generating summary for {party_name} via OpenRouter...")
        res = generate_summary_openrouter(party_name, speech_text, OPENROUTER_API_KEY)
        if res:
            return res

    # Priority 3: Local Ollama
    res = generate_summary_ollama(party_name, speech_text)
    if res:
        return res

    # Priority 4: Rule-based fallback
    return generate_fallback_summary(party_name, speeches)

def generate_all_party_summaries(speech_records):
    grouped = group_speeches_by_party(speech_records)
    summaries = {}

    for party_name, party_speeches in grouped.items():
        if party_name == "Non-Partisan / Presiding Officer":
            continue
        logger.info(f"Generating summary for {party_name} ({len(party_speeches)} speeches)...")
        summaries[party_name] = generate_party_summary(party_name, party_speeches)

    return summaries

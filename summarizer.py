import os
import requests
import json
import logging

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a neutral, objective parliamentary analyst for OpenQueensPark.
Your task is to summarize the daily proceedings of the Legislative Assembly of Ontario.
You must provide a strictly neutral, factual, party-by-party summary without political bias or commentary.
Highlight key legislative proposals, question period inquiries, and major debate points raised by each party.
"""

def group_speeches_by_party(speech_records):
    """
    Groups speeches by political party name.
    """
    party_speeches = {}
    for sp in speech_records:
        party = sp.get('party_name') or 'Independent'
        if party not in party_speeches:
            party_speeches[party] = []
        party_speeches[party].append(sp)
    return party_speeches

def generate_party_summary_ollama(party_name, speeches, model=DEFAULT_MODEL):
    """
    Calls local Ollama instance to generate neutral summary for a party's daily speeches.
    """
    if not speeches:
        return "No speeches recorded for this party on this date."

    # Format speeches for context window (cap at ~4000 words if needed)
    speech_text = ""
    for sp in speeches:
        speaker = sp.get('speaker_name', 'MPP')
        h2 = sp.get('h2_heading', '')
        text = sp.get('text', '')[:1000] # cap per speech to fit context
        speech_text += f"\n- {speaker} ({h2}): {text}\n"

    prompt = f"{SYSTEM_PROMPT}\n\nParty: {party_name}\nSpeeches recorded today:\n{speech_text}\n\nProvide a 3-4 paragraph neutral summary of {party_name}'s key positions, questions, and statements made today in the Ontario Legislature."

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3
        }
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            return result.get('response', 'No summary generated.').strip()
        else:
            logger.warning(f"Ollama returned status code {response.status_code}")
            return generate_fallback_summary(party_name, speeches)
    except Exception as e:
        logger.info(f"Ollama API unreachable ({e}). Using fallback rule-based summarizer.")
        return generate_fallback_summary(party_name, speeches)

def generate_fallback_summary(party_name, speeches):
    """
    Extractive fallback summary when Ollama is offline or unavailable.
    """
    total_speeches = len(speeches)
    speakers = set(sp.get('speaker_name', 'MPP') for sp in speeches)
    sections = set(sp.get('h2_heading', '') for sp in speeches if sp.get('h2_heading'))

    summary = f"**Daily Overview for {party_name}:**\n\n"
    summary += f"Members of {party_name} delivered {total_speeches} statement(s)/speech(es) across key proceedings including: {', '.join(list(sections)[:4])}.\n\n"
    summary += f"Active speakers included: {', '.join(list(speakers)[:6])}.\n\n"

    # Include key excerpts
    summary += "**Key Points Raised:**\n"
    for sp in speeches[:4]:
        text_snippet = sp.get('text', '')[:200]
        summary += f"- **{sp.get('speaker_name')}** ({sp.get('h2_heading', 'Floor')}): \"{text_snippet}...\"\n"

    return summary

def generate_all_party_summaries(speech_records, model=DEFAULT_MODEL):
    """
    Generates neutral summaries for all active parties in the session records.
    Returns:
        dict { party_name: summary_text }
    """
    grouped = group_speeches_by_party(speech_records)
    summaries = {}

    for party_name, party_speeches in grouped.items():
        if party_name == "Non-Partisan / Presiding Officer":
            continue
        logger.info(f"Generating summary for {party_name} ({len(party_speeches)} speeches)...")
        summary = generate_party_summary_ollama(party_name, party_speeches, model=model)
        summaries[party_name] = summary

    return summaries

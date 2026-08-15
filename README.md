# OpenQueensPark 🏛️

**Automated Ontario Legislature Overview & Analytics**

Summarizing the daily proceedings and activity in Ontario's Legislature at Queen's Park.

Deeply inspired by [openparliament](https://github.com/michaelmulley/openparliament) and [myparliament.ca](https://myparliament.ca/provincial/on) (which is no longer actively updated and lacked features like n-gram word visualization and neutral LLM summaries of daily debates).

---

## 🛠️ Architecture & Technical Overview

OpenQueensPark is a full-stack civic technology platform that scrapes official Hansard transcripts from the Legislative Assembly of Ontario ([ola.org](https://www.ola.org)), processes speeches into structured SQLite storage, and serves an interactive dashboard with daily political discourse analytics.

```
OLA Official Hansard (HTML)
           │
           ▼
  [ parser.py ] ──▶ HTML Parsing & Speaker/Party Extraction
           │
           ▼
  [ database.py ] ──▶ SQLite Storage (`database.db`)
      │         │
      │         ├──▶ [ analysis.py ]   ──▶ Custom N-Gram Tokenization & Word Cloud
      │         └──▶ [ summarizer.py ] ──▶ Multi-Provider AI Summaries (Gemini / OpenRouter / Ollama)
      ▼
  [ app.py ] ──▶ Streamlit Interactive Web Interface
```

### Key Modules (`src/`)

- **`src/parser.py`**: BeautifulSoup4 HTML parser tailored for OLA Hansard structure. Extracts `speakerStart` paragraph blocks, speaker titles, party affiliations, constituency metadata, section headings (`Orders of the Day`, `Question Period`), and timestamps.
- **`src/database.py`**: SQLite relational schema (`sessions`, `speakers`, `parties`, `speeches`, `party_summaries`, `word_metrics`).
- **`src/analysis.py`**: Custom n-gram tokenization using `itertools.tee` (`ngram_iterator`) to compute 1-gram, 2-gram, and 3-gram relative frequency scores, extract "Word of the Day", and generate daily speech Word Clouds.
- **`src/summarizer.py`**: Neutral party-by-party summary engine with multi-provider fallback hierarchy:
  1. Google AI Studio (`GEMINI_API_KEY` - Gemini 2.0 Flash)
  2. OpenRouter (`OPENROUTER_API_KEY`)
  3. Local Ollama (`llama3`)
  4. Structured Rule-Based Fallback
- **`src/scraper.py`**: Automated pipeline driver that orchestrates fetching, parsing, analysis, and summary generation.
- **`app.py`**: Streamlit web dashboard featuring calendar navigation, party summaries sorted by seat count order (PC > NDP > Liberal > Green > Independent), interactive visualizations, and searchable Hansard speech browser.

---

## 🚀 Running Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run Streamlit app locally
python -m streamlit run app.py
```

---

## ☁️ Deployment Options

- **Streamlit Community Cloud**: Automatically deployed from `main` branch with zero server setup.
- **Raspberry Pi + Cloudflare Tunnel**: Hosted locally on Raspberry Pi using `cloudflared` to expose `localhost:8501` securely to `openqueenspark.ca` (see configuration files in `deployment/`).

# 🚀 Anikoto Resolver

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Build Status](https://img.shields.io/badge/tests-passing-brightgreen.svg)]()
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A production-grade, resilient Python engine and CLI tool that resolves MyAnimeList (MAL) IDs and Anime Titles to internal numeric **Anikoto.cz** IDs (`data-id`), used to construct video stream and embed URLs.

---

## ✨ Features

- 🔍 **Exhaustive Multi-Query Variant Search**: Automatically generates query permutations (English, Romaji, Synonyms, Base titles without subtitles, and Season-stripped variants) to guarantee matching even when title formats differ.
- 🎯 **Advanced Season & Part Disambiguation**: Parses season/part indicators (`Season 2`, `2nd Season`, `Part 3`, `Cour 2`) to prevent matching wrong seasons (e.g. matching *Jujutsu Kaisen Season 1* when *Season 2* was requested).
- ⚡ **Rate-Limit & WAF Resilient**: Automatically handles `429 Too Many Requests` and WAF rate limiting using exponential backoff with jitter and `Retry-After` header parsing.
- 🛡️ **Multi-Stage Regex & DOM Fallbacks**: Extracts `data-id` via BeautifulSoup DOM queries, followed by multi-pattern regex scans across raw HTML text if DOM structures shift.
- 🚀 **Zero-Dependency Mode for App Pipelines**: Allows resolving directly from pre-fetched title lists without hitting Jikan API at request time.
- 💻 **Clean CLI & JSON Output**: Provides stdout piping support (`internal_id` only) and structured `--json` mode for microservice integration.

---

## 📦 Installation

Clone the repository and install locally:

```bash
git clone https://github.com/your-username/anikoto-resolver.git
cd anikoto-resolver
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

---

## 💻 CLI Usage

### Resolve by MyAnimeList ID

```bash
# Get numeric internal ID only (clean for piping)
anikoto-resolver 52991
# Output: 6351

# Output with debug diagnostics
anikoto-resolver 52991 --debug

# Output full JSON response
anikoto-resolver 52991 --json
```

**JSON Output Example**:
```json
{
  "internal_id": "6351",
  "slug": "frieren-beyond-journey-s-end-c6fbj",
  "matched_title": "Frieren: Beyond Journey's End",
  "score": 165.0,
  "year": 2023,
  "type": "TV"
}
```

### Resolve by Titles (No Jikan Call)

```bash
anikoto-resolver --titles "Chainsaw Man" --year 2022 --json
```

---

## 🐍 Python Library API

### Option A: App Integration (Direct Titles - Fast & Reliable)
If your app already has title variants from your database/pipeline, call `resolve_from_titles()` directly:

```python
from anikoto_resolver import resolve_from_titles, ResolveError

try:
    result = resolve_from_titles(
        titles=["Chainsaw Man", "Chainsaw-man"],
        year=2022,
        anime_type="TV"
    )
    print(f"Internal ID: {result['internal_id']}")  # 6805
    print(f"Matched Title: {result['matched_title']}")
except ResolveError as e:
    print(f"Resolution failed: {e}")
```

### Option B: MAL ID Resolution (Hits Jikan API First)

```python
from anikoto_resolver import resolve, ResolveError

try:
    result = resolve(mal_id=40748, min_score=50.0)
    print(f"Resolved ID: {result['internal_id']}")  # 1103
except ResolveError as e:
    print(f"Error: {e}")
```

---

## 🧪 Running Unit Tests

Run the automated test suite to verify search algorithms, season parsing, and live resolution:

```bash
python -m unittest discover -s tests
```

---

## 📜 License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more details.

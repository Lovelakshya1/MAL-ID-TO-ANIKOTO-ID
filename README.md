# 🚀 Anikoto Resolver

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/lovelakshya/anikoto-resolver)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Build Status](https://img.shields.io/badge/tests-passing-brightgreen.svg)]()
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A production-grade, resilient Python engine, CLI tool, and **Vercel Serverless API** that resolves MyAnimeList (MAL) IDs and Anime Titles to internal numeric **Anikoto.cz** IDs (`data-id`), used to construct video stream and embed URLs.

---

## ✨ Features

- 🌐 **Vercel Serverless Ready**: Deploy as a zero-config serverless API microservice on Vercel (`GET /api/resolve?id=44511`) with CORS support enabled out of the box.
- 🔍 **Exhaustive Multi-Query Variant Search**: Automatically generates query permutations (English, Romaji, Synonyms, Base titles without subtitles, and Season-stripped variants) to guarantee matching even when title formats differ.
- 🎯 **Advanced Season & Part Disambiguation**: Parses season/part indicators (`Season 2`, `2nd Season`, `Part 3`, `Cour 2`) to prevent matching wrong seasons (e.g. matching *Jujutsu Kaisen Season 1* when *Season 2* was requested).
- ⚡ **Rate-Limit & WAF Resilient**: Automatically handles `429 Too Many Requests` and WAF rate limiting using exponential backoff with jitter and `Retry-After` header parsing.
- 🛡️ **Multi-Stage Regex & DOM Fallbacks**: Extracts `data-id` via BeautifulSoup DOM queries, followed by multi-pattern regex scans across raw HTML text if DOM structures shift.
- 🚀 **Zero-Dependency Mode for App Pipelines**: Allows resolving directly from pre-fetched title lists without hitting Jikan API at request time.
- 💻 **Clean CLI & JSON Output**: Provides stdout piping support (`internal_id` only) and structured `--json` mode for microservice integration.

---

## ⚡ Vercel Deployment (Serverless API)

You can deploy this repository directly to **Vercel** with zero configuration:

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/lovelakshya/anikoto-resolver)

### Serverless API Endpoints

Once deployed to Vercel, your live API endpoints will be:

#### 1. Resolve by MAL ID:
```http
GET https://your-app.vercel.app/api/resolve?id=44511
```

#### 2. Resolve by Title:
```http
GET https://your-app.vercel.app/api/resolve?title=Chainsaw+Man&year=2022
```

**JSON Response**:
```json
{
  "internal_id": "6805",
  "slug": "chainsaw-man-efeig",
  "matched_title": "Chainsaw Man",
  "score": 165.0,
  "year": 2022,
  "type": "TV"
}
```

---

## 📦 Local Installation

Clone the repository and install locally:

```bash
git clone https://github.com/lovelakshya/anikoto-resolver.git
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

---

## 🐍 Python Library API

### App Integration (Direct Titles - Fast & Reliable)

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

---

## 🧪 Running Unit Tests

Run the automated test suite to verify search algorithms, season parsing, and live resolution:

```bash
python -m unittest discover -s tests
```

---

## 👤 Author & Credits

- **Author**: **[lovelakshya](https://github.com/lovelakshya1)**
- **Development**: Developed and built with AI assistance (Advanced Agentic Coding).

---

## 📜 License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more details.

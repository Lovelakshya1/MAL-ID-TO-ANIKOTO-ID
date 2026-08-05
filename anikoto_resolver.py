#!/usr/bin/env python3
"""
Anikoto Resolver — Production-grade MAL ID & Title Resolver for Anikoto.cz

Resolves anime titles or MyAnimeList (MAL) IDs to internal numeric Anikoto IDs 
used for generating stream/embed URLs.

Features:
- Exhaustive Multi-Query Variant Search (English, Romaji, Synonyms, Base Titles).
- Advanced Multi-Factor Scoring (Similarity + Season/Part checks + Year/Type weights).
- Resilient Rate-Limiting Retries (429 Too Many Requests backoff + Retry-After headers).
- Multi-Stage HTML & Regex Fallback Extraction for `data-id`.
- Standalone CLI & Programmatic Library Interface.

Usage (CLI):
    python anikoto_resolver.py 44511
    python anikoto_resolver.py 44511 --debug
    python anikoto_resolver.py --titles "Chainsaw Man" --year 2022 --json

Usage (Python Import - No Jikan Dependency):
    from anikoto_resolver import resolve_from_titles
    result = resolve_from_titles(["Chainsaw Man"], year=2022, anime_type="TV")
    print(result["internal_id"])

Usage (Python Import - Hits Jikan):
    from anikoto_resolver import resolve
    result = resolve(44511)
    print(result["internal_id"])
"""

import re
import sys
import time
import json
import random
import argparse
import requests
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

__version__ = "1.0.0"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/html, */*",
    "Referer": "https://anikoto.cz/",
}

ANILIST_GRAPHQL_URL = "https://graphql.anilist.co"
JIKAN_URL = "https://api.jikan.moe/v4/anime/{}"
SEARCH_URL = "https://anikoto.cz/ajax/anime/search"
WATCH_URL = "https://anikoto.cz/watch/{}"

TYPE_ALIASES = {"TV_SHORT": "TV", "SPECIALS": "Special"}
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class AnikotoError(Exception):
    """Base exception class for anikoto_resolver."""
    pass


class ResolveError(AnikotoError):
    """Raised when no match satisfies confidence thresholds."""
    pass


class JikanAPIError(AnikotoError):
    """Raised on Jikan API communication errors."""
    pass


class AnikotoAPIError(AnikotoError):
    """Raised on Anikoto network/scraping errors."""
    pass


class HttpClient:
    """Resilient HTTP client with retry logic and WAF rate-limit handling."""
    def __init__(self, max_retries: int = 4, backoff_factor: float = 1.5, timeout: float = 12.0):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> requests.Response:
        last_error = None
        req_headers = DEFAULT_HEADERS.copy()
        if headers:
            req_headers.update(headers)

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, headers=req_headers, timeout=self.timeout)
                if response.status_code not in RETRYABLE_STATUS_CODES:
                    return response
                
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = float(retry_after)
                else:
                    jitter = random.uniform(0.1, 0.4)
                    delay = (self.backoff_factor * (2 ** (attempt - 1))) + jitter
                    
                last_error = f"HTTP {response.status_code}"
                if attempt < self.max_retries:
                    time.sleep(delay)
            except requests.RequestException as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    time.sleep(self.backoff_factor * attempt)

        raise AnikotoAPIError(f"Request to '{url}' failed after {self.max_retries} attempts (last error: {last_error})")


def normalize_title(title: str) -> str:
    if not title:
        return ""
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def extract_season_info(title: str) -> str:
    if not title:
        return "s1"
    title_lower = title.lower()
    
    m = re.search(r'\b(?:season|s)\s*(\d+)\b', title_lower)
    if m:
        return f"s{m.group(1)}"
    m = re.search(r'\b(\d+)(?:st|nd|rd|th)\s+season\b', title_lower)
    if m:
        return f"s{m.group(1)}"
    m = re.search(r'\bpart\s*(\d+)\b', title_lower)
    if m:
        return f"p{m.group(1)}"
    m = re.search(r'\bcour\s*(\d+)\b', title_lower)
    if m:
        return f"c{m.group(1)}"
    return "s1"


def similarity_score(title_a: str, title_b: str) -> float:
    norm_a = normalize_title(title_a)
    norm_b = normalize_title(title_b)
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0

    seq_ratio = SequenceMatcher(None, norm_a, norm_b).ratio()

    words_a = set(norm_a.split())
    words_b = set(norm_b.split())
    if words_a and words_b:
        intersection = words_a.intersection(words_b)
        token_ratio = len(intersection) / max(len(words_a), len(words_b))
    else:
        token_ratio = 0.0

    return max(seq_ratio, token_ratio)


def score_candidate(mal_titles: List[str], mal_year: Optional[int], mal_type: Optional[str], candidate: Dict[str, Any]) -> float:
    best_title_score = 0.0
    matched_mal_season = "s1"
    
    for mal_title in mal_titles:
        s_score = similarity_score(mal_title, candidate["title"])
        if s_score > best_title_score:
            best_title_score = s_score
            matched_mal_season = extract_season_info(mal_title)

    cand_season = extract_season_info(candidate["title"])
    score = best_title_score * 100.0

    if matched_mal_season and cand_season:
        if matched_mal_season == cand_season:
            score += 25.0
        else:
            score -= 35.0

    if mal_year and candidate.get("year"):
        cand_year = candidate["year"]
        if cand_year == mal_year:
            score += 25.0
        elif abs(cand_year - mal_year) <= 1:
            score += 10.0

    norm_mal_type = TYPE_ALIASES.get(mal_type, mal_type) if mal_type else None
    if norm_mal_type and candidate.get("type"):
        if candidate["type"] == norm_mal_type:
            score += 15.0

    return max(0.0, score)


def generate_query_variants(titles: List[str]) -> List[str]:
    variants: List[str] = []
    for title in titles:
        if not title:
            continue
        clean_t = title.strip()
        if clean_t and clean_t not in variants:
            variants.append(clean_t)

        for sep in [":", "-", "—", "~", "("]:
            if sep in clean_t:
                base = clean_t.split(sep)[0].strip()
                if len(base) >= 2 and base not in variants:
                    variants.append(base)

        cleaned = re.sub(r'\b(?:Season|Part|Cour|\d+nd|\d+rd|\d+th|\d+st)\b.*$', '', clean_t, flags=re.IGNORECASE).strip()
        if len(cleaned) >= 2 and cleaned not in variants:
            variants.append(cleaned)

    return list(dict.fromkeys(variants))


class AnikotoResolver:
    def __init__(self, client: Optional[HttpClient] = None):
        self.client = client or HttpClient()
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_mal_titles(self, mal_id: int) -> Dict[str, Any]:
        """
        Fetch title variants & metadata for MAL ID.
        Uses AniList GraphQL API as primary (sub-100ms, zero 504 Gateway Timeouts),
        with Jikan API as secondary fallback.
        """
        # 1. Primary: AniList GraphQL API
        try:
            query = """
            query ($id: Int) {
              Media(idMal: $id, type: ANIME) {
                title { romaji english native }
                synonyms
                startDate { year }
                format
              }
            }
            """
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}
            resp = self.client.session.post(
                ANILIST_GRAPHQL_URL,
                json={"query": query, "variables": {"id": mal_id}},
                headers=headers,
                timeout=8
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {}).get("Media")
                if data:
                    titles = set()
                    t_obj = data.get("title", {})
                    if t_obj.get("romaji"): titles.add(t_obj["romaji"])
                    if t_obj.get("english"): titles.add(t_obj["english"])
                    for syn in data.get("synonyms", []):
                        if syn: titles.add(syn)
                    titles.discard(None)
                    
                    year = data.get("startDate", {}).get("year")
                    fmt = data.get("format")
                    
                    if titles:
                        return {
                            "titles": list(titles),
                            "primary": t_obj.get("romaji") or t_obj.get("english") or list(titles)[0],
                            "year": year,
                            "type": TYPE_ALIASES.get(fmt, fmt)
                        }
        except Exception as e:
            sys.stderr.write(f"[AnikotoResolver WARNING] AniList lookup failed for MAL {mal_id}: {e}, falling back to Jikan...\n")

        # 2. Secondary Fallback: Jikan API
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}
            resp = self.client.session.get(JIKAN_URL.format(mal_id), headers=headers, timeout=10)
            if resp.status_code != 200:
                raise JikanAPIError(f"Jikan API responded with status {resp.status_code} for MAL ID {mal_id}")

            data = resp.json().get("data")
            if not data:
                raise JikanAPIError(f"No Jikan data payload returned for MAL ID {mal_id}")

            titles = {data.get("title"), data.get("title_english")}
            for entry in data.get("titles", []):
                titles.add(entry.get("title"))
            titles.discard(None)

            if not titles:
                raise JikanAPIError(f"No usable titles returned by Jikan for MAL ID {mal_id}")

            return {
                "titles": list(titles),
                "primary": data.get("title"),
                "year": data.get("year"),
                "type": TYPE_ALIASES.get(data.get("type"), data.get("type")),
            }
        except JikanAPIError:
            raise
        except Exception as e:
            raise JikanAPIError(f"Failed to fetch metadata from Jikan API for MAL ID {mal_id}: {e}")

    def search_candidates(self, titles: List[str]) -> List[Dict[str, Any]]:
        variants = generate_query_variants(titles)
        candidates_by_slug: Dict[str, Dict[str, Any]] = {}

        for query in variants:
            if not any(ord(c) < 128 for c in query):
                continue

            # 1. AJAX search suggestions
            try:
                response = self.client.get(SEARCH_URL, params={"keyword": query})
                if response.status_code == 200:
                    html_content = response.json().get("result", {}).get("html", "")
                    if html_content:
                        soup = BeautifulSoup(html_content, "html.parser")
                        for a_tag in soup.find_all("a", class_="item"):
                            href = a_tag.get("href", "")
                            if "/watch/" not in href: continue
                            slug = href.split("/watch/")[-1].split("/")[0]
                            name_div = a_tag.find("div", class_="name")
                            title = name_div.text.strip() if name_div else slug

                            year, type_ = None, None
                            meta_div = a_tag.find("div", class_="meta")
                            if meta_div:
                                for span in meta_div.find_all("span", class_="dot"):
                                    text = span.text.strip()
                                    if text.isdigit() and len(text) == 4: year = int(text)
                                    elif text in {"TV", "Movie", "OVA", "ONA", "Special"}: type_ = text

                            if slug not in candidates_by_slug:
                                candidates_by_slug[slug] = {"title": title, "slug": slug, "year": year, "type": type_}
            except Exception:
                pass

            # 2. Filter search page (captures all results beyond top 5)
            try:
                response = self.client.get("https://anikoto.cz/filter", params={"keyword": query})
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    list_items = soup.find("div", id="list-items")
                    if list_items:
                        for div in list_items.find_all("div", class_="item"):
                            a_tag = div.find("a", class_="d-title") or div.find("a", href=True)
                            if not a_tag: continue
                            href = a_tag.get("href", "")
                            if "/watch/" not in href: continue
                            slug = href.split("/watch/")[-1].split("/")[0]
                            title = a_tag.text.strip()

                            year, type_ = None, None
                            meta_div = div.find("div", class_="meta")
                            if meta_div:
                                for m_item in meta_div.find_all("div", class_="m-item"):
                                    lbl = m_item.find("label")
                                    if lbl:
                                        txt = lbl.text.strip()
                                        if txt in {"TV", "Movie", "OVA", "ONA", "Special", "TV_SHORT"}: type_ = txt

                            m_year = re.search(r'\b(19\d\d|20\d\d)\b', div.text)
                            if m_year: year = int(m_year.group(1))

                            if slug not in candidates_by_slug:
                                candidates_by_slug[slug] = {"title": title, "slug": slug, "year": year, "type": type_}
            except Exception:
                pass

        return list(candidates_by_slug.values())

    def get_internal_id(self, slug: str) -> str:
        resp = self.client.get(WATCH_URL.format(slug))
        if resp.status_code != 200:
            raise AnikotoAPIError(f"Watch page error ({resp.status_code}) for slug '{slug}'")

        text = resp.text
        soup = BeautifulSoup(text, "html.parser")
        watch_main = soup.find("div", id="watch-main")
        if watch_main and watch_main.get("data-id"):
            return str(watch_main.get("data-id"))

        m = re.search(r'data-id=["\'](\d+)["\']', text)
        if m:
            return m.group(1)

        m = re.search(r'id=["\']watch-main["\'][^>]*data-id=["\'](\d+)["\']', text)
        if m:
            return m.group(1)

        m = re.search(r'(?:anime_id|media_id|episode_id)\s*[:=]\s*["\']?(\d+)["\']?', text)
        if m:
            return m.group(1)

        raise AnikotoAPIError(f"Failed to extract 'data-id' attribute for slug '{slug}'")

    def resolve_from_titles(
        self,
        titles: List[str],
        year: Optional[int] = None,
        anime_type: Optional[str] = None,
        min_score: float = 50.0,
        debug: bool = False
    ) -> Dict[str, Any]:
        cleaned_titles = [t.strip() for t in titles if t and t.strip()]
        if not cleaned_titles:
            raise ResolveError("resolve_from_titles() called with empty titles list")

        cache_key = f"titles:{':'.join(sorted(cleaned_titles))}:{year}:{anime_type}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if debug:
            print(f"[AnikotoResolver DEBUG] Resolving titles={cleaned_titles}, year={year}, type={anime_type}", file=sys.stderr)

        candidates = self.search_candidates(cleaned_titles)
        if not candidates:
            raise ResolveError(f"No candidates found on Anikoto for query variants of '{cleaned_titles[0]}'")

        best_cand: Optional[Dict[str, Any]] = None
        best_score: float = -1.0

        for cand in candidates:
            score = score_candidate(cleaned_titles, year, anime_type, cand)
            if debug:
                print(f"  Candidate '{cand['title']}' (slug={cand['slug']}, {cand['year']}, {cand['type']}) -> Score: {score:.1f}", file=sys.stderr)

            if score > best_score:
                best_cand = cand
                best_score = score

        if not best_cand or best_score < min_score:
            best_desc = f"'{best_cand['title']}' at score {best_score:.1f}" if best_cand else "no scored candidates"
            raise ResolveError(f"No confident match found for '{cleaned_titles[0]}' — best was {best_desc} (min score: {min_score})")

        internal_id = self.get_internal_id(best_cand["slug"])

        result = {
            "internal_id": internal_id,
            "slug": best_cand["slug"],
            "matched_title": best_cand["title"],
            "score": round(best_score, 1),
            "year": best_cand.get("year"),
            "type": best_cand.get("type"),
        }

        self._cache[cache_key] = result
        return result

    def resolve(
        self,
        mal_id: int,
        min_score: float = 50.0,
        debug: bool = False
    ) -> Dict[str, Any]:
        cache_key = f"mal_id:{mal_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        mal_data = self.get_mal_titles(mal_id)
        if debug:
            print(f"[AnikotoResolver DEBUG] MAL {mal_id} metadata: titles={mal_data['titles']}, year={mal_data['year']}, type={mal_data['type']}", file=sys.stderr)

        result = self.resolve_from_titles(
            titles=mal_data["titles"],
            year=mal_data["year"],
            anime_type=mal_data["type"],
            min_score=min_score,
            debug=debug
        )

        self._cache[cache_key] = result
        return result


_default_instance = AnikotoResolver()

def resolve_from_titles(
    titles: List[str],
    year: Optional[int] = None,
    anime_type: Optional[str] = None,
    min_score: float = 50.0,
    debug: bool = False
) -> Dict[str, Any]:
    return _default_instance.resolve_from_titles(titles, year=year, anime_type=anime_type, min_score=min_score, debug=debug)

def resolve(
    mal_id: int,
    min_score: float = 50.0,
    debug: bool = False
) -> Dict[str, Any]:
    return _default_instance.resolve(mal_id, min_score=min_score, debug=debug)


def main():
    parser = argparse.ArgumentParser(
        prog="anikoto_resolver",
        description="Resiliently resolves MyAnimeList IDs or titles to internal numeric Anikoto IDs."
    )
    
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("mal_id", type=int, nargs="?", help="MyAnimeList anime ID (e.g. 52991)")
    target_group.add_argument("--titles", "-t", type=str, nargs="+", help="One or more title strings to resolve without Jikan API")

    parser.add_argument("--year", "-y", type=int, help="Optional release year hint for title resolution")
    parser.add_argument("--type", "-type", type=str, help="Optional media type hint (TV, Movie, OVA, Special)")
    parser.add_argument("--min-score", type=float, default=50.0, help="Minimum confidence match score threshold (default: 50.0)")
    parser.add_argument("--json", "-j", action="store_true", help="Output full resolution metadata as JSON")
    parser.add_argument("--debug", "-d", action="store_true", help="Print matching diagnostics to stderr")

    args = parser.parse_args()
    resolver = AnikotoResolver()

    try:
        if args.titles:
            res = resolver.resolve_from_titles(
                titles=args.titles,
                year=args.year,
                anime_type=args.type,
                min_score=args.min_score,
                debug=args.debug
            )
        else:
            res = resolver.resolve(
                mal_id=args.mal_id,
                min_score=args.min_score,
                debug=args.debug
            )

        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(res["internal_id"])
            if args.debug:
                print(f"# slug='{res['slug']}' matched='{res['matched_title']}' score={res['score']}", file=sys.stderr)

    except AnikotoError as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Fatal Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

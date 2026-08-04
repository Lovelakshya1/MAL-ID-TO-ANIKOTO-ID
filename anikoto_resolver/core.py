"""
Core Anikoto Resolver Class & Public API.
"""

import re
import sys
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from .client import HttpClient
from .exceptions import ResolveError, JikanAPIError, AnikotoAPIError
from .search import search_anikoto_exhaustive
from .scorer import score_candidate, TYPE_ALIASES

ANILIST_GRAPHQL_URL = "https://graphql.anilist.co"
JIKAN_URL = "https://api.jikan.moe/v4/anime/{}"
WATCH_URL = "https://anikoto.cz/watch/{}"


class AnikotoResolver:
    """
    Production-grade, resilient resolver for mapping anime titles / MAL IDs to 
    internal numeric Anikoto IDs.
    """

    def __init__(self, client: Optional[HttpClient] = None):
        self.client = client or HttpClient()
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_mal_titles(self, mal_id: int) -> Dict[str, Any]:
        """
        Fetch title variants & metadata for MAL ID.
        Uses AniList GraphQL API as primary (sub-100ms, zero 504 Gateway Timeouts),
        with Jikan API as secondary fallback.
        """
        # 1. Primary: AniList GraphQL API (Fast, Cloudflare-backed, zero 504 Gateway Timeouts)
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

    def get_internal_id(self, slug: str) -> str:
        """
        Extracts the internal numeric `data-id` attribute from an Anikoto watch page using 
        BeautifulSoup and multi-stage regex fallbacks.
        """
        resp = self.client.get(WATCH_URL.format(slug))
        if resp.status_code != 200:
            raise AnikotoAPIError(f"Watch page error ({resp.status_code}) for slug '{slug}'")

        text = resp.text

        # 1. Primary: BeautifulSoup #watch-main data-id attribute
        soup = BeautifulSoup(text, "html.parser")
        watch_main = soup.find("div", id="watch-main")
        if watch_main and watch_main.get("data-id"):
            return str(watch_main.get("data-id"))

        # 2. Fallback Regex 1: Any data-id="1234"
        m = re.search(r'data-id=["\'](\d+)["\']', text)
        if m:
            return m.group(1)

        # 3. Fallback Regex 2: Watch main container data-id
        m = re.search(r'id=["\']watch-main["\'][^>]*data-id=["\'](\d+)["\']', text)
        if m:
            return m.group(1)

        # 4. Fallback Regex 3: JS variable declarations (anime_id = 1234)
        m = re.search(r'(?:anime_id|media_id|episode_id)\s*[:=]\s*["\']?(\d+)["\']?', text)
        if m:
            return m.group(1)

        raise AnikotoAPIError(f"Failed to extract 'data-id' attribute from watch page for slug '{slug}'")

    def resolve_from_titles(
        self,
        titles: List[str],
        year: Optional[int] = None,
        anime_type: Optional[str] = None,
        min_score: float = 50.0,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Resolves a list of anime title variants to an internal Anikoto numeric ID.
        Requires zero Jikan API calls — ideal for high-throughput app usage.
        """
        cleaned_titles = [t.strip() for t in titles if t and t.strip()]
        if not cleaned_titles:
            raise ResolveError("resolve_from_titles() called with empty titles list")

        cache_key = f"titles:{':'.join(sorted(cleaned_titles))}:{year}:{anime_type}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if debug:
            print(f"[AnikotoResolver DEBUG] Resolving titles={cleaned_titles}, year={year}, type={anime_type}", file=sys.stderr)

        candidates = search_anikoto_exhaustive(self.client, cleaned_titles)
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
            raise ResolveError(f"No confident match found for '{cleaned_titles[0]}' — best candidate was {best_desc} (min score required: {min_score})")

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
        """
        Resolves a MyAnimeList (MAL) numeric ID to an internal Anikoto ID.
        Fetches title variants from Jikan API, then calls resolve_from_titles().
        """
        cache_key = f"mal_id:{mal_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        mal_data = self.get_mal_titles(mal_id)
        if debug:
            print(f"[AnikotoResolver DEBUG] MAL ID {mal_id} metadata: titles={mal_data['titles']}, year={mal_data['year']}, type={mal_data['type']}", file=sys.stderr)

        result = self.resolve_from_titles(
            titles=mal_data["titles"],
            year=mal_data["year"],
            anime_type=mal_data["type"],
            min_score=min_score,
            debug=debug
        )

        self._cache[cache_key] = result
        return result


# Singleton instance for simple module-level function calls
_default_resolver = AnikotoResolver()

def resolve_from_titles(
    titles: List[str],
    year: Optional[int] = None,
    anime_type: Optional[str] = None,
    min_score: float = 50.0,
    debug: bool = False
) -> Dict[str, Any]:
    return _default_resolver.resolve_from_titles(titles, year=year, anime_type=anime_type, min_score=min_score, debug=debug)

def resolve(
    mal_id: int,
    min_score: float = 50.0,
    debug: bool = False
) -> Dict[str, Any]:
    return _default_resolver.resolve(mal_id, min_score=min_score, debug=debug)

"""
Exhaustive Multi-Query Search Module for Anikoto.cz (AJAX + Filter Page Dual Search)
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .client import HttpClient

SEARCH_URL = "https://anikoto.cz/ajax/anime/search"
FILTER_URL = "https://anikoto.cz/filter"


def generate_query_variants(titles: List[str]) -> List[str]:
    """
    Generates multiple query permutations (primary, english, base titles without subtitles,
    stripped season text) to guarantee search coverage against Anikoto's database.
    """
    variants: List[str] = []
    
    for title in titles:
        if not title:
            continue
        clean_t = title.strip()
        if clean_t and clean_t not in variants:
            variants.append(clean_t)

        # Base title before punctuation separators (':', '-', '—', '~', '(')
        for sep in [":", "-", "—", "~", "("]:
            if sep in clean_t:
                base = clean_t.split(sep)[0].strip()
                if len(base) >= 2 and base not in variants:
                    variants.append(base)

        # Strip season & part suffixes
        cleaned = re.sub(
            r'\b(?:Season|Part|Cour|\d+nd|\d+rd|\d+th|\d+st)\b.*$',
            '',
            clean_t,
            flags=re.IGNORECASE
        ).strip()
        if len(cleaned) >= 2 and cleaned not in variants:
            variants.append(cleaned)

    return list(dict.fromkeys(variants))


def search_anikoto_single_query(client: HttpClient, query: str) -> List[Dict[str, Any]]:
    """Performs a single AJAX search query against Anikoto.cz."""
    try:
        response = client.get(SEARCH_URL, params={"keyword": query})
        if response.status_code != 200:
            return []

        try:
            json_data = response.json()
        except Exception:
            return []

        html_content = json_data.get("result", {}).get("html", "")
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        results: List[Dict[str, Any]] = []

        for a_tag in soup.find_all("a", class_="item"):
            href = a_tag.get("href", "")
            if "/watch/" not in href:
                continue

            slug = href.split("/watch/")[-1].split("/")[0]
            name_div = a_tag.find("div", class_="name")
            title = name_div.text.strip() if name_div else slug

            year: Any = None
            type_: Any = None
            meta_div = a_tag.find("div", class_="meta")
            if meta_div:
                for span in meta_div.find_all("span", class_="dot"):
                    text = span.text.strip()
                    if text.isdigit() and len(text) == 4:
                        year = int(text)
                    elif text in {"TV", "Movie", "OVA", "ONA", "Special"}:
                        type_ = text

            results.append({
                "title": title,
                "slug": slug,
                "year": year,
                "type": type_,
                "query": query,
                "source": "ajax"
            })

        return results
    except Exception:
        return []


def search_anikoto_filter_query(client: HttpClient, query: str) -> List[Dict[str, Any]]:
    """Performs a search against Anikoto's full filter page (/filter?keyword=...) to fetch all results beyond AJAX limits."""
    try:
        response = client.get(FILTER_URL, params={"keyword": query})
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        list_items = soup.find("div", id="list-items")
        if not list_items:
            return []

        results: List[Dict[str, Any]] = []

        for div in list_items.find_all("div", class_="item"):
            a_tag = div.find("a", class_="d-title") or div.find("a", href=True)
            if not a_tag:
                continue

            href = a_tag.get("href", "")
            if "/watch/" not in href:
                continue

            slug = href.split("/watch/")[-1].split("/")[0]
            title = a_tag.text.strip()

            year: Any = None
            type_: Any = None
            meta_div = div.find("div", class_="meta")
            if meta_div:
                for m_item in meta_div.find_all("div", class_="m-item"):
                    lbl = m_item.find("label")
                    if lbl:
                        txt = lbl.text.strip()
                        if txt in {"TV", "Movie", "OVA", "ONA", "Special", "TV_SHORT"}:
                            type_ = txt

            m_year = re.search(r'\b(19\d\d|20\d\d)\b', div.text)
            if m_year:
                year = int(m_year.group(1))

            results.append({
                "title": title,
                "slug": slug,
                "year": year,
                "type": type_,
                "query": query,
                "source": "filter"
            })

        return results
    except Exception:
        return []


def search_anikoto_exhaustive(client: HttpClient, titles: List[str]) -> List[Dict[str, Any]]:
    """
    Runs multi-variant search queries across both AJAX suggestions and Full Filter Page results.
    """
    variants = generate_query_variants(titles)
    candidates_by_slug: Dict[str, Dict[str, Any]] = {}

    for query in variants:
        if not any(ord(char) < 128 for char in query):
            continue

        # 1. AJAX quick search
        for candidate in search_anikoto_single_query(client, query):
            slug = candidate["slug"]
            if slug not in candidates_by_slug:
                candidates_by_slug[slug] = candidate

        # 2. Filter page search (captures all results beyond top 5)
        for candidate in search_anikoto_filter_query(client, query):
            slug = candidate["slug"]
            if slug not in candidates_by_slug:
                candidates_by_slug[slug] = candidate

    return list(candidates_by_slug.values())

"""
Advanced Multi-Factor Scoring Engine for Anime Title Matching.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher

TYPE_ALIASES = {
    "TV_SHORT": "TV",
    "SPECIALS": "Special",
}


def normalize_title(title: str) -> str:
    """Normalize string for consistent fuzzy comparisons."""
    if not title:
        return ""
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def extract_season_info(title: str) -> str:
    """Extract normalized season or part indicator (s1, s2, p1, p2, etc.)."""
    if not title:
        return "s1"
    title_lower = title.lower()
    
    # Season X or S2
    m = re.search(r'\b(?:season|s)\s*(\d+)\b', title_lower)
    if m:
        return f"s{m.group(1)}"
    
    # 2nd Season / 3rd Season
    m = re.search(r'\b(\d+)(?:st|nd|rd|th)\s+season\b', title_lower)
    if m:
        return f"s{m.group(1)}"
        
    # Part 2 / Part II
    m = re.search(r'\bpart\s*(\d+)\b', title_lower)
    if m:
        return f"p{m.group(1)}"

    # Cour 2
    m = re.search(r'\bcour\s*(\d+)\b', title_lower)
    if m:
        return f"c{m.group(1)}"
        
    return "s1"


def similarity_score(title_a: str, title_b: str) -> float:
    """Calculate maximum similarity between two title strings using sequence & token set ratio."""
    norm_a = normalize_title(title_a)
    norm_b = normalize_title(title_b)
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0

    seq_ratio = SequenceMatcher(None, norm_a, norm_b).ratio()

    # Token set overlap ratio
    words_a = set(norm_a.split())
    words_b = set(norm_b.split())
    if words_a and words_b:
        intersection = words_a.intersection(words_b)
        token_ratio = len(intersection) / max(len(words_a), len(words_b))
    else:
        token_ratio = 0.0

    return max(seq_ratio, token_ratio)


def score_candidate(
    mal_titles: List[str],
    mal_year: Optional[int],
    mal_type: Optional[str],
    candidate: Dict[str, Any]
) -> float:
    """
    Evaluates a candidate search result against MAL metadata.
    Returns confidence score (0-200+).
    """
    best_title_score = 0.0
    matched_mal_season = "s1"
    
    for mal_title in mal_titles:
        s_score = similarity_score(mal_title, candidate["title"])
        if s_score > best_title_score:
            best_title_score = s_score
            matched_mal_season = extract_season_info(mal_title)

    cand_season = extract_season_info(candidate["title"])
    score = best_title_score * 100.0

    # Season matching / mismatch penalty
    if matched_mal_season and cand_season:
        if matched_mal_season == cand_season:
            score += 25.0
        else:
            score -= 35.0

    # Year match
    if mal_year and candidate.get("year"):
        cand_year = candidate["year"]
        if cand_year == mal_year:
            score += 25.0
        elif abs(cand_year - mal_year) <= 1:
            score += 10.0

    # Media Type match (TV, Movie, OVA, ONA, Special)
    norm_mal_type = TYPE_ALIASES.get(mal_type, mal_type) if mal_type else None
    if norm_mal_type and candidate.get("type"):
        if candidate["type"] == norm_mal_type:
            score += 15.0

    return max(0.0, score)

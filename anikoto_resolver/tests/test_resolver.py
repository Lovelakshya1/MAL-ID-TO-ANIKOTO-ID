"""
Unit Tests for Anikoto Resolver.
"""

import unittest
from anikoto_resolver.scorer import (
    normalize_title,
    extract_season_info,
    similarity_score,
    score_candidate
)
from anikoto_resolver.search import generate_query_variants
from anikoto_resolver import resolve_from_titles


class TestAnikotoResolver(unittest.TestCase):

    def test_normalize_title(self):
        self.assertEqual(normalize_title("Frieren: Beyond Journey's End!"), "frieren beyond journeys end")
        self.assertEqual(normalize_title("Jujutsu Kaisen (TV)"), "jujutsu kaisen tv")

    def test_extract_season_info(self):
        self.assertEqual(extract_season_info("Jujutsu Kaisen Season 2"), "s2")
        self.assertEqual(extract_season_info("Frieren 2nd Season"), "s2")
        self.assertEqual(extract_season_info("Attack on Titan Part 3"), "p3")
        self.assertEqual(extract_season_info("Chainsaw Man"), "s1")

    def test_similarity_score(self):
        self.assertEqual(similarity_score("Chainsaw Man", "Chainsaw Man"), 1.0)
        self.assertGreater(similarity_score("Fullmetal Alchemist: Brotherhood", "Fullmetal Alchemist Brotherhood"), 0.9)

    def test_query_variants(self):
        variants = generate_query_variants(["Frieren: Beyond Journey's End Season 2"])
        self.assertIn("Frieren: Beyond Journey's End Season 2", variants)
        self.assertIn("Frieren", variants)

    def test_score_candidate(self):
        mal_titles = ["Jujutsu Kaisen", "Jujutsu Kaisen (TV)"]
        cand_match = {"title": "Jujutsu Kaisen (TV)", "year": 2020, "type": "TV"}
        cand_wrong_season = {"title": "Jujutsu Kaisen 2nd Season", "year": 2023, "type": "TV"}

        score_good = score_candidate(mal_titles, 2020, "TV", cand_match)
        score_bad = score_candidate(mal_titles, 2020, "TV", cand_wrong_season)

        self.assertGreater(score_good, score_bad)

    def test_live_resolution(self):
        res = resolve_from_titles(["Chainsaw Man"], year=2022, anime_type="TV")
        self.assertEqual(res["internal_id"], "6805")
        self.assertEqual(res["slug"], "chainsaw-man-efeig")


if __name__ == "__main__":
    unittest.main()

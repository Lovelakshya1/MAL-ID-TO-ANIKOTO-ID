"""
Vercel Serverless Function Handler for Anikoto Resolver.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import json
from anikoto_resolver import resolve, resolve_from_titles, AnikotoError


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

        mal_id = params.get("id", [None])[0] or params.get("mal_id", [None])[0]
        titles = params.get("title", []) or params.get("titles", [])
        year = params.get("year", [None])[0]
        anime_type = params.get("type", [None])[0]
        
        try:
            min_score = float(params.get("min_score", [50.0])[0])
        except ValueError:
            min_score = 50.0

        try:
            if mal_id and mal_id.isdigit():
                result = resolve(int(mal_id), min_score=min_score)
            elif titles:
                result = resolve_from_titles(
                    titles=titles,
                    year=int(year) if (year and year.isdigit()) else None,
                    anime_type=anime_type,
                    min_score=min_score
                )
            else:
                result = {
                    "error": "Missing parameter. Usage: /api/resolve?id=44511 or /api/resolve?title=Chainsaw+Man",
                    "endpoints": {
                        "by_mal_id": "/api/resolve?id=44511",
                        "by_title": "/api/resolve?title=Chainsaw+Man&year=2022"
                    }
                }
        except AnikotoError as e:
            result = {"error": str(e)}
        except Exception as e:
            result = {"error": f"Internal Server Error: {str(e)}"}

        self.wfile.write(json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

"""
Command Line Interface (CLI) for Anikoto Resolver.
"""

import sys
import json
import argparse
from typing import List
from .core import AnikotoResolver
from .exceptions import AnikotoError

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main(argv: List[str] = None):
    parser = argparse.ArgumentParser(
        prog="anikoto-resolver",
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

    args = parser.parse_args(argv)
    resolver = AnikotoResolver()

    try:
        if args.titles:
            result = resolver.resolve_from_titles(
                titles=args.titles,
                year=args.year,
                anime_type=args.type,
                min_score=args.min_score,
                debug=args.debug
            )
        else:
            result = resolver.resolve(
                mal_id=args.mal_id,
                min_score=args.min_score,
                debug=args.debug
            )

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            # Clean output (ID only) suitable for stdout piping
            print(result["internal_id"])
            if args.debug:
                print(f"# slug='{result['slug']}' matched='{result['matched_title']}' score={result['score']}", file=sys.stderr)

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

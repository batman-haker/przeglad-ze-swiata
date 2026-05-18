"""
build.py — spina cały pipeline

Uruchomienie:
    python scripts/build.py                        # posts_raw.txt → events.json
    python scripts/build.py data/fetched_posts.txt # inny plik źródłowy
    python scripts/build.py --limit 20             # test: tylko pierwsze N fragmentów
    python scripts/build.py --force                # pomiń cache AI

Przebieg:
    1. parse.py    — plik źródłowy → data/fragments.json
    2. enrich.py   — fragmenty → data/events.json + site/events.json
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from parse import parse_posts, POSTS_FILE
from enrich import enrich_fragments, FRAGMENTS_FILE

import json


def main():
    # --- argumenty ---
    args   = sys.argv[1:]
    force  = "--force" in args
    limit  = None
    source = None

    clean_args = [a for a in args if a not in ("--force",)]
    i = 0
    while i < len(clean_args):
        arg = clean_args[i]
        if arg == "--limit" and i + 1 < len(clean_args):
            try: limit = int(clean_args[i + 1]); i += 1
            except ValueError: pass
        elif arg.startswith("--limit="):
            try: limit = int(arg.split("=", 1)[1])
            except ValueError: pass
        elif not arg.startswith("--"):
            source = arg
        i += 1

    src_path = Path(source) if source else POSTS_FILE

    print("=" * 60)
    print(f"TABLICA SWIAT — pipeline")
    print(f"Zrodlo: {src_path.name}")
    print("=" * 60)

    # --- krok 1: parse ---
    print("\n[1/2] Parsowanie postow...")
    fragments = parse_posts(str(src_path))
    print(f"  -> {len(fragments)} fragmentow")

    # Zapisz fragments.json (podgląd / debug)
    out = ROOT / "data" / "fragments.json"
    out.write_text(json.dumps(fragments, ensure_ascii=False, indent=2), encoding="utf-8")

    if not fragments:
        print("Brak fragmentow do przetworzenia. Koniec.")
        return

    # --- krok 2: enrich ---
    print("\n[2/2] Wzbogacanie przez AI...")
    events = enrich_fragments(fragments, force=force, limit=limit)

    print(f"\nPipeline zakończony. Wydarzen w bazie: {len(events)}")
    print(f"  data/events.json")
    print(f"  site/events.json")


if __name__ == "__main__":
    main()

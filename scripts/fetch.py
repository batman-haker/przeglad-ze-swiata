"""
fetch.py — pobiera tweety @GPW_Trader2022 przez twitterapi.io

Uruchomienie:
    python scripts/fetch.py            # nowe posty (od ostatnio zapisanego)
    python scripts/fetch.py --all      # cała historia (wiele stron)
    python scripts/fetch.py --pages 5  # maksymalnie N stron (5 * 20 = 100 tweetów)

Wynik:
    data/fetched_raw.json    — surowe odpowiedzi z API (archiwum)
    data/fetched_posts.txt   — gotowe posty w formacie posts_raw.txt (do ręcznej weryfikacji)

Workflow:
    1. Uruchom skrypt
    2. Sprawdź data/fetched_posts.txt
    3. Skopiuj wybrane posty do data/posts_raw.txt
    4. Posty subskrybentów dopisz ręcznie do osobnego pliku (np. data/posts_sub.txt)
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import urllib3
import requests
from dotenv import load_dotenv
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("TWITTERAPI_KEY")
USERNAME = "GPW_Trader2022"
BASE_URL = "https://api.twitterapi.io/twitter/user/last_tweets"

RAW_OUT = ROOT / "data" / "fetched_raw.json"
POSTS_OUT = ROOT / "data" / "fetched_posts.txt"


def fetch_page(cursor: str = "") -> dict:
    headers = {"X-API-Key": API_KEY}
    params = {
        "userName": USERNAME,
        "cursor": cursor,
        "includeReplies": "false",
    }
    resp = requests.get(BASE_URL, headers=headers, params=params, timeout=15, verify=False)
    resp.raise_for_status()
    raw = resp.json()
    # normalizuj: tweety mogą być w data.tweets lub bezpośrednio w tweets
    if "data" in raw and isinstance(raw["data"], dict):
        tweets = raw["data"].get("tweets", [])
        raw["tweets"] = tweets
    return raw


def parse_datetime(created_at: str) -> tuple[str, str]:
    """Zwraca (DATA: RRRR-MM-DD, GODZINA: GG:MM) z pola createdAt tweeta."""
    # twitterapi.io zwraca np. "Mon May 12 14:30:00 +0000 2025"
    try:
        dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
    except ValueError:
        # fallback: ISO 8601
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    # konwertuj na UTC (już powinno być)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")


def tweet_to_post_block(tweet: dict, index: int) -> str:
    """Formatuje tweet do bloku kompatybilnego z posts_raw.txt."""
    tid = tweet.get("id", "")
    url = tweet.get("url") or f"https://x.com/GPW_Trader2022/status/{tid}"
    created_at = tweet.get("createdAt", "")
    text = tweet.get("text", "").strip()

    if created_at:
        data, godzina = parse_datetime(created_at)
    else:
        data, godzina = "????-??-??", "??:??"

    return (
        f"=== POST ===\n"
        f"URL: {url}\n"
        f"DATA: {data}\n"
        f"GODZINA: {godzina}\n"
        f"\n"
        f"{text}\n"
    )


def load_known_ids() -> set:
    """Zbiera ID już zapisane w fetched_raw.json (żeby nie duplikować)."""
    if not RAW_OUT.exists():
        return set()
    with RAW_OUT.open(encoding="utf-8") as f:
        raw = json.load(f)
    return {t["id"] for t in raw if "id" in t}


def main():
    if not API_KEY:
        print("BŁĄD: brak TWITTERAPI_KEY w .env")
        sys.exit(1)

    fetch_all = "--all" in sys.argv
    max_pages = 99999 if fetch_all else 3  # domyślnie 3 strony = ~60 tweetów
    for arg in sys.argv[1:]:
        if arg.startswith("--pages"):
            try:
                max_pages = int(arg.split("=")[1]) if "=" in arg else int(sys.argv[sys.argv.index(arg) + 1])
            except (IndexError, ValueError):
                pass

    known_ids = load_known_ids()
    all_tweets: list[dict] = []
    cursor = ""
    page = 0
    new_count = 0
    stop_early = False

    print(f"Pobieranie tweetów @GPW_Trader2022 (maks. {max_pages} stron)...")

    while page < max_pages:
        page += 1
        print(f"  Strona {page}...", end=" ", flush=True)
        try:
            data = fetch_page(cursor)
        except requests.HTTPError as e:
            print(f"\nBŁĄD HTTP: {e}")
            break

        tweets = data.get("tweets", [])
        print(f"{len(tweets)} tweetów")

        for t in tweets:
            tid = t.get("id", "")
            if tid in known_ids:
                print(f"  → tweet {tid} już pobrany, zatrzymuję.")
                stop_early = True
                break
            all_tweets.append(t)
            new_count += 1

        if stop_early or not data.get("has_next_page"):
            break

        cursor = data.get("next_cursor", "")
        if not cursor:
            break

        time.sleep(0.3)  # grzecznościowy throttle

    if not all_tweets:
        print("Brak nowych tweetów.")
        return

    # dołącz do fetched_raw.json
    existing: list[dict] = []
    if RAW_OUT.exists():
        with RAW_OUT.open(encoding="utf-8") as f:
            existing = json.load(f)

    merged = all_tweets + existing  # nowe na początku
    RAW_OUT.parent.mkdir(exist_ok=True)
    with RAW_OUT.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    # zapisz fetched_posts.txt
    lines = [
        "# Pobrane automatycznie przez fetch.py\n"
        f"# {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
        "# Zweryfikuj i skopiuj wybrane posty do data/posts_raw.txt\n"
        "#\n"
    ]
    for i, tweet in enumerate(all_tweets, 1):
        lines.append(tweet_to_post_block(tweet, i))
        lines.append("")  # pusta linia między postami

    with POSTS_OUT.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nGotowe:")
    print(f"  Nowe tweety:        {new_count}")
    print(f"  data/fetched_raw.json   — {len(merged)} tweetów łącznie")
    print(f"  data/fetched_posts.txt  — gotowe do wklejenia do posts_raw.txt")


if __name__ == "__main__":
    main()

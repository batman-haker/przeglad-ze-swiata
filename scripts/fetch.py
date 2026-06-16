"""
fetch.py — pobiera tweety @GPW_Trader2022 przez twitterapi.io

Uruchomienie:
    python scripts/fetch.py            # nowe posty (ostatnie 4 dni)
    python scripts/fetch.py --all      # cała historia (wiele stron)
    python scripts/fetch.py --pages 5  # maksymalnie N stron (5 * 20 = 100 tweetów)

Wynik:
    data/fetched_raw.json    — surowe odpowiedzi z API (archiwum)
    data/fetched_posts.txt   — wszystkie posty z ostatnich 4 dni (wejście do build.py)
"""

import json
import sys
import time
from datetime import datetime, timezone, timedelta
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

LOOKBACK_DAYS = 8  # fetched_posts.txt zawiera tweety z ostatnich N dni
                   # (8 dni + 6 stron ponizej = krotkie przerwy nie robia luk w archiwum)


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
    if "data" in raw and isinstance(raw["data"], dict):
        tweets = raw["data"].get("tweets", [])
        raw["tweets"] = tweets
    return raw


def parse_datetime(created_at: str) -> datetime:
    try:
        return datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y").astimezone(timezone.utc)
    except ValueError:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone(timezone.utc)


def tweet_to_post_block(tweet: dict, index: int) -> str:
    tid = tweet.get("id", "")
    url = tweet.get("url") or f"https://x.com/GPW_Trader2022/status/{tid}"
    created_at = tweet.get("createdAt", "")
    text = tweet.get("text", "").strip()

    if created_at:
        dt = parse_datetime(created_at)
        data = dt.strftime("%Y-%m-%d")
        godzina = dt.strftime("%H:%M")
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
    max_pages = 99999 if fetch_all else 6
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
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

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

        too_old = False
        for t in tweets:
            tid = t.get("id", "")

            # Zatrzymaj gdy tweety są starsze niż cutoff
            try:
                dt = parse_datetime(t.get("createdAt", ""))
                if dt < cutoff:
                    too_old = True
                    break
            except Exception:
                pass

            if tid in known_ids:
                # Nie przerywaj — skrót info mógł być między już pobranymi tweetami
                continue

            all_tweets.append(t)
            new_count += 1

        if too_old or not data.get("has_next_page"):
            break

        cursor = data.get("next_cursor", "")
        if not cursor:
            break

        time.sleep(0.3)

    # Dołącz nowe tweety do archiwum
    existing: list[dict] = []
    if RAW_OUT.exists():
        with RAW_OUT.open(encoding="utf-8") as f:
            existing = json.load(f)

    merged = all_tweets + existing
    RAW_OUT.parent.mkdir(exist_ok=True)
    with RAW_OUT.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    # fetched_posts.txt: WSZYSTKIE tweety z ostatnich LOOKBACK_DAYS (z archiwum)
    # Dzięki temu build.py widzi wszystkie posty z ostatnich dni, nie tylko nowe
    recent: list[dict] = []
    for t in merged:
        try:
            dt = parse_datetime(t.get("createdAt", ""))
            if dt >= cutoff:
                recent.append(t)
        except Exception:
            pass

    recent.sort(key=lambda t: t.get("id", ""), reverse=True)

    lines = [
        "# Pobrane automatycznie przez fetch.py\n"
        f"# {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"# Tweety z ostatnich {LOOKBACK_DAYS} dni ({len(recent)} postów)\n"
        "#\n"
    ]
    for i, tweet in enumerate(recent, 1):
        lines.append(tweet_to_post_block(tweet, i))
        lines.append("")

    with POSTS_OUT.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    if new_count:
        print(f"\nGotowe:")
        print(f"  Nowe tweety:        {new_count}")
    else:
        print("  Brak nowych tweetów.")
    print(f"  data/fetched_raw.json   — {len(merged)} tweetów łącznie")
    print(f"  data/fetched_posts.txt  — {len(recent)} tweetów z ostatnich {LOOKBACK_DAYS} dni")


if __name__ == "__main__":
    main()

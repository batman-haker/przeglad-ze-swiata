"""
enrich.py — KROK 4: Warstwa AI

Rola: bierze surowe fragmenty z parse.py i wzbogaca je przez API.
Każdy fragment → kompletny obiekt wydarzenia zgodny z data/schema.json.

Obsługiwani dostawcy (wybierany automatycznie wg kluczy w .env):
  1. Anthropic Claude (ANTHROPIC_API_KEY)  — priorytet
  2. Google Gemini   (GEMINI_API_KEY)       — fallback

Uruchomienie:
    python scripts/enrich.py                  # przetwarza data/fragments.json
    python scripts/enrich.py --limit 10       # tylko pierwsze N (test)
    python scripts/enrich.py --force          # pomiń cache, przetwórz wszystko

Wynik:
    data/events.json + site/events.json

Cache: fragmenty już w events.json (wg post_url + fragment_nn) są pomijane.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

FRAGMENTS_FILE = ROOT / "data" / "fragments.json"
EVENTS_DATA    = ROOT / "data" / "events.json"
EVENTS_SITE    = ROOT / "site" / "events.json"

BATCH_SIZE = 10

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Jesteś redaktorem globalnej tablicy informacyjnej "Tablica Świat".
Otrzymasz listę surowych fragmentów newsów ze skrótów informacyjnych z profilu X @GPW_Trader2022.
Każdy fragment to jeden news — często skrócony, bez polskich znaków lub z literówkami.

Twoje zadanie: dla każdego fragmentu zwróć obiekt JSON z polami poniżej.
Odpowiedz WYŁĄCZNIE tablicą JSON — bez żadnych komentarzy, bez markdown, bez ```json.

POLA:

haslo (string, max 90 znaków)
  Czysty, poprawny nagłówek newsa. Popraw literówki, dodaj polskie znaki.
  Usuń emoji-flagi i zbędne symbole. Zostaw liczby i procenty.

rozwiniecie (string, 2-4 zdania)
  Rozwiń news o kontekst i tło. Wyjaśnij dlaczego to ważne.
  Pisz po polsku, w czasie teraźniejszym lub przeszłym.
  Jeśli to żart/ciekawostka — wystarczy jedno zdanie.

kategoria (JEDNA z sześciu):
  geopolityka  — konflikty, dyplomacja, bezpieczeństwo, polityka międzynarodowa
  gospodarka   — makroekonomia, handel, firmy, wyniki, inflacja, prawo pracy
  rynki        — giełdy, akcje, indeksy, surowce, waluty, kryptowaluty
  energia      — ropa, gaz, węgiel, OZE, ceny paliw, Ormuz, elektrownie
  technologia  — AI, kosmos, elektronika, cyberbezpieczeństwo, innowacje
  polska       — sprawy wyłącznie dotyczące Polski

waga:
  high    — wojny, ataki, decyzje banków centralnych, przełomowe umowy, katastrofy
  medium  — istotne dane ekonomiczne, ważne decyzje polityczne, znaczące ruchy firm
  low     — ciekawostki, statystyki, lokalne zdarzenia, humor

typ (JEDEN z siedmiu):
  deklaracja  — zapowiedź, obietnica, groźba, oświadczenie
  decyzja     — podjęta decyzja, ustawa, sankcja, zakaz, zezwolenie
  dane        — statystyki, wyniki, raporty, liczby
  konflikt    — atak, starcie, demonstracja, napięcie
  umowa       — porozumienie, kontrakt, współpraca, deal
  prognoza    — analiza, prognoza, ostrzeżenie, scenariusz
  wydarzenie  — fakt który się wydarzył, nie pasuje do innych

podmioty (array, max 6 pozycji)
  Kraje, firmy, osoby, organizacje. Format: "USA", "Iran", "Trump", "OPEC", "JSW".

region (string lub null)
  "Bliski Wschód", "Europa", "USA", "Azja", "Polska", "Afryka",
  "Ameryka Łacińska", "Globalnie". null jeśli niejednoznaczny.

watek (string lub null)
  "iran-2025"   — konflikt/napięcie wokół Iranu i Ormuz
  "jsw-shorts"  — JSW, shorty, koks, huty stali
  "ai-tech"     — AI, modele językowe, centra danych, chipy
  "spacex"      — SpaceX, rakiety, Musk, kosmos
  null          — brak pasującego wątku

ZASADY:
- Zwróć dokładnie tyle obiektów ile dostałeś (w tej samej kolejności).
- Pole "fragment_nn" przepisz bez zmian.
- Odpowiedz TYLKO czystą tablicą JSON: [ {...}, {...}, ... ]

Format każdego obiektu:
{"fragment_nn":<int>,"haslo":<str>,"rozwiniecie":<str>,"kategoria":<str>,\
"waga":<str>,"typ":<str>,"podmioty":[<str>],"region":<str|null>,"watek":<str|null>}
"""


# ---------------------------------------------------------------------------
# Adaptery API
# ---------------------------------------------------------------------------

class AnthropicAdapter:
    def __init__(self, api_key: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-haiku-4-5-20251001"

    def complete(self, user_message: str) -> str:
        import anthropic
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=[{"type": "text", "text": SYSTEM_PROMPT,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_message}],
        )
        return resp.content[0].text.strip()


class GeminiAdapter:
    """Używa Gemini REST API przez requests (omija SSL gRPC)."""
    def __init__(self, api_key: str):
        import urllib3
        import requests as req
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self._req = req
        self._key = api_key
        self._url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash:generateContent"
        )

    def complete(self, user_message: str) -> str:
        body = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": user_message}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
        }
        resp = self._req.post(
            self._url,
            params={"key": self._key},
            json=body,
            timeout=60,
            verify=False,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def get_provider():
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    gemini_key    = os.getenv("GEMINI_API_KEY", "")

    if anthropic_key and not anthropic_key.startswith("sk-ant-xxx"):
        print("Dostawca AI: Anthropic Claude (claude-haiku-4-5)")
        return AnthropicAdapter(anthropic_key)

    if gemini_key:
        print("Dostawca AI: Google Gemini (gemini-2.5-flash)")
        return GeminiAdapter(gemini_key)

    print("BŁĄD: brak klucza API. Ustaw ANTHROPIC_API_KEY lub GEMINI_API_KEY w .env")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Logika przetwarzania
# ---------------------------------------------------------------------------

def load_fragments(path: Path) -> list[dict]:
    if not path.exists():
        print(f"BŁĄD: Brak pliku {path}. Uruchom najpierw parse.py.")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def load_events(path: Path) -> list[dict]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def cache_key(frag: dict) -> str:
    return f"{frag['post_url']}#{frag['fragment_nn']}"


def make_id(frag: dict, global_nn: int) -> str:
    try:
        dt = datetime.fromisoformat(frag["datetime"])
    except ValueError:
        dt = datetime.now(timezone.utc)
    return f"{dt.strftime('%Y%m%d-%H%M')}-{global_nn:02d}"


def build_user_msg(batch: list[dict]) -> str:
    items = [
        {
            "fragment_nn": f["fragment_nn"],
            "raw_fragment": f["raw_fragment"],
            "haslo_raw": f.get("haslo_raw", f["raw_fragment"]),
            "zlozony": f.get("zlozony", False),
            "punkty": f.get("punkty"),
        }
        for f in batch
    ]
    return json.dumps(items, ensure_ascii=False, indent=2)


def parse_response(raw: str) -> list[dict]:
    """Parsuje odpowiedź API → lista dictów. Toleruje markdown wrapping."""
    text = raw
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    # znajdź tablicę JSON jeśli jest poprzedzona tekstem
    start = text.find("[")
    if start > 0:
        text = text[start:]
    return json.loads(text)


def merge(frag: dict, enriched: dict, global_nn: int) -> dict:
    return {
        "id":          make_id(frag, global_nn),
        "post_url":    frag["post_url"],
        "post_index":  frag["post_index"],
        "fragment_nn": frag["fragment_nn"],
        "datetime":    frag["datetime"],
        "kategoria":   enriched.get("kategoria", "geopolityka"),
        "watek":       enriched.get("watek"),
        "waga":        enriched.get("waga", "medium"),
        "haslo":       enriched.get("haslo", frag["raw_fragment"][:90]),
        "rozwiniecie": enriched.get("rozwiniecie", ""),
        "punkty":      frag.get("punkty"),
        "podmioty":    enriched.get("podmioty", []),
        "region":      enriched.get("region"),
        "typ":         enriched.get("typ", "wydarzenie"),
        "raw_fragment": frag["raw_fragment"],
    }


def save(events: list[dict]) -> None:
    events_sorted = sorted(events, key=lambda e: e["datetime"], reverse=True)
    payload = json.dumps(events_sorted, ensure_ascii=False, indent=2)
    EVENTS_DATA.write_text(payload, encoding="utf-8")
    EVENTS_SITE.write_text(payload, encoding="utf-8")


def enrich_fragments(fragments: list[dict], force: bool = False,
                     limit: int | None = None) -> list[dict]:
    provider = get_provider()

    existing   = load_events(EVENTS_DATA)
    cached     = {cache_key(e): e for e in existing} if not force else {}

    to_process = [f for f in fragments if cache_key(f) not in cached]
    if limit:
        to_process = to_process[:limit]

    skipped = len(fragments) - len(to_process) - (len(fragments) - len([f for f in fragments if cache_key(f) not in cached]))
    print(f"Fragmentow do przetworzenia: {len(to_process)}  (cache: {len(cached)})")

    if not to_process:
        print("Brak nowych fragmentow. Gotowe.")
        return existing

    new_events: list[dict] = []
    total = (len(to_process) + BATCH_SIZE - 1) // BATCH_SIZE
    global_nn = len(cached) + 1

    for b_start in range(0, len(to_process), BATCH_SIZE):
        batch   = to_process[b_start: b_start + BATCH_SIZE]
        b_num   = b_start // BATCH_SIZE + 1
        print(f"  Batch {b_num}/{total} ({len(batch)} fragmentow)...", end=" ", flush=True)

        try:
            raw     = provider.complete(build_user_msg(batch))
            results = parse_response(raw)
        except Exception as e:
            print(f"\n  BLAD: {e}")
            print(f"  Pomijam batch — fragmenty stracone.")
            continue

        if len(results) != len(batch):
            print(f"\n  UWAGA: oczekiwano {len(batch)}, dostano {len(results)}")

        for frag, enriched in zip(batch, results):
            new_events.append(merge(frag, enriched, global_nn))
            global_nn += 1

        print(f"OK")
        time.sleep(0.3)

    all_events = list(cached.values()) + new_events
    save(all_events)

    print(f"\nGotowe: {len(new_events)} nowych + {len(cached)} z cache = {len(all_events)} lacznie")
    print(f"  data/events.json")
    print(f"  site/events.json")
    return all_events


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    force = "--force" in sys.argv
    limit = None
    args  = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            try: limit = int(args[i + 1])
            except ValueError: pass
        elif arg.startswith("--limit="):
            try: limit = int(arg.split("=", 1)[1])
            except ValueError: pass

    fragments = load_fragments(FRAGMENTS_FILE)
    enrich_fragments(fragments, force=force, limit=limit)

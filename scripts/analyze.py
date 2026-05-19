"""
analyze.py — Analiza dzienna przez Gemini

Rola: bierze wszystkie wydarzenia danego dnia z events.json,
      wysyła je do Gemini z prośbą o syntezę i perspektywę,
      zapisuje wynik do data/analyses.json + site/analyses.json.

Cache: dni już przeanalizowane są pomijane (chyba że --force).
Analizuje domyślnie ostatnie 3 dni; --all żeby przetworzyć wszystkie.

Uruchomienie:
    python scripts/analyze.py           # ostatnie 3 dni (z cache)
    python scripts/analyze.py --all     # wszystkie dni
    python scripts/analyze.py --force   # wymuś ponowną analizę
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

EVENTS_FILE   = ROOT / "data" / "events.json"
ANALYSES_DATA = ROOT / "data" / "analyses.json"
ANALYSES_SITE = ROOT / "site" / "analyses.json"

MAX_DAYS_DEFAULT = 3


SYSTEM_PROMPT = """\
Jesteś analitykiem geopolitycznym i ekonomicznym najwyższej klasy.
Piszesz po polsku. Twoje analizy są rzeczowe, konkretne i głębokie.
Unikasz pustych fraz i ogólników. Piszesz jak ekspert dla ekspertów.
"""

USER_PROMPT_TEMPLATE = """\
Poniżej lista wydarzeń z {date_pl} zebrana ze skrótów informacyjnych.
Przeanalizuj je całościowo i napisz zwięzłą, ale głęboką syntezę w formacie JSON.

WYDARZENIA:
{events_text}

Odpowiedz WYŁĄCZNIE czystym JSON (bez markdown, bez ```):
{{
  "naglowek": "Jeden zdanie — główny temat/napięcie dnia (max 120 znaków)",
  "synteza": "3-5 zdań łączących wszystkie wątki w spójną całość. Co naprawdę się dzieje za kulisami? Jakie są ukryte powiązania między wydarzeniami?",
  "kontekst_globalny": "2-3 zdania — szerszy kontekst globalny. Jak te wydarzenia wpisują się w większe procesy geopolityczne/ekonomiczne?",
  "perspektywa": "2-3 zdania — co z tego wynika? Jakie scenariusze są możliwe w ciągu najbliższych dni/tygodni? Na co warto zwrócić uwagę?",
  "kluczowe_napięcia": ["Napięcie 1 (max 60 znaków)", "Napięcie 2", "Napięcie 3"]
}}
"""


class GeminiAdapter:
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

    def complete(self, system: str, user: str) -> str:
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 4096,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        resp = self._req.post(
            self._url,
            params={"key": self._key},
            json=body,
            timeout=90,
            verify=False,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


class AnthropicAdapter:
    def __init__(self, api_key: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-haiku-4-5-20251001"

    def complete(self, system: str, user: str) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text.strip()


def get_provider():
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    gemini_key    = os.getenv("GEMINI_API_KEY", "")
    if anthropic_key and not anthropic_key.startswith("sk-ant-xxx"):
        print("AI: Anthropic Claude")
        return AnthropicAdapter(anthropic_key)
    if gemini_key:
        print("AI: Google Gemini 2.5 Flash")
        return GeminiAdapter(gemini_key)
    print("BŁĄD: brak klucza API.")
    sys.exit(1)


def format_date_pl(iso_date: str) -> str:
    d = datetime.strptime(iso_date, "%Y-%m-%d")
    months = ["stycznia","lutego","marca","kwietnia","maja","czerwca",
              "lipca","sierpnia","września","października","listopada","grudnia"]
    weekdays = ["poniedziałek","wtorek","środa","czwartek","piątek","sobota","niedziela"]
    return f"{weekdays[d.weekday()]}, {d.day} {months[d.month-1]} {d.year}"


def events_to_text(events: list[dict]) -> str:
    lines = []
    for e in events:
        time = e["datetime"][11:16]
        waga = {"high": "🔴", "medium": "🟡", "low": "⚪"}.get(e.get("waga",""), "•")
        kat  = e.get("kategoria", "")
        haslo = e.get("haslo", "")
        rozw  = e.get("rozwiniecie", "")
        podmioty = ", ".join(e.get("podmioty", [])[:4])
        lines.append(f"{waga} [{time}] [{kat}] {haslo}")
        if rozw:
            lines.append(f"   → {rozw[:180]}")
        if podmioty:
            lines.append(f"   Podmioty: {podmioty}")
    return "\n".join(lines)


def parse_response(raw: str) -> dict:
    text = raw.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            if part.startswith("json"):
                text = part[4:].strip()
                break
            if "{" in part:
                text = part.strip()
                break
    start = text.find("{")
    if start > 0:
        text = text[start:]
    end = text.rfind("}") + 1
    if end > 0:
        text = text[:end]
    return json.loads(text)


def analyze_day(provider, date: str, events: list[dict]) -> dict:
    events_text = events_to_text(events)
    date_pl = format_date_pl(date)
    user_msg = USER_PROMPT_TEMPLATE.format(date_pl=date_pl, events_text=events_text)

    raw = provider.complete(SYSTEM_PROMPT, user_msg)
    parsed = parse_response(raw)

    return {
        "date":              date,
        "date_pl":           date_pl,
        "generated_at":      datetime.now(timezone.utc).isoformat(),
        "events_count":      len(events),
        "naglowek":          parsed.get("naglowek", ""),
        "synteza":           parsed.get("synteza", ""),
        "kontekst_globalny": parsed.get("kontekst_globalny", ""),
        "perspektywa":       parsed.get("perspektywa", ""),
        "kluczowe_napięcia": parsed.get("kluczowe_napięcia", []),
    }


def save(analyses: list[dict]) -> None:
    analyses_sorted = sorted(analyses, key=lambda a: a["date"], reverse=True)
    payload = json.dumps(analyses_sorted, ensure_ascii=False, indent=2)
    ANALYSES_DATA.write_text(payload, encoding="utf-8")
    ANALYSES_SITE.write_text(payload, encoding="utf-8")


def main():
    force   = "--force" in sys.argv
    do_all  = "--all"   in sys.argv

    events = json.loads(EVENTS_FILE.read_text(encoding="utf-8"))

    # Grupuj po dniach
    by_day: dict[str, list] = defaultdict(list)
    for e in events:
        day = e["datetime"][:10]
        by_day[day].append(e)

    days_sorted = sorted(by_day.keys(), reverse=True)

    if not do_all:
        days_sorted = days_sorted[:MAX_DAYS_DEFAULT]

    # Wczytaj istniejące analizy
    existing: dict[str, dict] = {}
    if ANALYSES_DATA.exists():
        for a in json.loads(ANALYSES_DATA.read_text(encoding="utf-8")):
            existing[a["date"]] = a

    to_process = [d for d in days_sorted if force or d not in existing]
    print(f"Dni do analizy: {len(to_process)}  (cache: {len(existing)})")

    if not to_process:
        print("Brak nowych dni. Gotowe.")
        return

    provider = get_provider()

    for day in to_process:
        evs = by_day[day]
        print(f"  Analizuję {day} ({len(evs)} wydarzeń)...", end=" ", flush=True)
        try:
            result = analyze_day(provider, day, evs)
            existing[day] = result
            print(f"OK — {result['naglowek'][:60]}")
        except Exception as ex:
            print(f"BŁĄD: {ex}")
        time.sleep(1)

    save(list(existing.values()))
    print(f"\nZapisano: {len(existing)} analiz")
    print(f"  data/analyses.json")
    print(f"  site/analyses.json")


if __name__ == "__main__":
    main()

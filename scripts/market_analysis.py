"""
market_analysis.py — Analiza rynkowa: newsy + dane cenowe → Gemini

Pobiera dane cenowe z Yahoo Finance (yfinance) za ostatnie 5 dni roboczych,
łączy z newsami z events.json (ostatnie 72h), wysyła do Gemini po analizę
trendów z perspektywy profesjonalnego tradera.

Wynik: data/market_analysis.json + site/market_analysis.json
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import yfinance as yf
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

EVENTS_FILE  = ROOT / "data" / "events.json"
OUT_DATA     = ROOT / "data" / "market_analysis.json"
OUT_SITE     = ROOT / "site" / "market_analysis.json"

GEMINI_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL   = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)

# ---------------------------------------------------------------------------
# Instrumenty do śledzenia
# ---------------------------------------------------------------------------

INSTRUMENTS = {
    # Indeksy
    "SPX":    {"ticker": "^GSPC",   "name": "S&P 500",    "group": "indeksy"},
    "NDX":    {"ticker": "^IXIC",   "name": "Nasdaq",     "group": "indeksy"},
    "DAX":    {"ticker": "^GDAXI",  "name": "DAX",        "group": "indeksy"},
    "WIG20":  {"ticker": "WIG20.WA","name": "WIG20",      "group": "indeksy"},
    # Surowce
    "GOLD":   {"ticker": "GC=F",    "name": "Złoto",      "group": "surowce"},
    "OIL":    {"ticker": "CL=F",    "name": "Ropa WTI",   "group": "surowce"},
    "SILVER": {"ticker": "SI=F",    "name": "Srebro",     "group": "surowce"},
    "COPPER": {"ticker": "HG=F",    "name": "Miedź",      "group": "surowce"},
    # Crypto
    "BTC":    {"ticker": "BTC-USD", "name": "Bitcoin",    "group": "crypto"},
    "ETH":    {"ticker": "ETH-USD", "name": "Ethereum",   "group": "crypto"},
    # Waluty
    "USDPLN": {"ticker": "USDPLN=X","name": "USD/PLN",   "group": "waluty"},
    "EURUSD": {"ticker": "EURUSD=X","name": "EUR/USD",   "group": "waluty"},
    # Spółki kluczowe
    "NVDA":   {"ticker": "NVDA",    "name": "Nvidia",     "group": "akcje"},
    "TSLA":   {"ticker": "TSLA",    "name": "Tesla",      "group": "akcje"},
    "MSFT":   {"ticker": "MSFT",    "name": "Microsoft",  "group": "akcje"},
    "KGHM":   {"ticker": "KGH.WA",  "name": "KGHM",       "group": "akcje"},
}

# ---------------------------------------------------------------------------
# Pobieranie danych
# ---------------------------------------------------------------------------

def fetch_market_data() -> dict:
    tickers = [v["ticker"] for v in INSTRUMENTS.values()]
    print(f"  Pobieranie danych dla {len(tickers)} instrumentów...")

    raw = yf.download(
        tickers,
        period="5d",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    close = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw

    result = {}
    ticker_to_key = {v["ticker"]: k for k, v in INSTRUMENTS.items()}

    for ticker, key in ticker_to_key.items():
        try:
            series = close[ticker].dropna()
            if len(series) < 2:
                continue
            price_now  = float(series.iloc[-1])
            price_1d   = float(series.iloc[-2])
            price_3d   = float(series.iloc[-4]) if len(series) >= 4 else float(series.iloc[0])
            price_5d   = float(series.iloc[0])

            def pct(a, b):
                return round((a - b) / b * 100, 2) if b else 0

            result[key] = {
                "name":      INSTRUMENTS[key]["name"],
                "group":     INSTRUMENTS[key]["group"],
                "price":     round(price_now, 4),
                "change_1d": pct(price_now, price_1d),
                "change_3d": pct(price_now, price_3d),
                "change_5d": pct(price_now, price_5d),
            }
        except Exception as e:
            print(f"  WARN {ticker}: {e}")

    print(f"  Pobrano dane dla {len(result)} instrumentów")
    return result


# ---------------------------------------------------------------------------
# Newsy z ostatnich 72h
# ---------------------------------------------------------------------------

def load_recent_events(hours: int = 72) -> list[dict]:
    if not EVENTS_FILE.exists():
        return []
    events = json.loads(EVENTS_FILE.read_text(encoding="utf-8"))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent = []
    for e in events:
        try:
            dt = datetime.fromisoformat(e["datetime"].replace("Z", "+00:00"))
            if dt >= cutoff:
                recent.append(e)
        except Exception:
            pass
    return recent


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Jesteś analitykiem rynkowym dla grupy profesjonalnych traderów.
Twoim zadaniem jest identyfikacja rzeczywistych trendów rynkowych — odcinasz szum,
skupiasz się na tym co ma znaczenie dla pozycji średnio- i krótkoterminowych.

Zasady:
- Pisz po polsku, zwięźle, konkretnie. Bez ogólników.
- Nie pisz tego co oczywiste ("rynki zareagowały na..."). Pisz CO z tego wynika.
- Szukaj nieoczekiwanych korelacji, anomalii, dywergencji.
- Jeśli ruch jest szumem — powiedz to wprost.
- Maksymalnie 600 słów w całej odpowiedzi.
- Odpowiedz TYLKO czystym JSON bez markdown, bez ```.
"""

def build_prompt(market: dict, events: list[dict]) -> str:
    # Grupuj dane rynkowe
    market_lines = []
    for group in ["indeksy", "surowce", "crypto", "waluty", "akcje"]:
        items = [(k, v) for k, v in market.items() if v["group"] == group]
        if not items:
            continue
        market_lines.append(f"\n{group.upper()}:")
        for k, v in items:
            market_lines.append(
                f"  {v['name']}: cena={v['price']}  "
                f"1D={v['change_1d']:+.2f}%  "
                f"3D={v['change_3d']:+.2f}%  "
                f"5D={v['change_5d']:+.2f}%"
            )

    # Newsy — tylko hasła, posortowane od najnowszego
    news_lines = []
    for e in sorted(events, key=lambda x: x["datetime"], reverse=True)[:40]:
        dt = e["datetime"][5:16].replace("T", " ")
        waga = {"high": "❗", "medium": "·", "low": "·"}.get(e.get("waga", ""), "·")
        news_lines.append(f"{waga} [{dt}] {e['haslo']}")

    payload = {
        "task": (
            "Przeanalizuj dane rynkowe z ostatnich 5 dni roboczych "
            "w kontekście newsów z ostatnich 72 godzin. "
            "Zidentyfikuj trendy, korelacje i sygnały istotne dla tradera."
        ),
        "market_data": "\n".join(market_lines),
        "news_72h": "\n".join(news_lines),
        "output_format": {
            "naglowek": "1 zdanie — najważniejszy wniosek z całości",
            "trendy": [
                "lista 3-5 trendów rynkowych, każdy jako konkretne zdanie z liczbami"
            ],
            "korelacje": [
                "lista 2-4 korelacji news↔rynek które są nieoczywiste lub zaskakujące"
            ],
            "uwaga": "1-2 zdania — co ignorować (szum), gdzie skupić uwagę",
            "sygnaly": [
                "lista 2-3 konkretnych obserwacji dla tradera (bez rekomendacji inwestycyjnych)"
            ]
        }
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def call_gemini(prompt: str) -> dict:
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096},
    }
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    resp = requests.post(
        GEMINI_URL,
        params={"key": GEMINI_KEY},
        json=body,
        timeout=60,
        verify=False,
    )
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    # Usuń ewentualne markdown wrapping
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:]
            p = p.strip()
            if p.startswith("{"):
                text = p
                break

    start = text.find("{")
    end   = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Spróbuj naprawić ucięty JSON
        import re
        # Usuń ostatni niekompletny klucz/wartość
        text = re.sub(r',\s*"[^"]*$', '', text)
        text = re.sub(r',\s*"[^"]*":\s*[^,}\]]*$', '', text)
        # Zamknij otwarte struktury
        open_brackets = text.count('[') - text.count(']')
        open_braces   = text.count('{') - text.count('}')
        text += ']' * open_brackets + '}' * open_braces
        return json.loads(text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not GEMINI_KEY:
        print("BŁĄD: brak GEMINI_API_KEY w .env")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    print(f"[market_analysis] Start: {now.strftime('%Y-%m-%d %H:%M UTC')}")

    print("  Krok 1: dane rynkowe...")
    market = fetch_market_data()
    if not market:
        print("  BŁĄD: brak danych rynkowych")
        sys.exit(1)

    print("  Krok 2: newsy z 72h...")
    events = load_recent_events(72)
    print(f"  Znaleziono {len(events)} newsów")

    print("  Krok 3: analiza Gemini...")
    prompt   = build_prompt(market, events)
    analysis = call_gemini(prompt)

    out = {
        "generated_at": now.isoformat(),
        "period_days":  5,
        "events_count": len(events),
        "market":       market,
        "analysis":     analysis,
    }

    payload = json.dumps(out, ensure_ascii=False, indent=2)
    OUT_DATA.write_text(payload, encoding="utf-8")
    OUT_SITE.write_text(payload, encoding="utf-8")
    print(f"  Zapisano: {OUT_SITE}")
    print(f"[market_analysis] Gotowe.")


if __name__ == "__main__":
    main()

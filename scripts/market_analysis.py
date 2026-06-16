"""
market_analysis.py — Analiza rynkowa: newsy + dane cenowe → Gemini

Pobiera dane cenowe z Yahoo Finance (yfinance) za ostatnie 5 dni roboczych,
łączy z newsami z events.json (ostatnie 72h), wysyła do Gemini po analizę
trendów z perspektywy profesjonalnego tradera.

Wynik: data/market_analysis.json + site/market_analysis.json
"""

import json
import os
import re
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

# Etap 2: sledzenie skutecznosci sygnalow
SIGNALS_LOG       = ROOT / "data" / "signals_log.json"
SIGNALS_LOG_SITE  = ROOT / "site" / "signals_log.json"
SCOREBOARD        = ROOT / "data" / "signals_scoreboard.json"
SCOREBOARD_SITE   = ROOT / "site" / "signals_scoreboard.json"
HORIZON_DAYS = 3     # dni roboczych do rozliczenia sygnalu
BAND_PCT     = 1.5   # +/- pasmo: ruch ponizej = "bez ruchu"

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
    "SPX":    {"ticker": "^GSPC",    "name": "S&P 500",          "group": "indeksy"},
    "NDX":    {"ticker": "^IXIC",    "name": "Nasdaq",           "group": "indeksy"},
    "WIG20":  {"ticker": "ETFBW20TR.WA", "name": "WIG20 (ETF)",  "group": "indeksy"},
    "VIX":    {"ticker": "^VIX",     "name": "VIX (zmienność)",  "group": "indeksy"},
    # Surowce
    "GOLD":   {"ticker": "GC=F",     "name": "Złoto",   "group": "surowce"},
    "SILVER": {"ticker": "SI=F",     "name": "Srebro",  "group": "surowce"},
    "OIL":    {"ticker": "CL=F",     "name": "Ropa WTI","group": "surowce"},
    # Crypto
    "BTC":    {"ticker": "BTC-USD",  "name": "Bitcoin", "group": "crypto"},
    "ETH":    {"ticker": "ETH-USD",  "name": "Ethereum","group": "crypto"},
    # Waluty
    "USDPLN": {"ticker": "USDPLN=X", "name": "USD/PLN", "group": "waluty"},
    # ETF-y
    "QQQ":    {"ticker": "QQQ",      "name": "QQQ (Nasdaq 100)",     "group": "etf"},
    "TQQQ":   {"ticker": "TQQQ",     "name": "TQQQ (3x Nasdaq)",     "group": "etf"},
    "TLT":    {"ticker": "TLT",      "name": "TLT (obligacje 20Y+)", "group": "etf"},
    "COPX":   {"ticker": "COPX",     "name": "COPX (górnicy miedzi)","group": "etf"},
    # Akcje
    "NVDA":   {"ticker": "NVDA",     "name": "Nvidia",        "group": "akcje"},
    "TSLA":   {"ticker": "TSLA",     "name": "Tesla",         "group": "akcje"},
    "AMD":    {"ticker": "AMD",      "name": "AMD",           "group": "akcje"},
    "AMZN":   {"ticker": "AMZN",     "name": "Amazon",        "group": "akcje"},
    "META":   {"ticker": "META",     "name": "Meta",          "group": "akcje"},
    "KGHM":   {"ticker": "KGH.WA",   "name": "KGHM",          "group": "akcje"},
    "XTB":    {"ticker": "XTB.WA",   "name": "XTB",           "group": "akcje"},
    "VST":    {"ticker": "VST",      "name": "Vistra",        "group": "akcje"},
    "TLN":    {"ticker": "TLN",      "name": "Talen Energy",  "group": "akcje"},
    "NVO":    {"ticker": "NVO",      "name": "Novo Nordisk",  "group": "akcje"},
    "AVAV":   {"ticker": "AVAV",     "name": "AeroVironment", "group": "akcje"},
    "MP":     {"ticker": "MP",       "name": "MP Materials",  "group": "akcje"},
    "NBIS":   {"ticker": "NBIS",     "name": "Nebius",        "group": "akcje"},
    "CEVA":   {"ticker": "CEVA",     "name": "Ceva",          "group": "akcje"},
    "VPG":    {"ticker": "VPG",      "name": "Vishay PG",     "group": "akcje"},
    "SPCX":   {"ticker": "SPCX",     "name": "SpaceX",        "group": "akcje"},
}

# ---------------------------------------------------------------------------
# Watchlista spolek — wykrywanie wzmianek w newsach (Etap 1)
#   klucz = symbol Yahoo Finance
#   ("Nazwa", [aliasy do dopasowania w podmiotach/hasle, lowercase])
#   Mapujemy tylko spolki PUBLICZNE (z realnym tickerem). OpenAI/Anthropic/
#   SpaceX/Shein pomijamy — prywatne, brak wyceny.
# ---------------------------------------------------------------------------

WATCHLIST = {
    "NVDA":    ("Nvidia",        ["nvidia"]),
    "TSLA":    ("Tesla",         ["tesla", "elon musk", "musk"]),
    "MSFT":    ("Microsoft",     ["microsoft"]),
    "META":    ("Meta",          ["meta", "facebook", "instagram", "whatsapp"]),
    "AAPL":    ("Apple",         ["apple", "iphone"]),
    "AMZN":    ("Amazon",        ["amazon", "aws"]),
    "GOOGL":   ("Alphabet",      ["google", "alphabet", "deepmind"]),
    "AVGO":    ("Broadcom",      ["broadcom"]),
    "AMD":     ("AMD",           ["amd"]),
    "PLTR":    ("Palantir",      ["palantir"]),
    "INTC":    ("Intel",         ["intel"]),
    "MU":      ("Micron",        ["micron"]),
    "COIN":    ("Coinbase",      ["coinbase"]),
    "MSTR":    ("MicroStrategy", ["microstrategy"]),
    "SPCX":    ("SpaceX",        ["spacex", "starlink"]),
    "NVO":     ("Novo Nordisk",  ["novo nordisk", "ozempic", "wegovy"]),
    "AVAV":    ("AeroVironment", ["aerovironment"]),
    "MP":      ("MP Materials",  ["mp materials", "metale ziem rzadkich", "ziem rzadkich"]),
    "NBIS":    ("Nebius",        ["nebius"]),
    "CEVA":    ("Ceva",          ["ceva"]),
    "VPG":     ("Vishay PG",     ["vishay"]),
    "VST":     ("Vistra",        ["vistra"]),
    "TLN":     ("Talen Energy",  ["talen"]),
    "XTB.WA":  ("XTB",           ["xtb"]),
    "KGH.WA":  ("KGHM",          ["kghm"]),
    "JSW.WA":  ("JSW",           ["jsw"]),
    "ZAB.WA":  ("Żabka",         ["żabka", "zabka"]),
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


def _changes_from_series(series) -> dict | None:
    """Z serii cen zamkniecia liczy cene + zmiany 1D/3D/5D."""
    series = series.dropna()
    if len(series) < 2:
        return None
    now = float(series.iloc[-1])
    d1  = float(series.iloc[-2])
    d3  = float(series.iloc[-4]) if len(series) >= 4 else float(series.iloc[0])
    d5  = float(series.iloc[0])
    pct = lambda a, b: round((a - b) / b * 100, 2) if b else 0
    return {
        "price":     round(now, 2),
        "change_1d": pct(now, d1),
        "change_3d": pct(now, d3),
        "change_5d": pct(now, d5),
    }


def fetch_spotlight(events: list[dict]) -> list[dict]:
    """Wykrywa spolki z WATCHLIST wzmiankowane w newsach z 72h, pobiera ich
    wyceny i zwraca liste: {ticker, name, ...zmiany, news:[hasla]}."""
    hits: dict[str, list[str]] = {}
    for e in events:
        text = " ".join(e.get("podmioty") or []) + " " + (e.get("haslo") or "")
        for ticker, (name, aliases) in WATCHLIST.items():
            if ticker in hits:
                # juz wykryta — dopisz news jesli pasuje
                pass
            for a in aliases:
                if re.search(r"\b" + re.escape(a) + r"\b", text, re.I):
                    hits.setdefault(ticker, [])
                    haslo = e.get("haslo") or ""
                    if haslo and haslo not in hits[ticker]:
                        hits[ticker].append(haslo)
                    break

    if not hits:
        print("  Spotlight: brak wzmianek spolek z watchlisty")
        return []

    print(f"  Spotlight: wykryto {len(hits)} spolek — pobieram wyceny...")
    spotlight = []
    for ticker, news in hits.items():
        name = WATCHLIST[ticker][0]
        try:
            hist = yf.Ticker(ticker).history(period="7d", interval="1d", auto_adjust=True)
            ch = _changes_from_series(hist["Close"]) if not hist.empty else None
            if not ch:
                print(f"  WARN spotlight {ticker}: brak danych cenowych")
                continue
            spotlight.append({"ticker": ticker, "name": name, **ch, "news": news[:4]})
        except Exception as e:
            print(f"  WARN spotlight {ticker}: {e}")

    print(f"  Spotlight: wyceny dla {len(spotlight)} spolek")
    return spotlight


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

def _pl_month_year(dt: datetime) -> str:
    """Zwraca aktualny miesiąc i rok po polsku, np. 'czerwiec 2026'."""
    miesiace = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
                "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień"]
    return f"{miesiace[dt.month - 1]} {dt.year}"


SYSTEM_PROMPT = """\
Jesteś analitykiem rynkowym dla grupy profesjonalnych traderów.

AKTUALNY KONTEKST (__CONTEXT_DATE__):
- Donald Trump jest OBECNYM prezydentem USA (od stycznia 2025)
- Wojna w Ukrainie trwa, napięcia USA-Iran wokół Cieśniny Ormuz
- Fed w cyklu utrzymywania stóp, inflacja w USA stopniowo spada

Twoim zadaniem jest identyfikacja rzeczywistych trendów rynkowych — odcinasz szum,
skupiasz się na tym co ma znaczenie dla pozycji średnio- i krótkoterminowych.

Zasady:
- Pisz po polsku, zwięźle, konkretnie. Bez ogólników.
- Nie pisz tego co oczywiste ("rynki zareagowały na..."). Pisz CO z tego wynika.
- Szukaj nieoczekiwanych korelacji, anomalii, dywergencji.
- Jeśli ruch jest szumem — powiedz to wprost.
- Maksymalnie 600 słów w całej odpowiedzi.
- Odpowiedz TYLKO czystym JSON bez markdown, bez ```.
""".replace("__CONTEXT_DATE__", _pl_month_year(datetime.now(timezone.utc)))

def build_prompt(market: dict, events: list[dict], spotlight: list[dict]) -> str:
    # Grupuj dane rynkowe
    market_lines = []
    for group in ["indeksy", "surowce", "crypto", "waluty", "etf", "akcje"]:
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

    # Spolki wykryte automatycznie w newsach (news -> ticker)
    spotlight_lines = []
    for s in spotlight:
        spotlight_lines.append(
            f"\n{s['name']} ({s['ticker']}): cena={s['price']}  "
            f"1D={s['change_1d']:+.2f}%  3D={s['change_3d']:+.2f}%  5D={s['change_5d']:+.2f}%"
        )
        for h in s["news"]:
            spotlight_lines.append(f"    • news: {h}")

    payload = {
        "task": (
            "Przeanalizuj dane rynkowe z ostatnich 5 dni roboczych "
            "w kontekście newsów z ostatnich 72 godzin. "
            "Zidentyfikuj trendy, korelacje i sygnały istotne dla tradera. "
            "Dla SPOLEK_WZMIANKOWANYCH powiąż KONKRETNY news z reakcją ceny spółki."
        ),
        "market_data": "\n".join(market_lines),
        "news_72h": "\n".join(news_lines),
        "spolki_wzmiankowane": "\n".join(spotlight_lines) or "(brak)",
        "output_format": {
            "naglowek": "1 zdanie — najważniejszy wniosek z całości",
            "trendy": [
                "lista 3-5 trendów rynkowych, każdy jako konkretne zdanie z liczbami"
            ],
            "korelacje": [
                "lista 2-4 korelacji news↔rynek które są nieoczywiste lub zaskakujące"
            ],
            "spolki": [
                {
                    "ticker": "symbol, np. NVDA",
                    "spolka": "nazwa spółki",
                    "ekspozycja": "pozytywna | negatywna | neutralna — wpływ newsa na spółkę",
                    "uzasadnienie": "1 zdanie: który news i dlaczego, z odniesieniem do ruchu ceny (1D/3D/5D). BEZ rekomendacji kup/sprzedaj."
                }
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
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
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
# Etap 2: sledzenie skutecznosci sygnalow
# ---------------------------------------------------------------------------

def _load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def _resolve_signal(e: dict) -> None:
    """Rozlicza otwarty sygnal jesli minelo >= HORIZON_DAYS dni roboczych."""
    try:
        hist = yf.Ticker(e["ticker"]).history(period="1mo", interval="1d", auto_adjust=True)
        if hist.empty:
            return
        closes = hist["Close"].dropna()
        after = [
            (idx.date().isoformat(), float(v))
            for idx, v in closes.items()
            if idx.date().isoformat() > e["date"]
        ]
        if len(after) < HORIZON_DAYS:
            return  # za malo sesji, czekamy
        eval_date, eval_price = after[HORIZON_DAYS - 1]
        base = e["price_at_signal"]
        ret = round((eval_price - base) / base * 100, 2) if base else 0.0

        exp = e["ekspozycja"]
        if exp == "pozytywna":
            outcome = "trafiony" if ret >= BAND_PCT else ("nietrafiony" if ret <= -BAND_PCT else "neutralny")
        elif exp == "negatywna":
            outcome = "trafiony" if ret <= -BAND_PCT else ("nietrafiony" if ret >= BAND_PCT else "neutralny")
        else:  # neutralna — trafiony jesli faktycznie bez ruchu
            outcome = "trafiony" if abs(ret) <= BAND_PCT else "nietrafiony"

        e.update(status="resolved", price_eval=round(eval_price, 2),
                 return_pct=ret, eval_date=eval_date, outcome=outcome)
    except Exception as ex:
        print(f"  WARN rozliczenie {e['ticker']}: {ex}")


def _build_scoreboard(log: list[dict], now: datetime) -> dict:
    judged = [e for e in log if e["status"] == "resolved" and e["outcome"] in ("trafiony", "nietrafiony")]

    def rate(items):
        n = len(items)
        h = sum(1 for e in items if e["outcome"] == "trafiony")
        return {"n": n, "trafione": h, "hit_rate": round(h / n * 100, 1) if n else None}

    by_exp = {exp: rate([e for e in judged if e["ekspozycja"] == exp])
              for exp in ("pozytywna", "negatywna", "neutralna")}

    return {
        "updated_at": now.isoformat(),
        "horizon_days": HORIZON_DAYS,
        "band_pct": BAND_PCT,
        "overall": rate(judged),
        "by_exposure": by_exp,
        "open_count": sum(1 for e in log if e["status"] == "open"),
        "resolved_count": sum(1 for e in log if e["status"] == "resolved"),
        "recent": sorted([e for e in log if e["status"] == "resolved"],
                         key=lambda e: e.get("eval_date") or "", reverse=True)[:15],
    }


def track_signals(spolki: list[dict], spotlight: list[dict], now: datetime) -> dict:
    """Zapisuje nowe sygnaly, rozlicza dojrzale, buduje tablice skutecznosci."""
    price_by_ticker = {s["ticker"]: s for s in spotlight}
    log = _load_json(SIGNALS_LOG, [])
    existing = {(e["date"], e["ticker"]) for e in log}
    today = now.date().isoformat()

    # 1. zapisz dzisiejsze sygnaly (1 na ticker/dzien)
    nowe = 0
    for sp in spolki:
        tk = sp.get("ticker")
        px = price_by_ticker.get(tk)
        if not tk or not px or (today, tk) in existing:
            continue
        log.append({
            "id": f"{today}-{tk}",
            "date": today,
            "ticker": tk,
            "spolka": sp.get("spolka") or px.get("name", tk),
            "ekspozycja": (sp.get("ekspozycja") or "neutralna").lower(),
            "price_at_signal": px["price"],
            "uzasadnienie": sp.get("uzasadnienie", ""),
            "status": "open",
            "price_eval": None, "return_pct": None, "outcome": None, "eval_date": None,
        })
        existing.add((today, tk))
        nowe += 1

    # 2. rozlicz otwarte sygnaly ktore dojrzaly
    for e in log:
        if e["status"] == "open":
            _resolve_signal(e)

    # 3. tablica skutecznosci
    scoreboard = _build_scoreboard(log, now)

    payload_log = json.dumps(log, ensure_ascii=False, indent=2)
    SIGNALS_LOG.write_text(payload_log, encoding="utf-8")
    SIGNALS_LOG_SITE.write_text(payload_log, encoding="utf-8")
    payload_sb = json.dumps(scoreboard, ensure_ascii=False, indent=2)
    SCOREBOARD.write_text(payload_sb, encoding="utf-8")
    SCOREBOARD_SITE.write_text(payload_sb, encoding="utf-8")

    ov = scoreboard["overall"]
    print(f"  Sygnaly: +{nowe} nowych, otwarte={scoreboard['open_count']}, "
          f"rozliczone={scoreboard['resolved_count']}, "
          f"trafnosc={ov['hit_rate']}% ({ov['trafione']}/{ov['n']})")
    return scoreboard


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

    print("  Krok 3: spolki wzmiankowane w newsach...")
    spotlight = fetch_spotlight(events)

    print("  Krok 4: analiza Gemini...")
    prompt   = build_prompt(market, events, spotlight)
    analysis = call_gemini(prompt)

    print("  Krok 5: sledzenie skutecznosci sygnalow...")
    track_signals(analysis.get("spolki", []), spotlight, now)

    out = {
        "generated_at": now.isoformat(),
        "period_days":  5,
        "events_count": len(events),
        "market":       market,
        "spotlight":    spotlight,
        "analysis":     analysis,
    }

    payload = json.dumps(out, ensure_ascii=False, indent=2)
    OUT_DATA.write_text(payload, encoding="utf-8")
    OUT_SITE.write_text(payload, encoding="utf-8")
    print(f"  Zapisano: {OUT_SITE}")
    print(f"[market_analysis] Gotowe.")


if __name__ == "__main__":
    main()

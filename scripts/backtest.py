"""
backtest.py — Nakładka newsów na historyczne wykresy cen (event study)

Bierze archiwum newsów (events.json) i dla kilku popularnych instrumentów
pobiera dzienną historię cen, oznacza dni z mocnymi (waga=high), tematycznie
pasującymi newsami i liczy średnią reakcję ceny +1D/+3D/+5D po takich dniach
względem baseline (wszystkie sesje).

UWAGA: to analiza OPISOWA (z perspektywy czasu), nie dowód predykcyjny.
Mała próbka (~5 tygodni), granularność dzienna, jedno źródło newsów.

Wynik: data/backtest.json + site/backtest.json
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
EVENTS_FILE = ROOT / "data" / "events.json"
OUT_DATA    = ROOT / "data" / "backtest.json"
OUT_SITE    = ROOT / "site" / "backtest.json"

PERIOD = "2mo"   # okno historii cen

# Instrument -> (ticker Yahoo, nazwa, kategorie istotne, slowa kluczowe w hasle)
INSTRUMENTS = {
    "SPX":   ("^GSPC",        "S&P 500", ["rynki", "gospodarka", "usa", "technologia"],
              ["s&p", "wall street", "fed", "giełd", "gield", "recesj", "inflac"]),
    "NDX":   ("^IXIC",        "Nasdaq",  ["technologia", "rynki"],
              ["nasdaq", "nvidia", "tesla", "microsoft", "apple", "amazon", "meta", "chip", "ai ", "sztucznej inteligenc"]),
    "WIG20": ("ETFBW20TR.WA", "WIG20",   ["polska", "gospodarka"],
              ["gpw", "wig", "polsk", "nbp", "kghm", "orlen", "pko", "pekao", "jsw", "żabka"]),
    "GOLD":  ("GC=F",         "Złoto",   ["geopolityka", "gospodarka"],
              ["złoto", "zloto", "inflac", "fed", "stóp", "stop proc", "bezpiecznej przystan"]),
    "OIL":   ("CL=F",         "Ropa WTI",["energia", "geopolityka"],
              ["ropa", "ormuz", "iran", "opec", "naft", "paliw", "baryłk", "barylk"]),
    "BTC":   ("BTC-USD",      "Bitcoin", ["rynki", "technologia"],
              ["bitcoin", "krypto", "crypto", "btc", "ethereum", "blockchain"]),
}


def load_events() -> list[dict]:
    if not EVENTS_FILE.exists():
        return []
    return json.loads(EVENTS_FILE.read_text(encoding="utf-8"))


def is_relevant(e: dict, kats: list[str], kws: list[str]) -> bool:
    if e.get("kategoria") in kats:
        return True
    haslo = (e.get("haslo") or "").lower()
    return any(kw in haslo for kw in kws)


def fetch_series(ticker: str):
    """Zwraca (dates[], close[]) z dziennej historii."""
    hist = yf.Ticker(ticker).history(period=PERIOD, interval="1d", auto_adjust=True)
    if hist.empty:
        return [], []
    closes = hist["Close"].dropna()
    dates = [idx.date().isoformat() for idx in closes.index]
    vals  = [round(float(v), 2) for v in closes.values]
    return dates, vals


def fwd_return(close: list[float], i: int, h: int):
    """Zwrot procentowy z indeksu i do i+h (None jesli poza zakresem)."""
    if i + h >= len(close) or close[i] == 0:
        return None
    return (close[i + h] - close[i]) / close[i] * 100.0


def avg(vals: list[float]):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def build_instrument(key: str, events: list[dict]) -> dict | None:
    ticker, name, kats, kws = INSTRUMENTS[key]
    dates, close = fetch_series(ticker)
    if len(dates) < 6:
        print(f"  WARN {key} ({ticker}): za malo danych cenowych")
        return None

    # mocne, pasujace newsy -> grupuj per dzien (kotwica = pierwsza sesja >= data newsa)
    rel = [e for e in events if e.get("waga") == "high" and is_relevant(e, kats, kws)]
    by_anchor: dict[int, list[str]] = {}
    for e in rel:
        nd = (e.get("datetime") or "")[:10]
        if not nd:
            continue
        anchor = next((i for i, d in enumerate(dates) if d >= nd), None)
        if anchor is None:
            continue
        by_anchor.setdefault(anchor, []).append(e.get("haslo") or "")

    markers = [
        {"i": i, "d": dates[i], "count": len(hasla), "hasla": hasla[:3]}
        for i, hasla in sorted(by_anchor.items())
    ]

    # event study: reakcja po dniach z newsem vs baseline
    news_idx = sorted(by_anchor.keys())
    all_idx  = list(range(len(close)))
    stats = {
        "news_days": len(news_idx),
        "after_news": {
            "r1": avg([fwd_return(close, i, 1) for i in news_idx]),
            "r3": avg([fwd_return(close, i, 3) for i in news_idx]),
            "r5": avg([fwd_return(close, i, 5) for i in news_idx]),
        },
        "baseline": {
            "r1": avg([fwd_return(close, i, 1) for i in all_idx]),
            "r3": avg([fwd_return(close, i, 3) for i in all_idx]),
            "r5": avg([fwd_return(close, i, 5) for i in all_idx]),
        },
    }

    return {
        "key": key, "name": name, "ticker": ticker,
        "dates": dates, "close": close,
        "markers": markers, "stats": stats,
    }


def main():
    now = datetime.now(timezone.utc)
    print(f"[backtest] Start: {now.strftime('%Y-%m-%d %H:%M UTC')}")
    events = load_events()
    print(f"  Newsow w archiwum: {len(events)}")

    out_instruments = []
    for key in INSTRUMENTS:
        inst = build_instrument(key, events)
        if inst:
            s = inst["stats"]
            print(f"  {key:6} {len(inst['dates'])} sesji, {s['news_days']} dni z newsem, "
                  f"po newsie 3D={s['after_news']['r3']}% vs baseline {s['baseline']['r3']}%")
            out_instruments.append(inst)

    if not out_instruments:
        print("  BŁĄD: brak danych dla zadnego instrumentu")
        sys.exit(1)

    out = {
        "generated_at": now.isoformat(),
        "period": PERIOD,
        "instruments": out_instruments,
    }
    payload = json.dumps(out, ensure_ascii=False, indent=2)
    OUT_DATA.write_text(payload, encoding="utf-8")
    OUT_SITE.write_text(payload, encoding="utf-8")
    print(f"  Zapisano: {OUT_SITE}")
    print("[backtest] Gotowe.")


if __name__ == "__main__":
    main()

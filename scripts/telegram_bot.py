"""
telegram_bot.py — Bot Telegram do przyjmowania newsów z telefonu

Uruchomienie:
    python3 scripts/telegram_bot.py

Komendy dla użytkownika:
    /id      — pokaż swoje Telegram ID (dodaj do .env jako TELEGRAM_ALLOWED_IDS)
    /status  — ile wydarzeń w bazie, kiedy ostatni news
    /help    — lista komend

Deduplicacja:
    Każdy fragment jest hashowany (sha256 pierwszych 80 znaków znormalizowanego tekstu).
    Hashe znanych fragmentów trzymamy w data/fragment_hashes.txt.
    Nowe fragmenty porównywane są z tym zbiorem — duplikaty pomijane PRZED wysłaniem do AI.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_RAW  = os.getenv("TELEGRAM_ALLOWED_IDS", "")
ALLOWED_IDS  = set(int(x) for x in ALLOWED_RAW.split(",") if x.strip().isdigit())

EVENTS_FILE  = ROOT / "data" / "events.json"
HASHES_FILE  = ROOT / "data" / "fragment_hashes.txt"
API_BASE     = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ── Telegram helpers ─────────────────────────────────────────────────────────

def tg(method: str, **kwargs) -> dict:
    try:
        r = requests.post(f"{API_BASE}/{method}", json=kwargs, timeout=15)
        return r.json()
    except Exception as e:
        print(f"[TG ERROR] {method}: {e}")
        return {}


def send(chat_id: int, text: str) -> None:
    tg("sendMessage", chat_id=chat_id, text=text)


# ── Hash cache (deduplicacja) ─────────────────────────────────────────────────

def normalize(text: str) -> str:
    """Usuwa emoji/znaki specjalne, normalizuje białe znaki, bierze pierwsze 80 znaków."""
    cleaned = "".join(
        c for c in text
        if unicodedata.category(c) not in ("So", "Mn", "Cc", "Cs")
    )
    return " ".join(cleaned.lower().split())[:80]


def frag_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode()).hexdigest()[:20]


def load_hashes() -> set[str]:
    hashes = set()
    if HASHES_FILE.exists():
        hashes.update(HASHES_FILE.read_text(encoding="utf-8").split())
    # Zbootstrapuj z istniejących wydarzeń (haslo jako przybliżenie)
    if EVENTS_FILE.exists():
        try:
            for e in json.loads(EVENTS_FILE.read_text(encoding="utf-8")):
                hashes.add(frag_hash(e.get("haslo", "")))
        except Exception:
            pass
    return hashes


def save_hashes(hashes: set[str]) -> None:
    HASHES_FILE.write_text("\n".join(sorted(hashes)), encoding="utf-8")


# ── Parsowanie wiadomości ─────────────────────────────────────────────────────

import re as _re
_HEADER_RE = _re.compile(
    r"skr[oó]t\s*info|kr[oó]tkie\s*info|info\s+nr\s*\d|skr[oó]t\s+nr\s*\d|"
    r"przegl[aą]d\s+.{0,10}[sś]wiat",
    _re.IGNORECASE,
)

def extract_lines(text: str) -> list[str]:
    """Wyciąga sensowne linie z wiadomości.
    Obsługuje dwa formaty:
      - każdy news na osobnej linii (z myślnikiem lub bez)
      - wszystko w jednej linii, newsy oddzielone ' -' lub ' – '
    Pomija linie nagłówkowe."""

    # Krok 1: podziel po newlinach
    raw_lines = text.strip().splitlines()

    # Krok 2: długie linie (>150 znaków) podziel też po ' -' w środku
    fragments = []
    for raw in raw_lines:
        raw = raw.strip()
        if not raw:
            continue
        if len(raw) > 150:
            # Dziel po ' -' lub ' –' gdzie zaczyna się nowy news
            parts = _re.split(r'\s+[-–]\s*', raw)
            fragments.extend(parts)
        else:
            fragments.append(raw)

    # Krok 3: wyczyść każdy fragment
    lines = []
    for frag in fragments:
        line = frag.strip()
        # Usuń prefiks myślnika/bullet
        for prefix in ("-", "•", "*", "·", "–", "—"):
            if line.startswith(prefix):
                line = line[len(prefix):].strip()
                break
        if len(line) <= 12:
            continue
        if _HEADER_RE.search(line):
            continue
        # Usuń linki na końcu (t.co, http...)
        line = _re.sub(r'\s+https?://\S+$', '', line).strip()
        if len(line) <= 12:
            continue
        lines.append(line)
    return lines


def build_post(lines: list[str]) -> str:
    """Buduje plik w formacie === POST === dla parse.py."""
    now = datetime.now(timezone.utc)
    uid = now.strftime("%Y%m%d_%H%M%S")
    return (
        f"=== POST ===\n"
        f"URL: https://t.me/tablicaswiata_bot/{uid}\n"
        f"DATA: {now.strftime('%Y-%m-%d')}\n"
        f"GODZINA: {now.strftime('%H:%M')}\n"
        f"\n"
        f"Skrót info ze świata\n"
        + "".join(f"-{line}\n" for line in lines)
    )


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_build(post_content: str) -> tuple[int, str]:
    """Uruchamia build.py, zwraca (liczba_nowych, pełny_output)."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", prefix="tg_", encoding="utf-8", delete=False
    ) as f:
        f.write(post_content)
        tmp = f.name
    try:
        result = subprocess.run(
            ["python3", str(ROOT / "scripts" / "build.py"), tmp],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
        )
        output = result.stdout + result.stderr
        new_count = 0
        for line in output.splitlines():
            if "nowych" in line and "=" in line:
                # "Gotowe: 5 nowych + 429 z cache = 434 łącznie"
                for part in line.split():
                    if part.isdigit():
                        new_count = int(part)
                        break
        return new_count, output
    finally:
        Path(tmp).unlink(missing_ok=True)


# ── Obsługa wiadomości ────────────────────────────────────────────────────────

def handle(msg: dict) -> None:
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    text    = msg.get("text", "").strip()

    if not text:
        return

    # Komendy otwarte (przed autoryzacją)
    if text == "/id":
        send(chat_id, f"Twoje Telegram ID: {user_id}\nDodaj je do .env jako TELEGRAM_ALLOWED_IDS={user_id}")
        return

    # Autoryzacja
    if ALLOWED_IDS and user_id not in ALLOWED_IDS:
        send(chat_id, f"⛔ Brak dostępu. Wyślij /id żeby sprawdzić swoje ID.")
        return

    if text == "/help":
        send(chat_id,
            "📋 Komendy:\n"
            "/id — Twoje Telegram ID\n"
            "/status — stan bazy\n"
            "/help — ta wiadomość\n\n"
            "Wyślij newsy jako listę z myślnikami:\n"
            "-Trump ogłasza nowe cła\n"
            "-USD/PLN rośnie do 4,20\n"
            "… i tak dalej."
        )
        return

    if text == "/status":
        if EVENTS_FILE.exists():
            evs = json.loads(EVENTS_FILE.read_text(encoding="utf-8"))
            n   = len(evs)
            latest = evs[0]["datetime"][:16].replace("T", " ") if evs else "—"
        else:
            n, latest = 0, "—"
        hashes = load_hashes()
        send(chat_id, f"📊 Wydarzeń w bazie: {n}\n🕒 Ostatnie: {latest}\n🔑 Znane fragmenty: {len(hashes)}")
        return

    # Przetwarzanie newsów
    lines = extract_lines(text)
    if not lines:
        send(chat_id, "⚠️ Nie znalazłem newsów do dodania. Wyślij listę z myślnikami.")
        return

    hashes   = load_hashes()
    new_lines, skipped = [], []

    for line in lines:
        h = frag_hash(line)
        if h in hashes:
            skipped.append(line[:55])
        else:
            new_lines.append(line)

    if not new_lines:
        reply = f"⏭️ Wszystkie {len(skipped)} fragmenty już są w bazie."
        if skipped:
            reply += "\n\nPominięte:\n" + "\n".join(f"• {s}" for s in skipped[:5])
        send(chat_id, reply)
        return

    send(chat_id, f"⏳ Przetwarzam {len(new_lines)} nowych fragmentów przez AI…")

    post_content = build_post(new_lines)
    new_count, raw_output = run_build(post_content)

    # Zapisz hashe nowo dodanych
    for line in new_lines:
        hashes.add(frag_hash(line))
    save_hashes(hashes)

    reply = f"✅ Dodano: {new_count} wydarzeń"
    if skipped:
        reply += f"\n⏭️ Duplikatów pominięto: {len(skipped)}"
    send(chat_id, reply)
    print(f"[BOT] user={user_id} nowe={new_count} skip={len(skipped)}")


# ── Główna pętla polling ──────────────────────────────────────────────────────

def main() -> None:
    if not BOT_TOKEN:
        print("BŁĄD: brak TELEGRAM_BOT_TOKEN w .env")
        sys.exit(1)

    print(f"[BOT] Start. Dozwolone ID: {ALLOWED_IDS or 'brak filtra — ustaw TELEGRAM_ALLOWED_IDS'}")

    # Wyczyść zalegające update'y ze startu
    tg("getUpdates", offset=-1)

    offset = None
    while True:
        try:
            data = requests.get(
                f"{API_BASE}/getUpdates",
                params={"timeout": 30, "offset": offset},
                timeout=40,
            ).json()

            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                if "message" in upd:
                    handle(upd["message"])

        except requests.exceptions.Timeout:
            pass  # normalne przy długim pollowaniu
        except Exception as e:
            print(f"[BOT ERROR] {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()

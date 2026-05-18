"""
email_fetch.py — odbiera emaile z przegladswiata@gmail.com,
przetwarza przez Gemini i dodaje do events.json.

Cron: 30 * * * * /opt/tablica-swiat/scripts/run_email.sh
"""

import imaplib
import email
import json
import os
import re
import sys
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from email.header import decode_header
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv

BASE_DIR    = Path(__file__).parent.parent
EVENTS_JSON = BASE_DIR / "data" / "events.json"
SITE_JSON   = BASE_DIR / "site" / "events.json"

load_dotenv(BASE_DIR / ".env")

IMAP_HOST   = "imap.gmail.com"
IMAP_PORT   = 993
GMAIL_USER  = os.getenv("GMAIL_USER", "przegladswiata@gmail.com")
GMAIL_PASS  = os.getenv("GMAIL_PASS", "")
GEMINI_KEY  = os.getenv("GEMINI_API_KEY", "")

ALLOWED_SENDERS = {
    "wiercinski.tomasz@gmail.com",
    "przegladswiata@gmail.com",
}

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

SYSTEM_PROMPT = """Jesteś analitykiem geopolitycznym. Wzbogacasz krótkie wiadomości informacyjne o metadane.
Dla każdego fragmentu zwróć JSON z polami:
- kategoria: geopolityka | gospodarka | rynki | energia | technologia | polska
- waga: high | medium | low
- typ: krótki opis typu zdarzenia (np. "decyzja polityczna", "wyniki finansowe", "konflikt zbrojny")
- podmioty: lista max 4 podmiotów (kraje, firmy, osoby) jako tablica stringów
- region: główny region geograficzny (np. "Iran", "USA", "Europa", "Polska")
- watek: iran-2025 | jsw-shorts | ai-tech | spacex | null
- haslo: zwięzły nagłówek po polsku (max 12 słów)
- rozwiniecie: rozszerzony opis po polsku (2-4 zdania)
- punkty: lista 2-4 kluczowych punktów jako tablica stringów (lub pusta tablica)

Odpowiedz TYLKO tablicą JSON, bez komentarzy."""

# ── Gmail ────────────────────────────────────────────────────

def decode_str(s):
    if not s:
        return ""
    parts = decode_header(s)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def extract_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                charset = part.get_content_charset() or "utf-8"
                body = part.get_payload(decode=True).decode(charset, errors="replace")
                break
    else:
        charset = msg.get_content_charset() or "utf-8"
        body = msg.get_payload(decode=True).decode(charset, errors="replace")

    lines = body.splitlines()
    clean = []
    for line in lines:
        if re.match(r"^--\s*$", line) or re.match(r"Sent from (my|iPhone|Android|Samsung)", line, re.I):
            break
        clean.append(line)
    return "\n".join(clean).strip()


def body_to_fragments(body, mail_date, mail_id):
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    dash_lines = [l for l in lines if l.startswith("-")]

    if len(dash_lines) >= 2:
        items = [l.lstrip("-").strip() for l in dash_lines if l.lstrip("-").strip()]
    else:
        items = [" ".join(lines)]

    fragments = []
    for nn, text in enumerate(items, start=1):
        fragments.append({
            "post_url":    f"email:{mail_id}",
            "post_index":  0,
            "fragment_nn": nn,
            "datetime":    mail_date,
            "raw_fragment": text,
            "haslo_raw":   text,
        })
    return fragments


def fetch_new_emails():
    print(f"Laczenie z Gmail ({GMAIL_USER})...")
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    try:
        mail.login(GMAIL_USER, GMAIL_PASS)
    except imaplib.IMAP4.error as e:
        print(f"BLAD logowania: {e}")
        print("Sprawdz haslo lub wygeneruj App Password w Google.")
        sys.exit(1)

    mail.select("INBOX")
    _, ids = mail.search(None, "UNSEEN")
    uid_list = ids[0].split()
    print(f"Nieprzeczytanych emaili: {len(uid_list)}")

    fragments = []
    for uid in uid_list:
        _, data = mail.fetch(uid, "(RFC822)")
        raw = data[0][1]
        msg = email.message_from_bytes(raw)

        sender = decode_str(msg.get("From", ""))
        m = re.search(r"[\w.+-]+@[\w.-]+", sender)
        addr = m.group(0).lower() if m else ""

        if addr not in ALLOWED_SENDERS:
            print(f"  Pomijam od: {addr}")
            mail.store(uid, "+FLAGS", "\\Seen")
            continue

        date_str = msg.get("Date", "")
        try:
            mail_date = parsedate_to_datetime(date_str).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            mail_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        body = extract_body(msg)
        if not body:
            mail.store(uid, "+FLAGS", "\\Seen")
            continue

        subject = decode_str(msg.get("Subject", ""))
        print(f"  Email: {subject[:50]} | {len(body)} znakow")

        frags = body_to_fragments(body, mail_date, uid.decode())
        fragments.extend(frags)
        mail.store(uid, "+FLAGS", "\\Seen")

    mail.logout()
    return fragments

# ── Gemini ───────────────────────────────────────────────────

def call_gemini(fragments):
    items = "\n".join(f"{i+1}. {f['raw_fragment']}" for i, f in enumerate(fragments))
    user_msg = f"Wzbogać następujące {len(fragments)} wiadomości:\n\n{items}"

    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": user_msg}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
    }
    resp = requests.post(GEMINI_URL, params={"key": GEMINI_KEY}, json=body, timeout=60, verify=False)
    resp.raise_for_status()
    raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        raise ValueError("Brak JSON w odpowiedzi Gemini")
    return json.loads(m.group(0))

# ── Zapis ────────────────────────────────────────────────────

def make_id(frag, nn):
    dt = datetime.fromisoformat(frag["datetime"])
    return f"{dt.strftime('%Y%m%d-%H%M')}-{nn:02d}"


def build_events(fragments, ai_results, offset):
    events = []
    for i, (frag, ai) in enumerate(zip(fragments, ai_results)):
        ev = {
            "id":          make_id(frag, offset + i + 1),
            "post_url":    frag["post_url"],
            "post_index":  frag["post_index"],
            "fragment_nn": frag["fragment_nn"],
            "datetime":    frag["datetime"],
            "kategoria":   ai.get("kategoria", "geopolityka"),
            "waga":        ai.get("waga", "medium"),
            "typ":         ai.get("typ", ""),
            "podmioty":    ai.get("podmioty", []),
            "region":      ai.get("region", ""),
            "watek":       ai.get("watek") or None,
            "haslo":       ai.get("haslo", frag["raw_fragment"][:80]),
            "rozwiniecie": ai.get("rozwiniecie", ""),
            "punkty":      ai.get("punkty", []),
            "raw_fragment": frag["raw_fragment"],
        }
        events.append(ev)
    return events


def load_existing():
    if EVENTS_JSON.exists():
        return json.loads(EVENTS_JSON.read_text(encoding="utf-8"))
    return []


def save_events(events):
    events_sorted = sorted(events, key=lambda e: e["datetime"], reverse=True)
    data = json.dumps(events_sorted, ensure_ascii=False, indent=2)
    EVENTS_JSON.write_text(data, encoding="utf-8")
    SITE_JSON.write_text(data, encoding="utf-8")
    print(f"Zapisano lacznie {len(events_sorted)} wydarzen.")

# ── Main ─────────────────────────────────────────────────────

def main():
    import urllib3
    urllib3.disable_warnings()

    fragments = fetch_new_emails()
    if not fragments:
        print("Brak nowych emaili.")
        return

    print(f"\nWzbogacanie {len(fragments)} fragmentow przez Gemini...")
    try:
        ai_results = call_gemini(fragments)
    except Exception as e:
        print(f"BLAD Gemini: {e}")
        sys.exit(1)

    existing = load_existing()
    new_events = build_events(fragments, ai_results, len(existing))

    print(f"Dodaje {len(new_events)} nowych wydarzen.")
    save_events(existing + new_events)


if __name__ == "__main__":
    main()

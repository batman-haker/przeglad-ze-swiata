"""
Naprawia podwójne kodowanie polskich znaków w events.json.

Uszkodzenie: bajty UTF-8 polskich liter były odczytywane jako mieszanka
ISO-8859-2 (pierwszy bajt) i Windows-1250/1252 (drugi bajt).

Przykłady:
  'ł' [C5 82] → 'Ĺ'+'‚'  → fix: iso-8859-2 + cp1252 → [C5 82] → 'ł'
  'ś' [C5 9B] → 'Ĺ'+'›'  → fix: iso-8859-2 + cp1252 → [C5 9B] → 'ś'
  'ź' [C5 BA] → 'Ĺ'+'ş'  → fix: iso-8859-2 + iso-8859-2 → [C5 BA] → 'ź'
  'ż' [C5 BC] → 'Ĺ'+'Ľ'  → fix: iso-8859-2 + cp1250 → [C5 BC] → 'ż'
  'ó' [C3 B3] → 'Ă'+'ł'  → fix: iso-8859-2 + iso-8859-2 → [C3 B3] → 'ó'
  'ę' [C4 99] → 'Ä'+'™'  → fix: iso-8859-2 + cp1252 → [C4 99] → 'ę'
  'ą' [C4 85] → 'Ä'+'…'  → fix: iso-8859-2 + cp1252 → [C4 85] → 'ą'

Bezpieczeństwo: akceptujemy TYLKO polskie znaki jako wynik naprawy.
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
FIELDS = ["haslo", "rozwiniecie", "raw_fragment", "haslo_raw", "region", "typ"]

POLISH_CHARS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")

# Znaki, które NIE są polskie, ale pojawiają się jako resztki błędnej korekcji
# ť (t z háčkem, słowacki/czeski) oraz ž (z s háčkem) w polskim tekście = ż
SINGLE_CHAR_FIXES = {
    'ť': 'ż',  # ť → ż
    'ž': 'ż',  # ž → ż
}

# kolejność prób: (codec_dla_pierwszego_bajtu, codec_dla_drugiego_bajtu)
CODEC_PAIRS = [
    ("iso-8859-2", "iso-8859-2"),
    ("iso-8859-2", "windows-1252"),
    ("iso-8859-2", "windows-1250"),
    ("windows-1252", "windows-1252"),
    ("windows-1252", "iso-8859-2"),
    ("latin-1", "latin-1"),
    ("latin-1", "windows-1252"),
]


def fix_pair(c1, c2):
    """Próbuje zdekodować parę znaków → wynik to znany polski znak lub None."""
    for codec1, codec2 in CODEC_PAIRS:
        try:
            b = c1.encode(codec1) + c2.encode(codec2)
            decoded = b.decode("utf-8")
            if len(decoded) == 1 and decoded in POLISH_CHARS:
                return decoded
        except Exception:
            pass
    return None


def fix(s):
    if not isinstance(s, str):
        return s

    chars = list(s)
    result = []
    i = 0
    changed = False

    while i < len(chars):
        c = chars[i]

        if ord(c) <= 0x7F:
            result.append(c)
            i += 1
            continue

        # Pojedynczy znak z listy znanych błędnych znaków
        if c in SINGLE_CHAR_FIXES:
            result.append(SINGLE_CHAR_FIXES[c])
            i += 1
            changed = True
            continue

        if i + 1 < len(chars) and ord(chars[i + 1]) > 0x7F:
            fixed = fix_pair(c, chars[i + 1])
            if fixed:
                result.append(fixed)
                i += 2
                changed = True
                continue

        result.append(c)
        i += 1

    return "".join(result) if changed else s


def fix_event(ev):
    for field in FIELDS:
        if field in ev:
            ev[field] = fix(ev[field])
    if ev.get("punkty"):
        ev["punkty"] = [fix(p) for p in ev["punkty"]]
    if ev.get("podmioty"):
        ev["podmioty"] = [fix(p) for p in ev["podmioty"]]
    return ev


with open(BASE / "data" / "events.json", "rb") as f:
    raw = f.read()

if raw.startswith(b"\xef\xbb\xbf"):
    raw = raw[3:]

data = json.loads(raw.decode("utf-8"))

fixed_count = 0
for ev in data:
    orig = json.dumps(ev, ensure_ascii=False)
    fix_event(ev)
    if json.dumps(ev, ensure_ascii=False) != orig:
        fixed_count += 1

out = json.dumps(data, ensure_ascii=False, indent=2)
(BASE / "data" / "events.json").write_text(out, encoding="utf-8")
(BASE / "site" / "events.json").write_text(out, encoding="utf-8")

print(f"Przetworzono: {len(data)} wydarzeń")
print(f"Naprawiono:   {fixed_count} wydarzeń")
print(f"Przykład 1:   {data[0]['haslo']}")
for ev in data:
    if "Vegas" in ev.get("haslo", ""):
        print(f"Las Vegas:    {ev['haslo']}")
        print(f"  rozw (80):  {ev['rozwiniecie'][:80]}")
        break

import json, re
from pathlib import Path

BASE = Path(__file__).parent.parent

EDITORIAL_RE = re.compile(
    r'(zobacz\s+skr[oó]t'
    r'|zapraszam\s+(do|na)'
    r'|skr[oó]t(y)?\s+(nocn|porann|wieczorn|nr\s*\d|numer\s*\d)'
    r'|nocne\s+numer'
    r'|poranne\s+numer'
    r'|wi[eę]cej\s+w\s+kolejn'
    r'|dzie[nń]\s+dobry.*skr[oó]t'
    r'|to\s+ju[zż]\s+wszystko)',
    re.IGNORECASE,
)

def is_editorial(ev):
    txt = ev.get("raw_fragment") or ev.get("haslo") or ""
    if EDITORIAL_RE.search(txt):
        return True
    if len(txt) < 35 and re.search(r"skr[oó]t", txt, re.IGNORECASE):
        return True
    return False

with open(BASE / "data" / "events.json", encoding="utf-8") as f:
    events = json.load(f)

before = len(events)
removed = [e for e in events if is_editorial(e)]
kept    = [e for e in events if not is_editorial(e)]

print(f"Przed:   {before}")
print(f"Usunieto: {len(removed)}")
for e in removed:
    print(f"  - {e['datetime'][:10]}  {(e.get('raw_fragment') or e.get('haslo',''))[:70]}")
print(f"Zostaje: {len(kept)}")

out = json.dumps(kept, ensure_ascii=False, indent=2)
(BASE / "data" / "events.json").write_text(out, encoding="utf-8")
(BASE / "site" / "events.json").write_text(out, encoding="utf-8")
print("Zapisano.")

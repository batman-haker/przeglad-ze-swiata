import json
from pathlib import Path

events = json.loads(Path("c:/tablica-swiat/tablica-swiat/data/events.json").read_text(encoding="utf-8"))
for e in events:
    print(f"ID:       {e['id']}")
    print(f"Haslo:    {e['haslo']}")
    print(f"Kat:      {e['kategoria']} / {e['waga']} / {e['typ']}")
    print(f"Region:   {e['region']}  |  Watek: {e['watek']}")
    print(f"Podmioty: {', '.join(e['podmioty'])}")
    print(f"Rozw:     {e['rozwiniecie'][:150]}")
    print(f"Raw:      {e['raw_fragment'][:80]}")
    print()

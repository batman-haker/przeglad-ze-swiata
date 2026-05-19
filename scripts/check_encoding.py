import json

data = json.load(open("/opt/tablica-swiat/data/events.json"))

POLISH_OK = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
bad = []
for ev in data:
    for f in ["haslo", "rozwiniecie"]:
        v = ev.get(f, "")
        suspicious = [c for c in v if 0x100 <= ord(c) <= 0x250 and c not in POLISH_OK]
        if suspicious:
            bad.append((ev["id"], f, "".join(suspicious[:5]), v[:60]))

print(f"Zepsute wpisy: {len(bad)}")
for b in bad[:10]:
    print(b)

# Count unique suspicious chars
all_suspicious = {}
for ev in data:
    for f in ["haslo", "rozwiniecie"]:
        for c in ev.get(f, ""):
            if 0x100 <= ord(c) <= 0x250 and c not in POLISH_OK:
                all_suspicious[c] = all_suspicious.get(c, 0) + 1

print(f"\nPodejrzane znaki (top 10):")
for c, n in sorted(all_suspicious.items(), key=lambda x: -x[1])[:10]:
    print(f"  U+{ord(c):04X} '{c}' x{n}")

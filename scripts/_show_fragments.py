import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
frags = json.loads((ROOT / "data" / "fragments.json").read_text(encoding="utf-8"))

per_post = defaultdict(list)
for f in frags:
    per_post[f["post_index"]].append(f)

for post_idx in sorted(per_post.keys()):
    items = per_post[post_idx]
    dt = items[0]["datetime"][:10]
    url = items[0]["post_url"]
    print(f"\n{'='*70}")
    print(f"POST {post_idx}  |  {dt}  |  {len(items)} fragmentow")
    print(f"{url}")
    print()
    for f in items:
        z = "  [ZLOZONY]" if f["zlozony"] else ""
        text = f["raw_fragment"].encode("ascii", "replace").decode()[:85]
        print(f"  {f['fragment_nn']:2d}. {text}{z}")
        if f["zlozony"] and f["punkty"]:
            for p in f["punkty"]:
                pp = p.encode("ascii", "replace").decode()[:70]
                print(f"       - {pp}")

"""
make_favicon.py — generuje favicon z logo przegladzeswiata.png

Kadruje logo do kwadratu (wycentrowany crop) i zapisuje:
  site/favicon.ico          — 16/32/48 px (klasyczna ikona karty przegladarki)
  site/apple-touch-icon.png — 180 px (iOS / zakladki ekranu glownego)

Uruchomienie (w katalogu z dostepnym Pillow):
    python3 scripts/make_favicon.py
"""

from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SRC = SITE / "przegladzeswiata.png"


def main() -> None:
    im = Image.open(SRC).convert("RGBA")
    w, h = im.size

    # Wycentrowany kwadratowy crop (bez znieksztalcen)
    s = min(w, h)
    left = (w - s) // 2
    top = (h - s) // 2
    sq = im.crop((left, top, left + s, top + s))

    # apple-touch-icon 180x180
    sq.resize((180, 180), Image.LANCZOS).save(SITE / "apple-touch-icon.png")

    # favicon.ico z trzema rozmiarami
    sq.save(SITE / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

    print("Zapisano:")
    print(f"  {SITE / 'favicon.ico'}")
    print(f"  {SITE / 'apple-touch-icon.png'}")


if __name__ == "__main__":
    main()

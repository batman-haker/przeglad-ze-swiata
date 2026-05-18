"""
parse.py — KROK 3: Parser strukturalny

Rola: czyta posts_raw.txt (lub fetched_posts.txt) i rozbija każdy
      "Skrót info ze Świata" na surowe fragmenty wydarzeń.
      NIE używa AI — czysta logika tekstowa.

Dwa obsługiwane formaty:
  Nowy (2026+): każdy news w osobnej linii zaczynającej się od '-'
  Stary (2025):  wszystkie newsy w jednej linii, separator '\\s+-\\s+'

Uruchomienie:
    python scripts/parse.py                  # data/posts_raw.txt
    python scripts/parse.py data/fetched_posts.txt  # inny plik
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_FILE = ROOT / "data" / "posts_raw.txt"

# Ogon: linia referująca poprzedni skrót
TAIL_REF = re.compile(
    r'poprzedni|skr[oó]t\s+(nr|z\s|w\s|informacji)',
    re.IGNORECASE,
)
URL_LINE = re.compile(r'^\s*https?://')

# Podpunkty a) b) c) ... i) — poprzedzone word-boundary
SUBPOINT_RE = re.compile(r'(?<!\w)([a-i])\)\s')


# ---------------------------------------------------------------------------
# 1. Czytanie pliku
# ---------------------------------------------------------------------------

def read_posts(path: Path) -> list[dict]:
    """Parsuje plik w formacie posts_raw.txt → lista postów z metadanymi."""
    text = path.read_text(encoding="utf-8")
    blocks = text.split("=== POST ===")
    posts = []

    for idx, block in enumerate(blocks[1:], 1):
        lines = [l for l in block.split('\n') if not l.strip().startswith('#')]

        meta: dict[str, str] = {}
        content_start: int | None = None

        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith('URL:'):
                meta['url'] = s[4:].strip()
            elif s.startswith('DATA:'):
                meta['date'] = s[5:].strip()
            elif s.startswith('GODZINA:'):
                meta['time'] = s[8:].strip()
            elif s == '' and 'url' in meta and content_start is None:
                content_start = i + 1
                break

        if not meta.get('url') or not meta.get('date') or content_start is None:
            continue

        content = '\n'.join(lines[content_start:]).strip()
        if not content:
            continue

        try:
            dt = datetime.strptime(
                f"{meta['date']} {meta.get('time', '00:00')}",
                "%Y-%m-%d %H:%M",
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        posts.append({
            'post_index': idx,
            'post_url': meta['url'],
            'datetime': dt.isoformat(),
            'content': content,
        })

    return posts


# ---------------------------------------------------------------------------
# 2. Filtrowanie i detekcja formatu
# ---------------------------------------------------------------------------

def is_skrot_info(content: str) -> bool:
    """True jeśli pierwsza linia to nagłówek 'Skrót info ze Świata'.
    Odrzuca RT (retweet) — są skrócone i nie zawierają pełnej treści."""
    first = content.strip().split('\n')[0]
    if first.strip().startswith('RT @'):
        return False
    return bool(re.search(r'skr[oó]t\s+info|skr[oó]t\s+informacji', first, re.IGNORECASE))


def detect_format(lines: list[str]) -> str:
    """'new' gdy >30% niepustych linii zaczyna się od '-', inaczej 'old'."""
    non_empty = [l for l in lines if l.strip()]
    if not non_empty:
        return 'new'
    dash = sum(1 for l in non_empty if l.strip().startswith('-'))
    return 'new' if dash / len(non_empty) > 0.3 else 'old'


# ---------------------------------------------------------------------------
# 3. Czyszczenie ogona
# ---------------------------------------------------------------------------

def strip_tail(lines: list[str]) -> list[str]:
    """Usuwa z dołu: puste linie, URL-e i referencje do poprzednich skrótów."""
    result = list(lines)
    changed = True
    while changed and result:
        changed = False
        last = result[-1].strip()
        if not last or URL_LINE.match(last) or TAIL_REF.search(last):
            result.pop()
            changed = True
    return result


# ---------------------------------------------------------------------------
# 4. Rozbicie na fragmenty
# ---------------------------------------------------------------------------

def split_new_format(lines: list[str]) -> list[str]:
    """Nowy format: separator = nowa linia zaczynająca się od '-'.
    Linie bez '-' na początku są kontynuacją poprzedniego fragmentu."""
    result: list[str] = []
    current: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith('-'):
            if current:
                result.append(' '.join(current))
            current = [s.lstrip('-').strip()]
        else:
            if current:
                current.append(s)
    if current:
        result.append(' '.join(current))
    return [f for f in result if f]


def split_old_format(text: str) -> list[str]:
    """Stary format: separator \\s+-\\s+ w jednej długiej linii."""
    parts = re.split(r'\s+-\s+', text)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# 5. Podpunkty
# ---------------------------------------------------------------------------

def extract_subpoints(text: str) -> tuple[str, list[str] | None]:
    """Wykrywa sekwencję a) b) c)...
    Zwraca (baza_hasła, lista_podpunktów) lub (text, None)."""
    matches = list(SUBPOINT_RE.finditer(text))
    if len(matches) < 2:
        return text, None
    base = text[:matches[0].start()].strip()
    punkty = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        punkty.append(text[m.start():end].strip())
    return base, punkty


# ---------------------------------------------------------------------------
# 6. Parsowanie treści jednego posta
# ---------------------------------------------------------------------------

def parse_content(content: str, post_meta: dict) -> list[dict]:
    """Główna logika: treść posta → lista fragmentów."""
    lines = content.split('\n')
    fmt = detect_format(lines)

    if fmt == 'new':
        body = strip_tail(lines[1:])   # linia 0 = nagłówek, pomijamy
        raw_fragments = split_new_format(body)
    else:
        one_line = ' '.join(l.strip() for l in lines if l.strip())
        parts = split_old_format(one_line)
        if not parts:
            return []
        parts = parts[1:]              # pierwszy fragment = nagłówek, pomijamy
        while parts and (TAIL_REF.search(parts[-1]) or URL_LINE.match(parts[-1])):
            parts.pop()
        raw_fragments = parts

    fragments = []
    for nn, frag in enumerate(raw_fragments, 1):
        base, punkty = extract_subpoints(frag)
        fragments.append({
            **post_meta,
            'raw_fragment': frag,
            'haslo_raw': base,
            'punkty': punkty,
            'zlozony': punkty is not None,
            'fragment_nn': nn,
        })
    return fragments


# ---------------------------------------------------------------------------
# 7. Publiczny interfejs
# ---------------------------------------------------------------------------

def parse_posts(path: str | None = None) -> list[dict]:
    """Zwraca listę surowych fragmentów gotowych do przekazania do enrich.py."""
    file_path = Path(path) if path else POSTS_FILE
    posts = read_posts(file_path)
    all_fragments = []
    for post in posts:
        if not is_skrot_info(post['content']):
            continue
        meta = {k: v for k, v in post.items() if k != 'content'}
        all_fragments.extend(parse_content(post['content'], meta))
    return all_fragments


# ---------------------------------------------------------------------------
# 8. Uruchomienie bezpośrednie — wypisuje bezpiecznik i zapisuje fragments.json
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else None
    fragments = parse_posts(source)

    per_post: dict = defaultdict(list)
    for f in fragments:
        per_post[(f['post_index'], f['post_url'])].append(f)

    print(f"\n{'='*60}")
    print("BEZPIECZNIK — licznik fragmentów per post:")
    for (idx, url), frags in sorted(per_post.items()):
        flag = "  <!> PODEJRZANIE MALO" if len(frags) < 5 else ""
        print(f"  Post {idx:2d}: {len(frags):3d} fragmentów{flag}")
        print(f"          {url[:80]}")

    print(f"\nLacznie: {len(fragments)} fragmentow z {len(per_post)} postow")

    if fragments:
        print(f"\n{'='*60}")
        print("Pierwsze 5 fragmentow (przyklad):")
        for f in fragments[:5]:
            tag = f"[{f['post_index']}-{f['fragment_nn']:02d}]"
            snippet = f['raw_fragment'][:110].encode('ascii', 'replace').decode()
            print(f"\n  {tag} {snippet}")
            if f['zlozony']:
                print(f"         -> ZLOZONY, {len(f['punkty'])} podpunktow")

    out = ROOT / "data" / "fragments.json"
    out.write_text(json.dumps(fragments, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano: {out}")

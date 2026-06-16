"""
archive_guard.py — chroni archiwum newsow przed utrata przy re-clone deploy.

Backup zyje POZA katalogiem repo (domyslnie /opt/tablica-backup), wiec
przezywa nawet pelne nadpisanie /opt/tablica-swiat swiezym git clone.

Tryby:
    python scripts/archive_guard.py restore
        Jesli backup ma WIECEJ rekordow niz biezacy plik (np. po deployu,
        ktory cofnal events.json do starej wersji z gita) — przywraca backup.
    python scripts/archive_guard.py backup
        Kopiuje archiwum do katalogu backupu + dzienny snapshot, rotacja 30 dni.

Sciezka backupu: env ARCHIVE_BACKUP_DIR (domyslnie /opt/tablica-backup).
"""

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = Path(os.getenv("ARCHIVE_BACKUP_DIR", "/opt/tablica-backup"))

# klucz w backupie -> sciezka zrodlowa w repo (data/)
FILES = {
    "events":      ROOT / "data" / "events.json",
    "signals_log": ROOT / "data" / "signals_log.json",
}
# pliki, ktore maja tez kopie serwowana w site/
SITE_MIRROR = {
    "events": ROOT / "site" / "events.json",
}


def count(path: Path) -> int:
    """Liczba rekordow w pliku JSON (lista). -1 gdy brak/blad."""
    try:
        return len(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return -1


def restore() -> None:
    for key, path in FILES.items():
        bak = BACKUP_DIR / f"{key}_latest.json"
        if not bak.exists():
            continue
        nb, nc = count(bak), count(path)
        if nb > nc:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(bak, path)
            if key in SITE_MIRROR:
                SITE_MIRROR[key].parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(bak, SITE_MIRROR[key])
            print(f"  [restore] {key}: przywrocono z backupu {nb} rekordow (bylo {max(nc, 0)})")


def backup() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now().strftime("%Y%m%d")
    saved = []
    for key, path in FILES.items():
        if not path.exists():
            continue
        shutil.copy(path, BACKUP_DIR / f"{key}_latest.json")
        if key == "events":
            shutil.copy(path, BACKUP_DIR / f"events_{day}.json")
        saved.append(f"{key}={count(path)}")
    # rotacja: trzymaj 30 najnowszych dziennych snapshotow events
    snaps = sorted(BACKUP_DIR.glob("events_2*.json"), reverse=True)
    for old in snaps[30:]:
        old.unlink()
    print(f"  [backup] {BACKUP_DIR}: {', '.join(saved) or 'brak plikow'}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "backup"
    if mode == "restore":
        restore()
    else:
        backup()

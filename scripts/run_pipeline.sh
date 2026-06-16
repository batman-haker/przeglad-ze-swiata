#!/bin/bash
# ============================================================
#  Tablica Swiat — pipeline (Linux / mikr.us)
#  Cron: 0 12,22 * * * /opt/tablica-swiat/scripts/run_pipeline.sh
# ============================================================

set -euo pipefail

PROJECT="/opt/tablica-swiat"
LOG_DIR="$PROJECT/logs"
LOG_FILE="$LOG_DIR/pipeline_$(date +%Y%m%d_%H%M).log"

mkdir -p "$LOG_DIR"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a "$LOG_FILE"; }

log "=== START PIPELINE ==="

cd "$PROJECT"

# Aktywuj virtualenv jesli istnieje
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# 0. Auto-restore archiwum z backupu jesli biezacy plik jest ubozszy
#    (np. po re-clone deploy, ktory cofnal events.json). Niekrytyczne.
log "Krok 0: archive_guard restore"
python3 scripts/archive_guard.py restore >> "$LOG_FILE" 2>&1 || log "  UWAGA: restore nieudany"

# 1. Pobierz nowe posty
log "Krok 1: fetch.py"
python3 scripts/fetch.py >> "$LOG_FILE" 2>&1

# 2. Wzbogac przez AI, zapisz events.json
log "Krok 2: build.py"
python3 scripts/build.py data/fetched_posts.txt >> "$LOG_FILE" 2>&1

# 3. Analiza rynkowa (newsy + ceny -> AI). Niekrytyczna: blad NIE przerywa pipeline.
log "Krok 3: market_analysis.py"
if python3 scripts/market_analysis.py >> "$LOG_FILE" 2>&1; then
    log "  market_analysis OK"
else
    log "  UWAGA: market_analysis.py nieudane (pomijam, newsy bez zmian)"
fi

# 4. Backtest (newsy nalozone na historyczne ceny). Niekrytyczny.
log "Krok 4: backtest.py"
if python3 scripts/backtest.py >> "$LOG_FILE" 2>&1; then
    log "  backtest OK"
else
    log "  UWAGA: backtest.py nieudane (pomijam)"
fi

# 5. Backup archiwum poza katalog repo (przezywa re-clone deploy). Niekrytyczny.
log "Krok 5: archive_guard backup"
python3 scripts/archive_guard.py backup >> "$LOG_FILE" 2>&1 || log "  UWAGA: backup nieudany"

log "=== PIPELINE ZAKONCZONY ==="

# Usun logi starsze niz 14 dni
find "$LOG_DIR" -name "pipeline_*.log" -mtime +14 -delete

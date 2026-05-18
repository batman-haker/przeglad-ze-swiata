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

# 1. Pobierz nowe posty
log "Krok 1: fetch.py"
python3 scripts/fetch.py >> "$LOG_FILE" 2>&1

# 2. Wzbogac przez AI, zapisz events.json
log "Krok 2: build.py"
python3 scripts/build.py data/fetched_posts.txt >> "$LOG_FILE" 2>&1

log "=== PIPELINE ZAKONCZONY ==="

# Usun logi starsze niz 14 dni
find "$LOG_DIR" -name "pipeline_*.log" -mtime +14 -delete

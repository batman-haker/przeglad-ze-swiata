#!/bin/bash
# Cron: */30 * * * * /opt/tablica-swiat/scripts/run_email.sh

PROJECT="/opt/tablica-swiat"
cd "$PROJECT"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

python3 scripts/email_fetch.py >> logs/email.log 2>&1

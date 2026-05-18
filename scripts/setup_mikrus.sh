#!/bin/bash
# ============================================================
#  Jednorazowy setup na mikr.us
#  Uruchom jako root: bash setup_mikrus.sh
# ============================================================

set -euo pipefail

PROJECT="/opt/tablica-swiat"
SITE="$PROJECT/site"
DOMAIN=""   # zostaw puste dla IP, lub wpisz np. tablica.mikr.us

echo "=== Setup: Tablica Swiat na mikr.us ==="

# ---- Zaleznosci systemowe ----
apt-get update -q
apt-get install -y python3 python3-pip python3-venv nginx curl

# ---- Kopiowanie projektu (jesli nie istnieje) ----
if [ ! -d "$PROJECT" ]; then
    echo "BLAD: Najpierw wgraj projekt do $PROJECT"
    echo "  np. scp -r tablica-swiat/ root@<IP>:/opt/tablica-swiat"
    exit 1
fi

# ---- Python virtualenv + pakiety ----
echo "Instalacja pakietow Python..."
cd "$PROJECT"
python3 -m venv .venv
source .venv/bin/activate
pip install --quiet requests python-dotenv

# ---- Uprawnienia do skryptu ----
chmod +x scripts/run_pipeline.sh

# ---- Nginx ----
echo "Konfiguracja nginx..."
cat > /etc/nginx/sites-available/tablica-swiat <<NGINX
server {
    listen 80;
    server_name ${DOMAIN:-_};

    root $SITE;
    index index.html;

    # Bez cache dla events.json (dane sie aktualizuja)
    location = /events.json {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma no-cache;
        expires 0;
    }

    location / {
        try_files \$uri \$uri/ =404;
    }

    gzip on;
    gzip_types text/css application/javascript application/json;
}
NGINX

ln -sf /etc/nginx/sites-available/tablica-swiat /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# ---- Cron ----
echo "Rejestrowanie zadania cron (12:00 i 22:00)..."
CRON_LINE_1="0 12 * * * $PROJECT/scripts/run_pipeline.sh >> $PROJECT/logs/cron.log 2>&1"
CRON_LINE_2="0 22 * * * $PROJECT/scripts/run_pipeline.sh >> $PROJECT/logs/cron.log 2>&1"

# Dodaj tylko jesli nie istnieja
(crontab -l 2>/dev/null | grep -v "run_pipeline"; echo "$CRON_LINE_1"; echo "$CRON_LINE_2") | crontab -

echo ""
echo "=== GOTOWE ==="
echo "Strona dziala na: http://$(curl -s ifconfig.me 2>/dev/null || echo '<IP serwera>')"
echo "Logi pipeline:   $PROJECT/logs/"
echo "Cron:            crontab -l"
echo ""
echo "Pamietaj: wgraj .env z kluczami API do $PROJECT/.env"

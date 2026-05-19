cfg40348 = """server {
    listen 40348;
    listen [::]:40348;
    server_name _;
    root /opt/tablica-swiat/site;
    index index.html;
    charset utf-8;
    location = /events.json {
        add_header Cache-Control no-cache;
        expires 0;
    }
    location / {
        try_files $uri $uri/ /index.html;
    }
    gzip on;
    gzip_types text/css application/javascript application/json text/plain text/html;
    gzip_vary on;
}
"""

cfg80 = """server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    root /opt/tablica-swiat/site;
    index index.html;
    charset utf-8;
    location = /events.json {
        add_header Cache-Control no-cache;
        expires 0;
    }
    location / {
        try_files $uri $uri/ /index.html;
    }
    gzip on;
    gzip_types text/css application/javascript application/json text/plain text/html;
    gzip_vary on;
}
"""

with open("/etc/nginx/sites-available/tablica-swiat", "w") as f:
    f.write(cfg40348)
with open("/etc/nginx/sites-available/default", "w") as f:
    f.write(cfg80)

print("Nginx configs written OK")

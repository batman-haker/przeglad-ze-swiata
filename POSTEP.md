# Przegląd ze świata — postęp prac

## Co zostało zbudowane

### Pipeline danych
- [x] `scripts/fetch.py` — pobiera posty @GPW_Trader2022 przez twitterapi.io API
- [x] `scripts/parse.py` — parser strukturalny (format stary/nowy, podpunkty a/b/c)
- [x] `scripts/enrich.py` — wzbogacanie AI przez Gemini 2.5 Flash (lub Anthropic)
- [x] `scripts/build.py` — pełny pipeline w jednym poleceniu
- [x] 388 wydarzeń przetworzone i w bazie (stan: 18.05.2026)

### Strona internetowa
- [x] Dark theme, banner graficzny, font Orbitron
- [x] **Tablica** — timeline z filtrami kategorii i wyszukiwarką
- [x] **Statystyki** — 5 wykresów Chart.js (kategorie, waga, aktywność, podmioty, typy)
- [x] **Mapa** — Leaflet.js, kolorowe pinezki per kategoria, popupy z wydarzeniami
- [x] **Powiązania** — D3.js graf podmiotów, drag & drop, zoom
- [x] **Iran/Ormuz** — chronologiczny timeline wątku, najnowsze na górze

### Automatyzacja
- [x] Cron na mikr.us: pipeline o **12:00 i 22:00** każdego dnia
- [x] Task Scheduler Windows: TablicaSwiat_Noon + TablicaSwiat_Evening
- [x] Logi: `/opt/tablica-swiat/logs/`

### Deploy
- [x] Serwer: mikr.us (andrzej240.mikrus.xyz, port SSH 10240)
- [x] Strona publiczna: **http://srv26.mikr.us:40348/**
- [x] nginx skonfigurowany, gzip włączony
- [x] Repo GitHub: **https://github.com/batman-haker/przeglad-ze-swiata**

---

## Co przed nami

### Priorytet 1 — Telegram bot (dodawanie treści z telefonu)
- [ ] Założyć bota przez @BotFather → uzyskać token
- [ ] `scripts/telegram_bot.py` — odbiera wiadomości, przetwarza przez Gemini, dodaje do events.json
- [ ] Deploy bota na mikr.us (jako proces w tle / PM2 / systemd)
- [ ] Instrukcja: kopiuj tekst na telefonie → wklej do Telegrama → pojawia się na stronie

### Priorytet 2 — Aktualizacja strony bez odświeżania
- [ ] Auto-refresh events.json co 5 minut (bez przeładowania strony)
- [ ] Wskaźnik "Ostatnia aktualizacja: X minut temu"
- [ ] Animacja nowych kart po załadowaniu

### Priorytet 3 — Więcej wątków Spotlight
- [ ] Dodać wątek: `ai-tech` (AI / technologia)
- [ ] Dodać wątek: `jsw-shorts` (JSW / shortseller)
- [ ] Dodać wątek: `spacex`
- [ ] UI: zakładka per wątek lub dropdown

### Priorytet 4 — Jakość danych
- [ ] Deduplikacja wydarzeń (te same newsy z różnych postów)
- [ ] Lepsze wykrywanie regionu (coords dla mapy)
- [ ] Weryfikacja kategorii przez AI (drugi pass dla niskiej pewności)

### Priorytet 5 — Domena i HTTPS
- [ ] Podpiąć własną domenę (np. przeglad.xyz)
- [ ] Certyfikat SSL przez Let's Encrypt (certbot)
- [ ] Redirect HTTP → HTTPS

### Priorytet 6 — Powiadomienia
- [ ] Telegram alert gdy pojawi się event o wadze `high`
- [ ] Dzienny digest (podsumowanie 24h) wysyłany na Telegram

---

## Dane techniczne

| Komponent | Technologia |
|---|---|
| Fetch | twitterapi.io REST API |
| AI | Google Gemini 2.5 Flash |
| Frontend | Vanilla JS + Chart.js + Leaflet + D3 |
| Hosting | mikr.us VPS (Ubuntu, nginx) |
| Automatyzacja | cron (Linux) + Task Scheduler (Windows) |
| Repo | github.com/batman-haker/przeglad-ze-swiata |

## Znane problemy / ograniczenia
- Gmail IMAP niedostępny (Google blokuje App Passwords na tym koncie) → zastąpiony Telegramem
- SSL verify=False na Windows Python 3.13 (certyfikaty systemowe)
- events.json jest w repo (publiczny) — dane newsowe, nie wrażliwe
- Strona bez HTTPS (port 40348) — do zmiany przy własnej domenie

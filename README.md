# Tablica Świat — interaktywna oś czasu wydarzeń

> **Pracujesz w Claude Code? Zacznij od pliku `BRIEF.md`** — zawiera pełny
> kontekst projektu, podjęte decyzje i otwarte pytania.

Interaktywna tablica informacyjna budowana na podstawie "skrótów info ze Świata"
z profilu X @GPW_Trader2022. Gęste posty są rozbijane na pojedyncze, klikalne
wydarzenia z dwoma poziomami: hasło → rozwinięcie ze szczegółami.

## Jak to działa

```
posts_raw.txt  ──parse.py──►  fragmenty  ──enrich.py (AI)──►  events.json  ──►  strona
   (wklejasz)                                                  (gotowe dane)    (hosting)
```

Przetwarzanie AI dzieje się raz, lokalnie. Na hosting trafia tylko gotowy
`events.json` + statyczne HTML/CSS/JS. Strona nie potrzebuje backendu.

## Struktura

```
tablica-swiat/
├── data/
│   ├── schema.json       definicja struktury wydarzenia
│   ├── posts_raw.txt     TU WKLEJASZ POSTY z X
│   └── events.json       wynik (generowany)
├── scripts/
│   ├── parse.py          rozbija posty na fragmenty (Krok 3)
│   ├── enrich.py          warstwa AI — wzbogaca fragmenty (Krok 4)
│   └── build.py           uruchamia cały pipeline
├── site/                  to ląduje na hostingu
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── events.json
├── .env                   klucz API (utwórz z .env.example)
└── README.md
```

## Pierwsze uruchomienie

1. Zainstaluj zależności:
   ```
   pip install anthropic python-dotenv
   ```
2. Utwórz plik `.env` na bazie `.env.example` i wpisz klucz API Anthropic.
3. Wklej posty do `data/posts_raw.txt` (format opisany na górze tego pliku).
4. Uruchom pipeline:
   ```
   python scripts/build.py
   ```
5. Otwórz `site/index.html` w przeglądarce.

## Aktualizacja (3x dziennie)

Dopisz nowe posty na koniec `posts_raw.txt` i ponownie uruchom `build.py`.
Skrypt przetworzy tylko nowe fragmenty (stare są w cache events.json).

## Status budowy

- [x] Krok 1 — struktura projektu i schemat danych
- [ ] Krok 2 — format wejściowy (gotowy w posts_raw.txt)
- [ ] Krok 3 — parser strukturalny
- [ ] Krok 4 — warstwa AI
- [ ] Krok 5 — klastrowanie wątków
- [ ] Krok 6-8 — frontend
- [ ] Krok 9-10 — test i deploy

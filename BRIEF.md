# BRIEF PROJEKTU — Tablica Świat

> Ten plik to kontekst startowy dla Claude Code.
> Przeczytaj go w całości przed pisaniem kodu.
> Zawiera: cel, architekturę, decyzje już podjęte, schemat danych, logikę parsera
> oraz listę otwartych pytań do ustalenia z użytkownikiem.

---

## 1. CEL PROJEKTU

Zbudować interaktywną, globalną **tablicę informacyjną** w formie osi czasu (timeline),
opartą na "skrótach info ze Świata" publikowanych na profilu X @GPW_Trader2022
(3 posty dziennie).

Każdy post to gęsty blok 20-30 newsów sklejonych myślnikami. Zadanie:
rozbić go na pojedyncze, **atomowe, klikalne wydarzenia**, gdzie każde ma dwa poziomy:
- **hasło** — krótki nagłówek
- **rozwinięcie** — szczegóły, kontekst, tło

Tablica ma być interaktywna i globalna, z naciskiem na bieżący główny wątek
(obecnie: Iran).

---

## 2. ARCHITEKTURA

```
posts_raw.txt ──parse.py──► fragmenty ──enrich.py (AI)──► events.json ──► strona
  (wklejane                                              (gotowe dane)   (hosting)
   ręcznie)
```

Kluczowa zasada: **przetwarzanie AI dzieje się raz, lokalnie/offline.**
Na hosting trafia tylko gotowy `events.json` + statyczne HTML/CSS/JS.
Strona NIE ma backendu, nie pali tokenów przy wejściu.

Cztery warstwy:
1. Pozyskanie danych — RĘCZNE wklejanie postów do posts_raw.txt
2. Parsing + wzbogacenie AI — przez API Claude (Anthropic)
3. Frontend — statyczna oś czasu
4. Aktualizacja — dokarmianie 3x/dzień

---

## 3. DECYZJE JUŻ PODJĘTE (nie zmieniać bez zgody użytkownika)

- Pozyskanie postów: RĘCZNIE (kopiuj-wklej). Bez scrapingu X.
- Przetwarzanie treści: przez API Claude (Anthropic). Kod modularny —
  możliwość podmiany dostawcy.
- Hosting: statyczna strona (Oracle Cloud Free Tier / Mikrus).
- Kategorie (zamknięta lista 6 pozycji):
  geopolityka, gospodarka, rynki, energia, technologia, polska
- Konferencja z podpunktami a/b/c/.../i = JEDNO wydarzenie złożone.
  Podpunkty trafiają do pola `punkty[]`, widoczne po rozwinięciu karty.
- Parser ma wypisywać BEZPIECZNIK: licznik fragmentów na każdy post.

---

## 4. PLAN — 10 KROKÓW

- [x] Krok 1 — struktura projektu i schemat danych
- [x] Krok 2 — format wejściowy posts_raw.txt
- [x] Krok 3 — parser strukturalny (napisany, przetestowany)
- [ ] Krok 4 — warstwa AI (enrich.py)
- [ ] Krok 5 — klastrowanie wątków (np. iran-2025)
- [ ] Krok 6 — frontend: szkielet HTML/CSS osi czasu
- [ ] Krok 7 — frontend: interaktywność, filtry, wyszukiwarka
- [ ] Krok 8 — panel "spotlight" dla głównego tematu (Iran)
- [ ] Krok 9 — test na realnych 30 dniach danych
- [ ] Krok 10 — deploy + procedura aktualizacji

AKTUALNY PUNKT: Krok 3 gotowy. Przechodzimy do Kroku 4 (enrich.py).

---

## 5. SCHEMAT DANYCH (jedno wydarzenie)

Pełna definicja w data/schema.json. Skrót pól:

| pole          | opis                                                        |
|---------------|-------------------------------------------------------------|
| id            | RRRRMMDD-GGMM-NN (data-godzina posta-numer wydarzenia)      |
| post_url      | URL posta źródłowego na X                                   |
| post_index    | numer porządkowy posta w posts_raw.txt (debug)             |
| datetime      | ISO 8601, data + godzina                                    |
| kategoria     | jedna z 6: geopolityka/gospodarka/rynki/energia/technologia/polska |
| watek         | id wątku tematycznego, np. "iran-2025", lub null            |
| waga          | high / medium / low                                         |
| haslo         | krótki nagłówek, ~80 znaków, poczyszczony                   |
| rozwiniecie   | 2-4 zdania kontekstu — pisane przez AI                      |
| punkty        | lista podpunktów dla wydarzeń złożonych, lub null           |
| podmioty      | kraje/firmy/osoby/organizacje                               |
| region        | np. Bliski Wschód, Europa, USA, lub null                    |
| typ           | deklaracja/decyzja/dane/konflikt/umowa/prognoza/wydarzenie  |
| raw_fragment  | oryginalny urywek tekstu — bezpiecznik weryfikacji          |

---

## 6. LOGIKA PARSERA (parse.py) — ZAIMPLEMENTOWANA

Parser jest CELOWO "głupi": tylko mechanicznie tnie tekst.
NIE klasyfikuje, NIE poprawia literówek, NIE pisze rozwinięć — to robi AI (Krok 4).

### Ustalenia empiryczne (na podstawie ~60 pobranych postów, maj 2025–2026)

**a) Dwa formaty separatorów (format zmienił się ok. przełomu 2025/2026):**
- STARY (2025): cały post w JEDNEJ linii, separator `\s+-\s+` (spacja-myślnik-spacja)
- NOWY (2026+): każdy news w OSOBNEJ linii zaczynającej się od `-`
  Parser wykrywa format automatycznie (>30% linii zaczyna się od `-` → nowy).

**b) Podpunkty:** wzorzec `a) b) c) ... i)` (tylko litery a–i z nawiasem).
   Pojawiają się wyłącznie w starym formacie (konferencje prasowe).
   W nowym formacie nie obserwowano. Zawsze poprzedzone wyraźną frazą.

**c) Nagłówek** — zawsze PIERWSZA linia/fragment, zawiera "skrót info" lub
   "skrót informacji" (wariantów wiele: "Do kawy skrót...", "Skrót info nr 2⃣...").
   **Ogon** — na końcu, zawiera "poprzedni" lub "skrót nr/z/w" + URL na nast. linii.
   Ogon nie zawsze istnieje (np. ostatni skrót danego dnia).

**d) Myślnik w treści:** nie jest problemem. W nowym formacie separator to
   nowa linia (nie ` - `), więc `srebro -3%` czy `Iran - USA` są bezpieczne.
   W starym formacie `+8%` i `-3%` nie mają spacji po myślniku — regex `\s+-\s+`
   ich nie rozetnie.

**e) Posty niestandardowe:** w pobranych danych jest ~70% postów niebędących
   skrótami info (Shorty JSW, RT, jednolinijkowe newsy, ankiety).
   Parser filtruje: przetwarza TYLKO posty z "skrót info/informacji" w 1. linii.

### Przepływ główny
1. Wczytaj plik (posts_raw.txt lub fetched_posts.txt — ten sam format)
2. Podziel po "=== POST ===", pomiń linie z `#`
3. Z każdego posta wyciągnij metadane: URL, DATA, GODZINA
4. Jeśli pierwsza linia treści NIE zawiera "skrót info" → pomiń post
5. Wykryj format (nowy/stary) i rozbij na fragmenty
6. Odetnij nagłówek i ogon
7. Wykryj bloki z podpunktami a) b) c) → `zlozony=true`, lista do `punkty[]`
8. Zwróć listę fragmentów z metadanymi

### Wyjście (jeden fragment)
```
{post_url, post_index, datetime, raw_fragment, haslo_raw, punkty, zlozony, fragment_nn}
```

### BEZPIECZNIK
Po parsowaniu wypisuje licznik fragmentów per post:
  "Post 1:  24 fragmentów"
Podejrzanie mało (<5) = coś się skleiło → ręczna korekta w pliku źródłowym.

### Uruchomienie
```
python scripts/parse.py                        # domyślnie posts_raw.txt
python scripts/parse.py data/fetched_posts.txt # lub inny plik
```

---

## 7. ODPOWIEDZI NA OTWARTE PYTANIA (zweryfikowane empirycznie)

Pytania z poprzedniej wersji zostały rozstrzygnięte analizą ~60 pobranych postów.
Szczegóły w sekcji 6 powyżej. Sekcja 7 zamknięta.

---

## 8. STRUKTURA PLIKÓW

```
tablica-swiat/
├── BRIEF.md              <-- ten plik
├── data/
│   ├── schema.json       definicja struktury wydarzenia
│   ├── posts_raw.txt      TU użytkownik wkleja posty
│   └── events.json        wynik (generowany)
├── scripts/
│   ├── parse.py           parser — Krok 3 (zalążek, do napisania)
│   ├── enrich.py          warstwa AI — Krok 4 (zalążek)
│   └── build.py           spina pipeline (zalążek)
├── site/                  to ląduje na hostingu
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── events.json
├── .env                   klucz API (utworzyć z .env.example)
├── .env.example
├── .gitignore
└── README.md
```

---

## 9. JAK KONTYNUOWAĆ (instrukcja dla Claude Code)

1. Przeczytaj ten plik i potwierdź użytkownikowi, że rozumiesz projekt.
2. Zadaj użytkownikowi 5 otwartych pytań z sekcji 7.
3. Po uzyskaniu odpowiedzi — zaktualizuj sekcję 6 (logika parsera).
4. Napisz parse.py zgodnie z ustaloną logiką. Parser musi dać się uruchomić
   samodzielnie (python scripts/parse.py) i wypisać wynik na przykładowym
   poście z posts_raw.txt — w tym licznik bezpiecznika.
5. Dopisz requirements.txt (anthropic, python-dotenv).
6. Dopiero potem przejdź do Kroku 4 (enrich.py).

Pracujcie krok po kroku, według planu z sekcji 4. Po każdym kroku
aktualizujcie checklistę.

# Dowody — CultureRoute (2026-10-20)

Środowisko: /usr/bin/python3 3.12, stdlib only.

```
$ python3 -m pytest tests -q
............                                                             [100%]
12 passed in 0.91s
```

```
$ python3 -m cultureroute plan --city Berlin --mood curious --minutes 180 --offline
CultureRoute — Berlin, mood=curious, mode=OFFLINE FIXTURES
  [place] Museum für Naturkunde (40 min, score 0.3) — affinity 0.00, mood match yes
  [film ] Documentary: Rivers of Berlin (60 min, score 0.3) — affinity 0.00, mood match yes
  [book ] Berlin: A City in Fragments (30 min, score 0.3) — affinity 0.00, mood match yes
  [place] Kleiner Garten (40 min, score 0.3) — affinity 0.00, mood match yes
  steps used: 6
```

```
$ env -u QLOO_API_KEY python3 -m cultureroute plan --city Berlin --minutes 60
error: QLOO_API_KEY is not set. Run with --offline for the deterministic fixture mode, or export
the key from https://docs.qloo.com before using --live.
```

Test negatywny obecny w `tests/test_qloo.py::test_live_mode_without_key_fails_loudly`.

## Poprawka integracji Qloo (2026-10-20)
Base URL zmieniony na `https://hackathon.api.qloo.com`, endpoint `/v2/insights`,
parametry `filter.type`, `filter.location.query`, `signal.interests`, `feature.explainability`.
Odpowiedź czytana z `results.entities`. Offline filtruje pool po typie encji.

```
$ python3 -m pytest tests -q
14 passed in 0.86s
```

```
$ python3 -m cultureroute plan --city Berlin --mood curious --minutes 180 --offline
CultureRoute — Berlin, mood=curious, mode=OFFLINE FIXTURES
  [place] Museum für Naturkunde (40 min, score 0.467) — affinity 0.17, mood match yes
  [music] Nils Frahm (35 min, score 0.0) — affinity 0.00, mood match no
  [film ] Sci-Fi Night: Metropolis (60 min, score 0.383) — affinity 0.08, mood match yes
  [book ] The Science of Sound (30 min, score 0.383) — affinity 0.08, mood match yes
  steps used: 6
```

Live nie był uruchomiony — wymaga `QLOO_API_KEY` z formularza organizatora.

## Ranking: cold start i kolejność z API (2026-10-20)

Objaw zmierzony przed zmianą (pusty profil, `--mood curious`, ten sam fixture):

```
[place] Museum für Naturkunde   score 0.3   affinity 0.00, mood match yes
[film ] Documentary: Rivers…   score 0.3   affinity 0.00, mood match yes
[book ] Berlin: A City…        score 0.3   affinity 0.00, mood match yes
[place] Kleiner Garten         score 0.3   affinity 0.00, mood match yes
```

Wszystkie pozycje miały dokładnie 0,3 (bonus nastroju był zero-jedynkowy), więc remisy
rozstrzygała kolejność encji z API. Zmierzone: te same dane wejściowe, przetasowany pool
encji (ziarna 1–5) → **trasa różna przy każdym ziarnie**. Plan nie był funkcją swoich
argumentów.

Po zmianie bonus nastroju jest stopniowany (`0.3 × trafione / wszystkie tagi nastroju`),
a remis rozstrzyga liczba trafień, potem nazwa — nigdy kolejność z API:

```
$ python3 -c "...CultureAgent(QlooClient(offline=True), TasteProfile()).plan('Berlin','curious',240)"
place Museum für Naturkunde  0.12  affinity 0.00, mood 2/5
film  Sci-Fi Night: Metropolis 0.12  affinity 0.00, mood 2/5
book  Berlin: A City in Fragments 0.06  affinity 0.00, mood 1/5
place Kleiner Garten         0.06  affinity 0.00, mood 1/5
```

Przetasowany pool, ziarna 1–7, nastroje `curious` i `reflective` → trasa identyczna
(co do rodzaju, nazwy i wyniku).

Regresja: `tests/test_agent.py::test_cold_start_scores_differentiate_by_mood_overlap` oraz
`::test_plan_does_not_depend_on_entity_order`. Ablacja (powrót do binarnego bonusu i „pierwszy
wygrywa przy remisie”) → oba testy czerwone.

```
$ python3 -m pytest tests -q -p no:warnings
....................                                                     [100%]
20 passed in 1.17s
```

Ten wynik nie mierzy trafności kulturalnej trasy — mierzy, czy ranking w ogóle reaguje na
wejście i czy jest powtarzalny. Doboru miejsc nie ocenialiśmy z ludźmi; to pozostaje otwarte.

## Demo w przeglądarce (2026-10-20)

```
$ python3 -m uvicorn web.server:app --host 127.0.0.1 --port 8749
$ curl -s http://127.0.0.1:8749/api/health
{"ok":true,"offline":true}
```

Chromium 155, 1280×900: nagłówek pokazuje `OFFLINE FIXTURES`, formularz startuje z
`Berlin / curious / 180`. Po „Plan the evening" strona renderuje **4 przystanki 19:00–21:50**
z typem, czasem trwania i uzasadnieniem („affinity 0.17, mood 2/5") obok **śladu decyzji**
(6 kroków: accept/skip z powodem), nagłówek karty: „4 stops, 19:00–21:50 · Berlin · curious".
0 błędów konsoli. Przy 390×844 `scrollWidth == innerWidth == 390` — brak poziomego przewijania.

Zrzuty: `evidence/webui-route-desktop.png`, `evidence/webui-route-mobile.png`,
`evidence/webui-empty-desktop.png`.

To jest ten sam agent co w CLI: `POST /api/plan` woła `CultureAgent.plan` bez zmian, a tryb
w nagłówku pochodzi z obecności `QLOO_API_KEY`. Nie mierzyliśmy tu żywego Qloo — strona
w tym przebiegu działała na fixtures.

## Retry policy klienta Qloo (2026-10-20)

`ARCHITECTURE.md` deklarował „Retry dotyczy 5xx/timeoutów; 4xx lecą od razu jako błąd",
a `QlooClient.get` łapał **każdy** `HTTPError` i ponawiał go dwa razy z odstępem 0,2/0,4 s.
Zły klucz albo literówka w parametrze kosztowały trzy żądania i 0,6 s, zanim użytkownik
zobaczył błąd; `Retry-After` z 429 był ignorowany. Testów ścieżki live nie było wcale.

Po zmianie ponawiane są tylko statusy, które mogą się udać (`408, 429, 500, 502, 503, 504`),
`Retry-After` jest respektowany (z sufitem 5 s), a 4xx kończy się natychmiast z kodem w treści.

Zmierzone w testach z podstawionym `urlopen` (liczba wywołań, nie opinia):

```
HTTP 401  -> 1 wywołanie, RuntimeError "Qloo rejected the request: HTTP 401 ... (retryable=False)"
HTTP 429  -> 3 wywołania (dwa z Retry-After: 0), potem sukces; sleep == [0.0, 0.0]
HTTP 503  -> 3 wywołania (retries=2), potem RuntimeError z HTTP 503
```

Regresja: `tests/test_qloo.py::test_terminal_4xx_is_not_retried`,
`::test_rate_limit_is_retried_and_retry_after_is_honoured`,
`::test_server_error_is_retried_then_reported`. Ablacja (powrót do „ponawiaj wszystko")
→ dwa pierwsze czerwone.

```
$ python3 -m pytest tests -q -p no:warnings
.......................                                                  [100%]
23 passed
```

## Limit ciała żądania w `/api/plan` (2026-10-20)

Endpoint przyjmował dowolne ciało i **odbijał miasto w odpowiedzi**. Zmierzone przed zmianą:
`POST /api/plan` z `city` = 10 mln znaków → **200 OK w 0,47 s, odpowiedź 10 000 870 B**,
peak RSS procesu 53 → 110 MB. To nie tylko zużycie pamięci: żądanie ≈ odpowiedź, czyli
amplifikator dla anonimowego ruchu.

Po zmianie: `Content-Length` wymagany (`411` bez niego), ciało > 16 KB → `413` przed
parsowaniem, pola ograniczone (`city` ≤ 200 znaków, `mood` ≤ 32, `minutes` 5–1440).
Odrzucone ciało jest odczytywane i wyrzucane, więc klient widzi treść błędu.

```
$ curl -s -o /dev/null -w '%{http_code} %{time_total}\n' -X POST --data-binary @bigcity.json ...
413 0.004
peak RSS: 53,5 -> 54,0 MB  (było 53 -> 110 MB)
```

Regresja: `tests/test_web.py::test_oversized_body_is_refused_before_the_agent` (agent
zmonkeypatchowany tak, by rzucił — nie może zostać wywołany), `::test_plan_fields_are_bounded`,
`::test_content_length_policy`. Ablacja: wyłączenie `_body_rejection` → pierwszy test czerwony.

```
$ python3 -m pytest tests -q -p no:warnings
..........................                                               [100%]
26 passed
```

Ta sama klasa defektu wystąpiła wcześniej w life-after-code (`POST /api/analyze`) — warto
znormalizować ją bramką w `tools/verify_wave.py`, zamiast łatać projekt po projekcie.

## Pętla observe w demo (2026-10-20)

Demo w przeglądarce miało tylko połowę pętli: `POST /api/plan` liczył trasę, ale profilu gustu
nie pokazywało i nie dało się go zmienić. `TasteProfile.observe` był wołany wyłącznie z CLI
(`cultureroute/cli.py:54`), a `web/server.py:64` czytał `state/taste.json` bez zapisu.

Zmierzone przed (uvicorn :8753, pusty profil):

```
$ curl -o /dev/null -w '%{http_code}' -X POST .../api/feedback -d '{"tags":["science"],"liked":true}'
404
$ curl -o /dev/null -w '%{http_code}' .../api/taste
404
```

Po: `GET /api/taste` zwraca wagi, `POST /api/feedback` je zmienia i zapisuje, a `POST /api/plan`
niesie pole `taste`. Pomiar na pustym profilu (TestClient, `CULTUREROUTE_TASTE_PATH` → plik tymczasowy):

```
feedback {"tags":["AMBIENT"," piano ","slow"],"liked":true}
  -> ambient 0.00→0.25, piano 0.00→0.25, slow 0.00→0.25, persisted=true
plan Berlin/energetic/180 przed: 1 przystanek  (Berghain Residents,   affinity 0.00)
plan Berlin/energetic/180 po:    4 przystanki  (Nils Frahm 0.25, Kleiner Garten 0.08, ...)
```

Ten sam przebieg w Chromium 155, 1280×900 (uvicorn :8756, pusty profil, 0 błędów konsoli):
4 przystanki z `affinity 0.00`, pasek „Your taste" pusty → klik **More like this** przy drugim
przystanku → komunikat `Profile updated (science 0.00→0.25, history 0.00→0.25, slow 0.00→0.25)
— rebuilding the route.` → trasa przerysowana (`Sci-Fi Night: Metropolis` 0.25), chipy
`science +0.25`, `history +0.25`, `slow +0.25`. Przy 390×844 `scrollWidth == innerWidth == 390`.
Zrzut: `evidence/webui-taste-after-feedback.png`.

Regresja: `tests/test_web.py::test_feedback_changes_the_next_route`,
`::test_feedback_needs_a_real_tag`, `::test_taste_endpoint_reports_the_same_profile_the_plan_uses`,
`::test_index_lets_a_visitor_rate_a_stop`. Ablacja (usunięcie `_persist` i wywołania
`profile.observe`) → pierwszy test czerwony, pozostałe zielone.

```
$ python3 -m pytest tests -q -p no:warnings
30 passed in 1.21s
```

Ścieżka live nadal nieprzebiegnięta: klucza z formularza organizatora nie mamy. Zmierzone
2026-10-20, że host odpowiada i wymaga klucza, więc brak jest po stronie dostępu, nie kodu:

```
$ curl -s -o /tmp/qloo-probe.txt -w '%{http_code} %{time_total}' \
    'https://hackathon.api.qloo.com/v2/insights?filter.type=urn:entity:place'
401 0.421781
{"error":{"reason":"No API key found in request","message":"Unauthorized","code":401}}
```

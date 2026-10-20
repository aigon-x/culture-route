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

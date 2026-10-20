# CRITIQUE — CultureRoute (sceptyk, 2026-10-20)

Werdykt: **37/100**. Kod jest czysty, ale dowód użycia Qloo jest pozorny: ścieżka live nie
może zadziałać, a demo pokazuje wyniki bez profilu gustu.

## Oceny

| Kryterium | Ocena | Uzasadnienie (dowód) |
|---|---|---|
| Technical execution | 50 | 282 linie, 12/12 testów, cache+retry; pętla nie obserwuje wyników, tnie czas trwania. |
| Innovation | 52 | „Trasa z budżetem i śladem" to sensowna rama, ale for-loop z sztywnym harmonogramem, nie agent. |
| Użycie Qloo API | **15** | Zły base URL, endpoint, parametr miasta i parser; zero wywołania live. |
| Jakość dowodów | 32 | Ręczne transkrypty, brak logów; BUILD_RECEIPT dotyczy innego projektu. |
| Zgodność z wymogami | 38 | Repo publiczne + MIT (potwierdzone API GitHuba); brak demo URL i wideo; SUBMISSION.md nie o tym projekcie. |
| Ryzyko odrzucenia | **wysokie (~65%)** | Stage One to pass/fail na „reasonably applies the required APIs". |

## Luka krytyczna — Qloo to atrapa, nie integracja

1. `cultureroute/qloo.py:13` — `https://api.qloo.com`. Klucze hackathonu działają WYŁĄCZNIE na
   `https://hackathon.api.qloo.com`; produkcyjny base daje 401.
2. `cultureroute/agent.py:10-15` — `/v2/entities/music|movie|book|place`. API to `/v2/insights`
   z `filter.type=urn:entity:artist|movie|book|place`; `urn:entity:music` nie istnieje → 404.
3. `cultureroute/agent.py:54` — `city=Berlin` nie jest parametrem Qloo. Filtr lokalizacji to
   `filter.location.query`; nieznane parametry są po cichu ignorowane.
4. `cultureroute/agent.py:56` — realna odpowiedź ma `results.entities` (obiekt), nie top-level
   `entities`; kod iterowałby po kluczach słownika → `AttributeError`.
5. `tests/test_qloo.py` nie dotyka HTTP: brak mocka 200/401/5xx, retry i TTL nieprzetestowane.
   Fixtures są ręcznie napisane, bez ID/URN — nie odwzorowują kształtu Qloo (README:26 kłamie).
6. FAQ Qloo: danych z API nie wolno trzymać w publicznym repo. Fixtures są „bezpieczne" tylko
   dlatego, że nie pochodzą z API — co jednocześnie obala tezę o wiernym mocku.

## Pozostałe słabości (dowód → skutek)

- `agent.py:64` — typ kroku wybierany indeksem `[music, place, film, book, place, music]`, nie
  wynikiem zapytania. Deklaracja „reaguje na to, co wróciło" (ARCHITECTURE.md:12) jest fałszywa.
- `agent.py:84` — `duration = min(typical_minutes, budget)`. Zmierzone: `--minutes 60` daje
  60-minutowy film jako **20 min**. To łamie „twardy budżet" (ARCHITECTURE.md:17).
- Demo: profil pusty (`cli.py:62-63`), więc `affinity 0.00` i wszystkie score 0.3 (EVIDENCE.md:10-16).
  Ablacja: `--city Nowhere` daje identyczną trasę co Berlin (miasto ignorowane w offline).
- `tests/test_agent.py:22-26` — „taste changes ordering" przechodzi też z pustym profilem;
  brak kontroli negatywnej, test nie dowodzi wpływu gustu.
- `EVIDENCE.md:16` — „steps used: 6" przy 4 pozycjach; licznik to iteracje pętli, nie użyte kroki.
- `../BUILD_RECEIPT.json` — `entrypoint: solution.py`, „5 klas, 22 przykładów" = klasyfikator
  Bayesa; nie waliduje tego projektu. `../SUBMISSION.md` opisuje triage bez Qloo.
- `DEVPOST_DRAFT.md:51` — `<VIDEO_URL>` placeholder; brak linku do działającego demo.
- `SUBMISSION-CHECKLIST.md:13` — „Repo publiczne: BLOKADA", a repo jest publiczne (zmierzone).

## 5 ulepszeń wg wpływu

1. **Napraw live Qloo** — `qloo.py:13` base, `agent.py:10-15` `/v2/insights` + `filter.type`,
   `agent.py:54` `filter.location.query`, `agent.py:56` `results.entities`; dodaj realny przebieg
   live do EVIDENCE. Wpływ: ratuje Stage One, +25 compliance, +30 Qloo.
2. **Demo z zasianym profilem** — `cli.py:62` ładuje pusty profil; dodaj `--seed-taste` lub wpis
   stanu i pokaż dwie różne trasy. Wpływ: +15 innovation, demo przestaje przeczyć tezie.
3. **Popraw budżet** — `agent.py:84`: pomiń pozycję, gdy `typical_minutes > budget`; test na
   60 min. Wpływ: +10 technical, usuwa jawny błąd merytoryczny.
4. **Prawdziwa obserwacja** — `agent.py:64`: wybieraj kolejny typ na podstawie zwróconych
   kategorii/pustych wyników; test, że zmiana wyniku zmienia następny krok. Wpływ: +10 innovation.
5. **Spójny pakiet** — usuń/przepisz `../SUBMISSION.md` i `BUILD_RECEIPT.json`, wstaw
   `VIDEO_URL` i URL demo, zaktualizuj checklistę. Wpływ: +10 evidence.

## Czy plan przekonuje sędziego?

Nie. Draft mówi „agent", a pokazuje deterministyczny harmonogram; mówi „taste-aware", a jedyny
zrzut ma affinity 0.00 i cztery identyczne oceny 0.3. Sędzia nie ma powodu uruchamiać CLI, skoro
nie ma demo URL ani wideo. Brakuje najbardziej: **jednego realnego wywołania Qloo z widocznym
`entity_id` i `feature.explainability=true`, zrzutu/wideo z przebiegu oraz kontrastu dwóch profili
gustu.** Bez tego Stage One oceni projekt jako „offline mock", nie integrację.

# CultureRoute

Agent, który zamienia profil gustu w spójną trasę kulturalną: muzyka, film, książka, miejsce.
Pyta Qloo o encje w mieście, ocenia je względem gustu i nastroju, pilnuje budżetu czasu
i zapisuje ślad decyzji.

## Dlaczego to nie jest lista rekomendacji
Lista odpowiada „co lubisz". Trasa odpowiada „co zrobić w 3 godziny, w tej kolejności, i dlaczego".
Agent prowadzi pętlę plan → act → observe: pyta Qloo, ocenia, odrzuca duplikaty i pozycje bez
trafienia w gust, skraca budżet, kończy gdy czas się wyczerpie albo limit kroków (6).

## Uruchomienie
```bash
python3 -m pytest tests -q                 # 23 testów
python3 -m cultureroute plan --city Berlin --mood curious --minutes 180 --offline
python3 -m cultureroute plan --city Berlin --mood curious --offline --json
python3 -m cultureroute feedback "Museum für Naturkunde" like --tags museum,science
```

## Demo w przeglądarce
```bash
python3 -m uvicorn web.server:app --host 127.0.0.1 --port 8099
# otwórz http://127.0.0.1:8099/ i naciśnij „Plan the evening"
```
Strona pokazuje trasę jako timeline (godzina startu, czas trwania, typ, uzasadnienie wyboru)
obok pełnego śladu decyzji (`accept` / `skip` z powodem), a w nagłówku jawny tryb pracy
(`OFFLINE FIXTURES` albo `LIVE QLOO`). Nic nie wychodzi do sieci, dopóki nie ustawisz
`QLOO_API_KEY` — wtedy ten sam endpoint odpowiada z live Qloo.

Zrzuty z realnego przebiegu (Chromium 155, 1280×900 i 390×844, zero błędów konsoli):
`evidence/webui-route-desktop.png`, `evidence/webui-route-mobile.png`,
`evidence/webui-empty-desktop.png`.

Tryb `--offline` korzysta z deterministycznych fixtures i jest jawnie oznaczony w wyjściu.
Tryb live wymaga `QLOO_API_KEY`; bez klucza CLI kończy się kodem 3 i czytelnym komunikatem.

## Ograniczenia
- Model gustu to suma wag tagów, nie embeddingi; przy pustym profilu decyduje stopień
  dopasowania do nastroju (0,3 × trafione/wszystkie), a remis rozstrzyga nazwa — trasa jest
  powtarzalna, ale nie twierdzimy, że jest „najlepsza” kulturalnie.
- Fixtures pokrywają cztery ścieżki Qloo; live korzysta z `https://hackathon.api.qloo.com` i wymaga klucza
  z formularza organizatora.
- Brak geolokalizacji trasy — kolejność wynika z budżetu i trafności, nie z odległości.

## Licencja
MIT.

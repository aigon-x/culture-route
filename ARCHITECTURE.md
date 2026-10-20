# Architektura

```
CLI (cli.py)
 ├── TasteProfile (taste.py)      wagi tagów [-1,1], aktualizacja z feedbacku, JSON state
 └── CultureAgent (agent.py)      pętla plan→act→observe, limit 6 kroków, budżet minut
      └── QlooClient (qloo.py)    HTTP GET, cache 120 s, retry 2x, tryb offline na fixtures
```

## Decyzje
1. **Własny klient HTTP zamiast SDK** — SDK Qloo nie jest wymagane, a klient daje kontrolę nad
   cache, retry i trybem offline, którego SDK nie ma.
2. **Pętla z limitem kroków zamiast jednego zapytania** — pozwala reagować na to, co wróciło
   (np. odrzucić duplikat i dobrać inny typ), i daje ślad decyzji do debugowania.
3. **Affinity jako średnia wag tagów** — prosta, deterministyczna, tłumaczalna. Alternatywa
   (embeddingi) wymaga modelu i nie wnosi nic przy 4 kategoriach i krótkich listach.
4. **Budżet czasu jako twardy warunek** — pozycja wchodzi tylko wtedy, gdy mieści się w limicie;
   dzięki temu wynik jest wykonalny, nie tylko ładny.

## Przepływ danych
`--city/--mood/--minutes` → agent wybiera typ → `QlooClient.get` → lista encji z tagami →
score = affinity + bonus nastroju → najlepsza niewidziana pozycja → budżet -= czas →
wpis w trace → koniec przy budżecie 0 lub 6 krokach → wydruk/JSON.

## Znane granice
- Cache jest w pamięci procesu (120 s), bez współdzielenia między uruchomieniami.
- Retry dotyczy 5xx/timeoutów; 4xx lecą od razu jako błąd.

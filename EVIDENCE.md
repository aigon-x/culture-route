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

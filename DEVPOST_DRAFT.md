# CultureRoute — Devpost draft

**Tagline:** A taste-aware agent that turns "what should I do tonight?" into a timed, justified cultural route.

## Inspiration
Recommendation apps answer a different question than the one people ask when they have three
hours in a city. We wanted an agent that plans a sequence, defends each choice, and respects the
clock.

## What it does
CultureRoute keeps a small taste profile (tag weights updated from likes/dislikes). The agent asks
Qloo for music, film, books and places in a city, scores each candidate against the profile plus
the chosen mood, drops duplicates and weak matches, and builds a route that fits the available
minutes. Every step is recorded in a trace.

## How we built it
Python 3.12, standard library only: a Qloo HTTP client with cache and retry, a deterministic
offline fixture mode, a taste model, and a bounded plan-act-observe loop. 20 unit tests, including
the negative case: live mode without an API key fails loudly instead of silently degrading.

## Challenges
- Qloo access requires an API key from the organiser form; we built the offline mode first so the
  agent is testable and demoable without credentials, and made the live path explicit.
- Avoiding "recommendation slop": the agent must reject candidates, not just rank them.

## Accomplishments
- Deterministic, reproducible planning with a decision trace: the route is a function of
  profile, mood and budget only — shuffling the API response does not change it.
- 20/20 tests, no network needed for the demo.
- Clear separation between offline fixtures and live API.

## What we learned
Bounded loops beat single-shot queries when the value is in sequencing, and a trace turns an
opaque recommendation into something a user can argue with.

## What's next
- Real Qloo key + entity embeddings for taste.
- Distance-aware ordering between stops.
- Feedback loop across sessions with a persistent profile.

## Built with
python, qloo-api, json, urllib

## Try it
```bash
python3 -m pytest tests -q
python3 -m cultureroute plan --city Berlin --mood curious --minutes 180 --offline
```

## Links
- Repository: https://github.com/aigon-x/culture-route
- Demo video: `<VIDEO_URL>`

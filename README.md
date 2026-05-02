# Vera — magicpin AI Challenge Bot

**Deterministic merchant growth message engine for Vera, magicpin's AI assistant.**

## Approach

The core insight: great Vera messages = **signal routing + merchant grounding + category voice**.

`compose(category, merchant, trigger, customer?)` is the single deterministic function. It:
1. Classifies the trigger type (spike, recall, dip, research, festival, review)
2. Selects the matching handler, which knows _what this moment calls for_
3. Injects real merchant numbers (rating, review count, live offer price, locality)
4. Applies category-specific tone and avoidance rules
5. Returns a structured output: `message`, `headline`, `cta`, `send_as`, `suppression_key`, `rationale`

No templates filled with blanks. Every output is assembled from the actual context it receives.

## Model choice

Rule-based composer (Python) — no LLM inference at compose time. This gives:
- **Determinism**: same input always returns the same message
- **Speed**: sub-millisecond composition, no cold starts
- **Grounding**: impossible to hallucinate facts not in the given context
- **Stability**: no prompt drift between judge runs

The compose logic is transparent and auditable — every decision can be explained.

## Architecture

```
POST /v1/context  →  ContextStore (versioned, scoped, idempotent)
POST /v1/tick     →  resolve context → compose() → structured output
POST /v1/reply    →  intent classification → next action
GET  /v1/healthz  →  { "status": "ok" }
GET  /v1/metadata →  capability declaration
```

### Context store
Versioned by `(scope, context_id)`. Re-posting the same version is a no-op; higher version replaces atomically. Supports scopes: `merchant`, `customer`, `trigger`.

## Category profiles

Each category gets a distinct profile:
- **Dentist**: clinical, reassuring, trust-first. CTAs are appointment-based. Avoids discount pressure.
- **Salon**: visual, aspirational, trend-aware. Surfaces combos and trending looks.
- **Restaurant**: warm, sensory, community-rooted. Time-limited / today-only framing.
- **Gym**: energetic, results-driven. Batch starts, transformation framing.
- **Pharmacy**: utility-first, calm. Availability and refill reminders.

## Trigger handlers

| Trigger | Decision logic |
|---------|----------------|
| `spike` | Surface exact searcher count + query + best offer → single campaign CTA |
| `recall` | Days-since-lapse + offer → low-friction re-booking |
| `dip` | Drop % + vs-period + flash deal → recovery framing |
| `research` | Query + competitor context + differentiator + intro offer |
| `festival` | Days to event + category seasonal hook + best offer |
| `review` | Stars ≥ 4 → referral nudge; < 4 → draft recovery reply |

## Running locally

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Deploying

Works on any Python hosting: Railway, Render, Fly.io, GCP Cloud Run, etc.

```bash
# Render / Railway: set start command to:
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Tradeoffs

- **Rule-based vs LLM**: Rule-based guarantees determinism and grounding. A hybrid approach (rules for routing + LLM for prose polish) could improve naturalness but risks non-determinism.
- **In-memory store**: Fast and simple. Production would use Redis with TTL per scope.
- **Reply classification**: Keyword matching covers the core intents. A small intent classifier would handle ambiguous replies better.

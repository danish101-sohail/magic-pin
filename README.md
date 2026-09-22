# magicpin Vera AI Challenge

## Approach

`/v1/tick` groups active trigger IDs by merchant and lets `priority.pick_trigger()` choose one using trigger kind, urgency, performance deltas, and merchant signals. `compose()` then uses the category slug, merchant facts, trigger payload, and optional customer context to choose a deterministic category-specific message and CTA. Each message gets a `merchant_id:trigger_kind` suppression key; `tick` keeps sent keys in memory and skips duplicates.

## Model Choice

The deployed app uses no LLM. Message phrasing, trigger priority, reply classification, and suppression are all plain Python rules. This keeps responses deterministic and fast, and avoids fabricating facts or depending on an external model during judging. `judge_simulator.py` can use an LLM to score the bot separately, but it is not part of the app runtime.

## Endpoints

- `POST /v1/context` accepts versioned category, merchant, customer, and trigger context, with idempotent higher-version replacement.
- `POST /v1/tick` selects at most one unsent trigger per merchant and returns at most 20 composed actions.
- `POST /v1/reply` handles canned auto-replies, positive intent, opt-outs, hostility, and off-topic replies.
- `GET /v1/healthz` reports process uptime and loaded-context counts.
- `GET /v1/metadata` returns the submission identity and version.

Reproduce the local dataset with:

```powershell
python dataset/generate_dataset.py --out dataset/expanded
```

## Tradeoffs / Known Limitations

- State is in memory only: contexts, suppression keys, reply history, and opt-outs disappear on restart.
- Composition and reply handling use phrase and field rules; they do not yet cover every trigger kind or nuanced conversation state.
- No application-side rate limiter or request timeout is included; those limits are enforced by the judge environment.
- No automated test suite is committed; deployment uses the included `requirements.txt` and `Procfile`.

## Setup

Create a virtual environment, install the app dependencies, and start FastAPI:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For Render or another Procfile-based host, use the included `Procfile`: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

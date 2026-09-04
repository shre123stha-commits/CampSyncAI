# Deployment

Running CampusSync for a class — a few dozen students on shared
infrastructure rather than one laptop.

---

## What changes from local development

| Concern | Local | Shared deployment |
|---|---|---|
| Database | SQLite file | **Postgres** |
| Model | Ollama on your machine | **Hosted API** (or a shared Ollama host) |
| Sessions | Database-backed | Same, and now it matters |
| Secret key | Auto-generated | **Must be set explicitly** |
| Uploads / cache | Local directories | **Named volumes** |
| OAuth redirects | `localhost` | Your real HTTPS domain |

---

## 1 · Configure

Create `.env` beside `docker-compose.prod.yml`:

```ini
# --- required ---
POSTGRES_PASSWORD=<long random string>
SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">

# --- model ---
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
PLANNING_MODEL=gpt-4o-mini

# --- optional integrations ---
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://campussync.example.edu/sources/classroom/callback

MS_CLIENT_ID=
MS_CLIENT_SECRET=
MS_REDIRECT_URI=https://campussync.example.edu/sources/teams/callback
MS_TENANT=common
```

> ⚠️ **`SECRET_KEY` must never change after the first deploy.** It encrypts
> every stored source credential. Rotate it and every connected calendar and
> OAuth token becomes undecryptable, forcing all students to reconnect. Back
> it up somewhere you will still have in a year.

## 2 · Start

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Postgres has a healthcheck and the backend waits for it, so a cold start
comes up in the right order.

```bash
docker compose -f docker-compose.prod.yml ps
curl http://localhost:8000/health
```

---

## Choosing a model provider

`LLM_PROVIDER` accepts `ollama` or `openai`. The `openai` path targets any
OpenAI-compatible endpoint, which is most of them:

| Provider | `OPENAI_BASE_URL` | Notes |
|---|---|---|
| OpenAI | *(leave empty)* | `gpt-4o-mini` is ample for this workload |
| Groq | `https://api.groq.com/openai/v1` | Very fast, generous free tier |
| Together | `https://api.together.xyz/v1` | Open-weight models |
| OpenRouter | `https://openrouter.ai/api/v1` | Many models behind one key |
| Self-hosted vLLM | `http://your-host:8000/v1` | Keeps data on your infrastructure |

**Privacy trade-off, stated plainly.** Ollama keeps every document on your
own machine. Any hosted API means timetable and assignment text leaves your
infrastructure — worth a moment's thought before pointing a university
project at a third party. A shared Ollama host, or self-hosted vLLM, keeps
the local-only guarantee while removing the per-user install.

To keep inference local for everyone:

```ini
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://your-gpu-box:11434
```

---

## Putting it behind HTTPS

OAuth providers will not redirect to plain `http` on a public domain, so TLS
is required the moment you leave localhost. With Caddy:

```
campussync.example.edu {
    reverse_proxy /health      backend:8000
    reverse_proxy /auth/*      backend:8000
    reverse_proxy /sources/*   backend:8000
    reverse_proxy /tasks/*     backend:8000
    reverse_proxy /my/*        backend:8000
    reverse_proxy *            frontend:8501
}
```

Then update **both** OAuth registrations with the HTTPS redirect URIs, and
set `GOOGLE_REDIRECT_URI` / `MS_REDIRECT_URI` to match exactly.

---

## Operational notes

**Backups.** Everything that matters is in Postgres.

```bash
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U campussync campussync > backup-$(date +%F).sql
```

The `uploads` volume holds student documents and is worth backing up too.
The `cache` volume is derived data and can be discarded freely.

**Expired sessions** accumulate in `auth_session`. `purge_expired_sessions()`
clears them; call it from a periodic job, or accept slow growth — the rows
are tiny and lookups are indexed.

**Scaling.** Sessions are in the database, so multiple backend workers are
safe. The extraction cache is a local volume, so workers will each warm their
own copy; move `CACHE_DIR` to shared storage if that becomes wasteful.

---

## What is still missing for a real production service

Honest list, in the order I would tackle it:

1. **No rate limiting.** Nothing stops one account from generating plans in a
   loop and exhausting your API budget.
2. **No email verification.** Anyone can register any registration number,
   including one that is not theirs.
3. **No password reset.** A forgotten password currently means database
   surgery.
4. **No admin view.** No way to see who is registered or revoke access
   without SQL.
5. **No migrations.** Tables are created with `create_all`; a schema change
   in a future version needs Alembic, not a redeploy.
6. **Logs are not aggregated.** Fine for one box, painful beyond that.

None of these block a class-sized deployment among people who know each
other. All of them block a public service.

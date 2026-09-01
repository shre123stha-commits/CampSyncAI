# 🎓 CampusSync AI

![CI](https://github.com/shre123stha-commits/CampSyncAI/actions/workflows/ci.yml/badge.svg)

An AI academic planner. It reads a student's timetable and assignment
documents, works out when they are actually free, and generates a realistic,
deadline-aware study plan.

Instead of checking LMS, Teams and Google Classroom separately and scheduling
in their heads, students get one consolidated plan.

---

**[Architecture](docs/ARCHITECTURE.md)** · **[Deployment](docs/DEPLOYMENT.md)** · **[Demo runbook](DEMO.md)**
**Integrations:** [Google Classroom](docs/GOOGLE_CLASSROOM_SETUP.md) · [Microsoft Teams](docs/MICROSOFT_TEAMS_SETUP.md)

---

## Quick start

```bash
# 1. Install
make install

# 2. Make sure Ollama is running with the model pulled
ollama serve
ollama pull qwen2.5:3b

# 3. Run both services
make dev
```

| Service | URL |
|---|---|
| Frontend | http://localhost:8501 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

Demo accounts: `24BAI1127`, `24BCE1085`, `24BCS1028`, `24BEC1043`, `24BME1001`

### With Docker

```bash
docker compose up
```

### Configuration

Copy `.env.example` to `.env` and adjust. Everything (model names, Ollama URL,
college hours, log level, backend URL) is environment-driven.

---

## Planning modes

| Mode | Scope | Timings |
|---|---|---|
| `day_without_timings` | Today | No |
| `day_with_timings` | Today | Yes |
| `week_without_timings` | This week | No |
| `week_with_timings` | This week | Yes |

---

## Architecture

See **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for full diagrams —
system overview, the self-correcting loop, and the feedback sequence.

```
        Streamlit frontend
                │  HTTP (BACKEND_URL)
        FastAPI  /generate-plan
                │
        LangGraph pipeline
                │
  academic_agent → classroom_agent → planning_agent
        │                                  │
  docx + LLM extraction            LLM plan + validation ⟲
        │                                  │
  deterministic scheduler ───────────────┘
  (free slots, days remaining, priority)
```

### Design principle: deterministic where possible, LLM where necessary

Anything that can be computed is computed in Python, never trusted to the
model:

* `days_remaining` — parsed from the deadline and recomputed after generation
* `priority` — a pure function of `days_remaining` (0–3 High, 4–10 Medium,
  >10 Low)
* free slots — derived per day from the timetable
* whether a session fits a real free slot, whether a day is overloaded,
  whether timings are present in the right modes

The LLM's job is reading messy documents and composing a humane schedule.

### Accounts and data

Accounts are stored in SQLite with **bcrypt-hashed passwords chosen for this
app**. We never collect a university credential — see the data-sources table
below.

Tasks are persisted with a content **fingerprint** (subject + work + deadline),
which gives them a stable identity across re-extraction. Ticking a task off
therefore survives a document refresh, and re-reading a document never creates
duplicate rows. Completed tasks are excluded from new plans, so the planner
schedules only what is genuinely left.

Students can upload their own `.docx` timetable and LMS export; an upload
takes precedence over the bundled sample data.

### Caching

Document extraction costs two LLM calls and is **deterministic for a given
document**, so its result is cached on disk under `backend/.cache/`, keyed by
a fingerprint (name, size, mtime) of the source files. Editing a document
invalidates the entry automatically.

`days_remaining` is deliberately recomputed *after* the cache lookup, because
it depends on today's date — a cached value would be wrong the next morning.

The dashboard calls `GET /students/{reg_no}/tasks`, which skips planning
entirely. Warm, it responds in **~4ms** instead of 30–60s. Only the planner
buttons invoke the LLM, and their results are cached per mode in the session.

Clear the cache with the **Refresh data** button, `POST
/students/{reg_no}/refresh`, or by deleting `backend/.cache/`. Set
`CACHE_ENABLED=false` to disable it.

### Self-correcting generation

Every LLM boundary runs the same loop:

```
prompt → invoke → tolerant parse → schema validation
                → semantic validation → retry with the specific error
```

`utils/safe_json.py` strips markdown fences, `<think>` blocks and stray prose,
then extracts the first balanced JSON value. `scheduler/plan_validator.py`
checks the plan against the deterministic rules above. Failures are fed back
into the prompt rather than surfaced to the user.

---

## Project structure

```
CampSyncAI/
├── backend/
│   ├── api/main.py            # FastAPI app + error contract
│   ├── agents/                # academic · classroom · planning
│   ├── extractors/            # timetable + task extraction
│   ├── scheduler/             # study_slots · plan_validator
│   ├── models/                # Task · Lecture · FreeSlot · StudyPlan · enums
│   ├── prompts/
│   ├── utils/                 # safe_json · llm_json · doc_loader · formatters
│   ├── sources/               # pluggable adapters: docs · ICS · Classroom
│   ├── graph.py               # LangGraph wiring
│   └── config.py              # all env-driven configuration
├── frontend/
│   ├── views/                 # login · dashboard · sources (not `pages/`)
│   ├── components/            # plan_view · cards · deadline_text
│   └── api/                   # backend client
├── tests/                     # 324 tests, no LLM required
├── docker-compose.yml
├── Makefile
└── PROJECT_PLAN.md            # full engineering plan
```

---

## API

**Authenticated** (send `Authorization: Bearer <token>`):

| Endpoint | Purpose |
|---|---|
| `POST /auth/register` | Create an account |
| `POST /auth/login` | Sign in, returns a token |
| `POST /auth/logout` | Invalidate the token |
| `GET /auth/me` | Current account |
| `GET /tasks` | Tasks + timetable, **no planning step** (fast) |
| `PATCH /tasks/{id}` | Mark a task complete / incomplete |
| `POST /upload?kind=timetable\|lms` | Upload a `.docx` |
| `POST /refresh` | Invalidate the extraction cache |
| `POST /my/generate-plan` | Generate a plan, skipping completed tasks |
| `GET /sources` | Every source and its connection state |
| `POST /sources/ics` | Connect a calendar feed |
| `GET /sources/classroom/authorize` | Start Google OAuth |
| `DELETE /sources/{type}` | Disconnect and destroy the credential |

**Public:**

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness |
| `GET /students` | Registration numbers with sample documents |
| `POST /generate-plan` | Legacy sample-data planning |

```bash
curl -X POST http://localhost:8000/generate-plan \
  -H "Content-Type: application/json" \
  -d '{"registration_no": "24BAI1127", "mode": "day_with_timings"}'
```

### Error contract

| Condition | Status |
|---|---|
| Unknown student / task | `404` |
| Not signed in, bad or expired token | `401` |
| Registration number already taken | `409` |
| Upload too large | `413` |
| Invalid mode / empty reg no | `422` |
| Ollama unreachable | `503` |
| No valid plan after retries | `502` |
| No tasks found | `200` with empty `plan[]` |

No stack trace is ever reachable from the UI.

---

## Testing

```bash
make test
```

324 tests, ~26s, **no Ollama required** — the LLM is stubbed. Covers JSON
recovery from malformed model output, day-aware slot detection, deadline
parsing across 8 formats, plan validation rules, the retry loop, and every
API error path, plus the caching layer.

---

## Human-in-the-loop feedback

A generated plan is a suggestion, not an instruction. Every plan page has a
feedback box:

> *"I have football practice Friday evening, move that work earlier"*

The note is added to the planning prompt and the schedule is rebuilt around
it. What **cannot** change is the arithmetic: deadlines, days remaining and
priority bands are recomputed in Python after every generation, so a student
can ask for anything but cannot talk the system into misreporting a deadline.

Feedback is untrusted input, so it is capped at 500 characters and the
prompt's section delimiter is stripped before interpolation. There is a test
that feeds the model hostile feedback and asserts the computed values survive.

---

## Data sources

**We deliberately never
handle university passwords** — every integration is OAuth or a
student-generated, revocable token:

| Source | Mechanism | Status |
|---|---|---|
| Documents | Local `.docx` | ✅ Working |
| Upload | Student-supplied `.docx` | ✅ Working |
| ICS feed | Private calendar URL (encrypted at rest) | ✅ Working |
| Google Classroom | OAuth 2.0, read-only scopes | ✅ Working* |
| Microsoft Teams | OAuth 2.0, read-only + calendar fallback | ✅ Working† |
| Moodle / Canvas | Student-generated API token | Planned |

\* Requires `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`; the UI marks it
unavailable until they are set. See
[`docs/GOOGLE_CLASSROOM_SETUP.md`](docs/GOOGLE_CLASSROOM_SETUP.md) for a
step-by-step guide.

† Requires `MS_CLIENT_ID` / `MS_CLIENT_SECRET`. Microsoft marks *every*
education permission as admin-consent-only, so `EduAssignments.ReadBasic`
needs your university's Microsoft 365 administrator. The adapter falls back
to `Calendars.Read` — which a student can approve alone — so Teams deadlines
still arrive without an IT ticket. See
[`docs/MICROSOFT_TEAMS_SETUP.md`](docs/MICROSOFT_TEAMS_SETUP.md).

### How sources work

All adapters implement one `Source` protocol and normalise into the shared
`Task` model, so the planner never learns where data came from. The registry
fans out over every connected source and merges the results, de-duplicating
on (subject, work, deadline) with documents taking precedence.

**A failing source never breaks the request.** If a calendar feed 404s or the
AI service is down, the working sources still return their tasks and the
failure is reported in `source_errors` for the UI to show as a warning.

Credentials are encrypted at rest with Fernet, keyed on `SECRET_KEY`, and
destroyed on disconnect.

---

## Roadmap

See [`PROJECT_PLAN.md`](PROJECT_PLAN.md) for the full plan.

- [x] **Phase 0** — Unified repo, one-command startup, dead code removed
- [x] **Phase 1** — Reliability: JSON recovery, retry loop, error contract, tests
- [x] **Phase 2** — Day-aware scheduling + semantic validators
- [x] **Phase 3** — Extraction caching, sub-second warm dashboard
- [x] **Phase 4** — SQLite persistence, bcrypt auth, upload, task completion
- [x] **Phase 5** — Live sources (ICS, Google Classroom OAuth)
- [x] **Phase 6** — Human-in-the-loop feedback, architecture docs, demo runbook
- [x] **Phase 7** — Multi-user deployment (Postgres, hosted-model fallback,
      persistent sessions) and the Microsoft Teams source

---

## Tech stack

Python 3.12 · FastAPI · LangGraph · LangChain · Ollama (Qwen) · Pydantic ·
Streamlit · pytest

## License

Educational and research purposes.

# 🎓 CampusSync AI

![CI](https://github.com/shre123stha-commits/CampSyncAI/actions/workflows/ci.yml/badge.svg)

An AI academic planner. It reads a student's timetable and assignment
documents, works out when they are actually free, and generates a realistic,
deadline-aware study plan.

Instead of checking LMS, Teams and Google Classroom separately and scheduling
in their heads, students get one consolidated plan.

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
│   ├── sources/               # future: OAuth/ICS/Classroom adapters
│   ├── graph.py               # LangGraph wiring
│   └── config.py              # all env-driven configuration
├── frontend/                  # Streamlit
├── tests/                     # 91 tests, no LLM required
├── docker-compose.yml
├── Makefile
└── PROJECT_PLAN.md            # full engineering plan
```

---

## API

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness |
| `GET /students` | Registration numbers with documents on file |
| `GET /students/{reg_no}/tasks` | Tasks + timetable, **no planning step** (fast) |
| `POST /students/{reg_no}/refresh` | Invalidate the extraction cache |
| `POST /generate-plan` | Generate a study plan |

```bash
curl -X POST http://localhost:8000/generate-plan \
  -H "Content-Type: application/json" \
  -d '{"registration_no": "24BAI1127", "mode": "day_with_timings"}'
```

### Error contract

| Condition | Status |
|---|---|
| Unknown student | `404` |
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

120 tests, ~0.9s, **no Ollama required** — the LLM is stubbed. Covers JSON
recovery from malformed model output, day-aware slot detection, deadline
parsing across 8 formats, plan validation rules, the retry loop, and every
API error path, plus the caching layer.

---

## Data sources

Today the system reads `.docx` files from `backend/data/documents/`.

Planned integrations use the `sources/` adapter seam. **We deliberately never
handle university passwords** — every integration is OAuth or a
student-generated, revocable token:

| Source | Mechanism | Status |
|---|---|---|
| Documents | Local `.docx` | ✅ Working |
| Upload | Student-supplied files | Planned |
| ICS feed | Private calendar URL | Planned |
| Google Classroom | OAuth 2.0 + MCP | Planned |
| Moodle / Canvas | Student API token | Planned |

---

## Roadmap

See [`PROJECT_PLAN.md`](PROJECT_PLAN.md) for the full plan.

- [x] **Phase 0** — Unified repo, one-command startup, dead code removed
- [x] **Phase 1** — Reliability: JSON recovery, retry loop, error contract, tests
- [x] **Phase 2** — Day-aware scheduling + semantic validators
- [x] **Phase 3** — Extraction caching, sub-second warm dashboard
- [ ] **Phase 4** — SQLite persistence, bcrypt auth, upload, task completion
- [ ] **Phase 5** — Live sources (ICS, Google Classroom OAuth)
- [ ] **Phase 6** — Human-in-the-loop feedback, polish

---

## Tech stack

Python 3.12 · FastAPI · LangGraph · LangChain · Ollama (Qwen) · Pydantic ·
Streamlit · pytest

## License

Educational and research purposes.

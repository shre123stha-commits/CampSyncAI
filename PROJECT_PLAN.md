# CampusSync AI — Engineering Plan & Technical Assessment

> A complete review of the current codebase, the architecture we should converge on,
> and a phased plan to take this from working prototype to a finished product.
>
> Audience: the CampusSync AI team.
> Status of repo at time of writing: branch `arena/01a05b5e-campsyncai`, one commit on `main`.

---

## Table of Contents

1. [What the project is](#1-what-the-project-is)
2. [Current state — an honest audit](#2-current-state--an-honest-audit)
3. [Target architecture](#3-target-architecture)
4. [Data ingestion strategy (the big decision)](#4-data-ingestion-strategy-the-big-decision)
5. [Authentication & security](#5-authentication--security)
6. [Why LangGraph and no other agent framework](#6-why-langgraph-and-no-other-agent-framework)
7. [Making the system reliable](#7-making-the-system-reliable)
8. [Performance strategy](#8-performance-strategy)
9. [Data model & persistence](#9-data-model--persistence)
10. [Testing strategy](#10-testing-strategy)
11. [Repository restructure](#11-repository-restructure)
12. [Phased delivery plan](#12-phased-delivery-plan)
13. [Risk register](#13-risk-register)
14. [Definition of done](#14-definition-of-done)
15. [Demo runbook](#15-demo-runbook)

---

## 1. What the project is

CampusSync AI is an **AI academic planner**. A student identifies themselves, the system
gathers their academic obligations (timetable + assignments/quizzes/projects from various
platforms), works out when they are actually free, and asks an LLM to produce a realistic,
deadline-aware study plan in one of four modes:

| Mode | Scope | Timings |
|---|---|---|
| `day_without_timings` | Today | No |
| `day_with_timings` | Today | Yes |
| `week_without_timings` | This week | No |
| `week_with_timings` | This week | Yes |

The core insight — and the thing that makes the project worth building — is that students
currently check LMS, Teams, Google Classroom and a paper timetable separately, then do the
scheduling in their heads. We consolidate the sources and do the scheduling for them.

### The two codebases today

```
CampSyncAI/
├── CampusSync-AI/     # Python backend: LangGraph pipeline + FastAPI
└── FRONTIER/          # Streamlit frontend
```

They are currently independent projects that happen to share a repo. Unifying them is
Phase 0.

---

## 2. Current state — an honest audit

### 2.1 What genuinely works

This is a real, functioning prototype. The happy path runs end to end.

| Capability | File(s) | Notes |
|---|---|---|
| DOCX text extraction (paragraphs **and** tables) | `utils/doc_loader.py` | Clean, correct |
| Timetable extraction via LLM → `Lecture[]` | `extractors/timetable_extractor.py` | Works |
| Task extraction via LLM → `Task[]` | `extractors/task_extractor.py` | Works |
| Deterministic `days_remaining` in Python | `agents/academic_agent.py` | **Good call** — see below |
| Free-slot detection | `scheduler/study_slots.py` | Works, but day-blind (bug #6) |
| Four planning modes | `utils/mode_prompt.py` | Well written |
| Planning prompt | `prompts/planning_prompt.py` | Genuinely strong prompt engineering |
| LangGraph orchestration | `graph.py` | 3 active nodes, linear |
| FastAPI endpoint | `api/main.py` | Single `POST /generate-plan` |
| Streamlit UI: login, dashboard, 4 plan views | `FRONTIER/` | Looks good |
| Sample data for 5 registration numbers | `data/documents/` | Demo-ready |

**Worth calling out as good engineering:** the planning prompt explicitly instructs the LLM
*not* to recalculate `days_remaining`, and `planning_agent` then overwrites the LLM's value
with Python's computed value via a `(subject, work)` lookup. That is exactly the right
instinct — never let the model do arithmetic you can do deterministically. We should apply
that same principle more widely (see §7).

### 2.2 Bugs and weaknesses, by severity

#### 🔴 Critical — will break a live demo

**B1. Unguarded `json.loads` on LLM output — 3 occurrences.**
`agents/planning_agent.py:70`, `extractors/task_extractor.py:19`,
`extractors/timetable_extractor.py:16`.
Qwen frequently wraps JSON in ```` ```json ```` fences, and reasoning-tuned Qwen variants
emit `<think>...</think>` preambles. Any of these → `JSONDecodeError` → HTTP 500 → red
traceback in Streamlit. This is the single most likely thing to fail in front of an
audience. Fix: a shared `safe_json_parse()` + a validator retry loop (§7).

**B2. No error handling in the API.** An unknown registration number produces
`FileNotFoundError` → 500 with a stack trace. Any reg number outside the five sample files
breaks the app. Needs 404/422 with a friendly message.

**B3. Full LLM pipeline re-runs on every page view.** `show_dashboard()` calls
`generate_plan()` at the top of the function, and every planner button re-invokes the entire
graph — 3 sequential LLM calls (timetable extraction, task extraction, planning) each time.
Roughly 30–60s per interaction on local Ollama. This is the worst UX problem in the project
and it is entirely fixable by caching (§8).

**B4. Dashboard crashes on an empty plan.** `min(t["days_remaining"] for t in tasks)` raises
`ValueError` on an empty sequence, and `tasks[0]` raises `IndexError`. A student with no
pending assignments — a completely normal state — crashes the app.

#### 🟠 High — architectural correctness

**B5. `extract_study_slots` is day-blind.** It sorts *all* lectures for the whole week by
`start_time` only, then computes gaps between consecutive entries. This means it computes a
"free period" between Monday's last lecture and Tuesday's first. It also appends exactly one
`After College` slot, always attributed to `lectures[0].day`. Consequence: weekly plans are
built on incorrect availability data. Must group by day → compute intra-day gaps → append one
after-college slot per day.

**B6. Hardcoded backend URL.** `FRONTIER/frontend/api/backend_api.py` pins
`http://127.0.0.1:8000`. Breaks in Docker, in any hosted deployment, and in a preview
environment. Must be `os.getenv("BACKEND_URL", ...)`.

**B7. `state["study_plan"]` is an untyped dict.** `state.py` declares it as `StudyPlan`, but
`planning_agent` assigns a raw `dict`. The declared type is a lie, and there is no Pydantic
model describing the *actual* output shape (`{mode, plan[]}`). The API therefore has no
`response_model` and no output validation.

**B8. `mode` is an unvalidated free-form string.** Any typo silently falls through to
`get_mode_instruction`'s default ("Generate the best study plan"), producing an
unpredictable shape the frontend may not be able to render. Must be an `Enum` on the
request model.

**B9. `mcp/` package name shadows the official `mcp` PyPI package.** The moment we
`pip install mcp` for the Google Classroom work, imports become ambiguous. Rename now,
while it's free.

#### 🟡 Medium — hygiene and maintainability

**B10. Dead and empty files.** Empty: `app.py` (backend root), `api/planner_api.py`,
`rag/ingest.py`, `rag/retriever.py`, `rag/vectorstore.py`, `mcp/classroom_client.py`.
Orphaned older code path, no longer in the graph: `scheduler/planner.py`,
`agents/scheduling_agent.py`, `models/study_plan.py`. Duplicate logic:
`scheduler/timetable.py` overlaps `scheduler/study_slots.py`. `agents/formatter_agent.py`
is commented out of the graph *and* would crash if enabled (it does
`state["study_plan"].tasks` on what is now a dict).

**B11. `test/` contains scripts, not tests.** Zero `assert` statements. They execute work at
import time, so `pytest` would trigger real LLM calls on collection. There is no CI signal.

**B12. `FRONTIER` has no dependency file** despite its README instructing
`pip install -r requirements.txt`.

**B13. Debug `print` throughout the agents**, including `print(state)` in `academic_agent`
and the entire prompt in `planning_agent`. Fine for development, but this is exactly the
kind of logging that leaks credentials once real integrations land. Move to the `logging`
module with levels.

**B14. Login is cosmetic.** Any non-empty string authenticates. No password, no session, no
authorisation — student A could request student B's plan by typing their reg number.

**B15. Unused heavy dependencies.** `faiss-cpu`, `sentence-transformers`, `pymupdf`,
`google-api-python-client`, `google-auth*` are all declared and none are imported. They
significantly slow `uv sync` for zero current benefit.

**B16. `bare except`** in `academic_agent`'s date parsing swallows every error including
`KeyboardInterrupt`. Should be `except (ValueError, TypeError)`.

**B17. No `mode` propagation guarantee.** `planning_agent` sets `study_plan["mode"]` from
state after parsing, which is correct — but if the LLM omits the `plan` key entirely, the
subsequent `for item in study_plan["plan"]` raises `KeyError`. Covered by the schema
validation fix.

### 2.3 Not built at all

- Google Classroom integration (`classroom_agent` returns `[]`)
- Any live data source whatsoever (§4)
- RAG layer (four empty files)
- Real authentication / multi-user isolation
- Document upload — files are placed manually into `data/documents/`
- Persistence — nothing is stored; every run starts from zero
- Task completion tracking
- Notifications, calendar sync, analytics
- Deployment: no Dockerfile, no CI, no single-command startup

---

## 3. Target architecture

```
                        ┌──────────────────────────┐
                        │   Streamlit Frontend     │
                        │  login · dashboard ·     │
                        │  connect sources · plans │
                        └───────────┬──────────────┘
                                    │ HTTP (BACKEND_URL)
                        ┌───────────▼──────────────┐
                        │      FastAPI Layer       │
                        │  /auth  /sources  /plan  │
                        │  Pydantic in & out       │
                        └───────────┬──────────────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │       LangGraph Pipeline       │
                    │                                │
                    │  ingest → normalise → schedule │
                    │     → plan → validate ⟲        │
                    └───────────────┬────────────────┘
                                    │
        ┌───────────────────────────┼────────────────────────┐
        │                           │                        │
┌───────▼────────┐        ┌─────────▼────────┐     ┌─────────▼────────┐
│ Source Adapters│        │  Deterministic   │     │   LLM (Ollama)   │
│                │        │     Scheduler    │     │                  │
│ DocumentSource │        │                  │     │  extraction  ·   │
│ ICSSource      │        │ free slots ·     │     │  planning    ·   │
│ ClassroomSource│        │ days_remaining · │     │  reflection      │
│ MoodleSource   │        │ conflict checks  │     │                  │
└───────┬────────┘        └──────────────────┘     └──────────────────┘
        │
┌───────▼────────────────────────────────────────────┐
│  SQLite (SQLModel): students · tasks · plans ·     │
│  source_connections · extraction_cache             │
└────────────────────────────────────────────────────┘
```

### Guiding principles

1. **Deterministic where possible, LLM where necessary.** Dates, gaps, conflicts, priority
   thresholds → Python. Understanding messy documents and composing a humane schedule → LLM.
   The existing `days_remaining` override is the model for this.
2. **Every source normalises to one internal `Task` model.** Adding a platform must never
   require touching the planner.
3. **Never accept a university password.** See §5.
4. **Every LLM boundary is schema-validated with a retry.** No raw `json.loads`.
5. **Cache aggressively.** Extraction is deterministic per document; only planning needs to
   be fresh.

---

## 4. Data ingestion strategy (the big decision)

### 4.1 Where we actually are

There is **no scraping and no live integration** in the codebase. There is no HTTP client, no
Selenium/Playwright, no session handling. `academic_agent` resolves
`TIMETABLE_DIR / f"{reg_no}.docx"` against five pre-placed sample files. The "login" is a
file lookup. `classroom_agent` is a stub that returns `[]`.

This is fine for a prototype, but the README currently implies live LMS/Teams/Classroom
sync, and it should be corrected until it's true.

### 4.2 Options evaluated

| Approach | Verdict | Reasoning |
|---|---|---|
| **Headless-browser scraping with student passwords** | ❌ Reject | Requires the student's full university credential in plaintext; breaks on SSO/MFA; violates most campus IT policy; brittle against UI changes; bulk logins from one IP resemble credential stuffing. See §5. |
| **Official REST APIs (Moodle / Canvas)** | ✅ Adopt where available | Token-based, revocable, stable, documented. Student generates their own token from their profile page — **we never see a password**. |
| **Private ICS calendar feed** | ✅ Adopt — highest ROI | Nearly every LMS exposes a personal iCal URL of deadlines. One `requests.get` + the `icalendar` library. ~30 lines for full deadline coverage, zero auth code. |
| **Google Classroom / MS Graph via OAuth** | ✅ Adopt | The only supported path — both vendors have removed programmatic password access entirely. Scoped, revocable tokens. |
| **Student-uploaded documents / screenshots** | ✅ Keep as the universal fallback | Already built. Works at *any* university, needs no credentials and no IT approval, and cannot break. This is a genuine strength of the LLM-extraction architecture. |

### 4.3 The adapter pattern

```python
class Source(Protocol):
    name: str
    def is_connected(self, student_id: str) -> bool: ...
    def fetch_tasks(self, student_id: str) -> list[Task]: ...
    def fetch_lectures(self, student_id: str) -> list[Lecture]: ...
```

Concrete adapters, in build order:

1. `DocumentSource` — wraps the existing docx path. **Already works**, just needs the interface.
2. `UploadSource` — same extraction, but the student uploads instead of us pre-placing.
3. `ICSSource` — paste a calendar URL. Cheapest real integration.
4. `ClassroomSource` — OAuth + MCP tool calling. The marquee feature.
5. `MoodleSource` / `CanvasSource` — student-supplied API token, only if the campus runs one.

The ingest node fans out over all connected sources, merges and de-duplicates into
`list[Task]`, and the rest of the pipeline is unchanged. This is the seam `classroom_agent`
already occupies — the architecture is well positioned for it.

The "Connect your accounts" UI is identical either way. The only difference is what each
card collects: an OAuth redirect or a revocable token, never a password.

---

## 5. Authentication & security

### 5.1 The proposal on the table

> Ask for the college username and password at login, and later for LMS / Teams / Google
> Classroom credentials inside the app.

### 5.2 Why we should not do this

**For Google and Microsoft it does not work at all.** Both have removed programmatic
password authentication. Driving `accounts.google.com` from a headless browser trips
automation detection ("This browser or app may not be secure") and stops. Microsoft Graph is
OAuth-only, and university tenants typically enforce Conditional Access + MFA. The password
approach here isn't a tradeoff — it's a broken implementation of the OAuth flow we already
planned.

**For the campus SSO credential it is dangerous precisely because it might work:**

- **Blast radius.** That one password usually unlocks email, grades, exam registration, fees,
  and personal records — not just assignments.
- **It cannot be stored safely.** Re-fetching data daily requires the password in
  *reversibly decryptable* form. No hashing. That means a real KMS, key rotation, an audit
  log, and an encrypted store. One leaked `.env`, or one `print(state)` — and we have
  several debug prints today (B13) — dumps live credentials to a log.
- **It trains students to be phished.** Once typing the university password into a
  third-party site feels normal, the next lookalike site succeeds too.
- **Institutional risk.** Most Indian university IT policies explicitly prohibit sharing
  credentials with third-party applications. Automated bulk logins from a single IP look
  like an attack. Realistic outcomes: IP block, disciplinary action, or takedown — and if an
  account is later compromised, the logs point at us.
- **Legal.** Under India's DPDP Act this makes us a data fiduciary with real consent,
  purpose-limitation and breach-notification obligations.
- **Fragility.** SSO redirect chains, CAPTCHAs, session expiry, MFA prompts, and a portal
  redesign every semester.

### 5.3 What we do instead

| Layer | Decision |
|---|---|
| **App login** | Our own account: email/reg-no + password, hashed with `bcrypt` in our DB. Real session tokens. Fixes B14 without touching university credentials. |
| **Google Classroom** | OAuth 2.0 — student authenticates on Google's own page; we receive a scoped, revocable token. |
| **Teams / Outlook** | Microsoft Graph OAuth, same model. |
| **Moodle / Canvas** | Student pastes a **self-generated API token**. Scoped and revocable — not a password. |
| **Generic deadlines** | Private ICS URL. |
| **Universal fallback** | Document upload → existing LLM extraction. |
| **Token storage** | Encrypted at rest, per-user, with an explicit "Disconnect" that deletes them. |

This is the same product experience with none of the liability. It is also a **stronger
answer under questioning**: *"we deliberately never handle university passwords — every
integration is OAuth or a revocable, scoped token"* is a mature security posture. *"we store
their college password encrypted"* is not.

**Interim option:** if the goal is simply a polished login screen for the demo, build the
username/password form now against our own bcrypt-hashed user table. Full UX, zero risk, and
it becomes the real auth system later.

---

## 6. Why LangGraph and no other agent framework

**We do not need CrewAI, AutoGen, or any additional orchestration library. LangGraph is
already the agentic layer, and it is the more appropriate choice.**

We have a `StateGraph`, a typed `PlannerState`, and nodes passing state — that *is*
multi-agent orchestration. Adding CrewAI would mean running two orchestrators in one process.

More importantly, consider what CrewAI would buy. Its value proposition is autonomous
role-playing agents that delegate to one another and decide their own execution order. Our
workflow is:

```
academic → classroom → planning → END
```

Fixed, deterministic, linear. No delegation, no dynamic routing, no negotiation. Wrapping it
in CrewAI adds non-determinism, extra LLM round-trips, and latency to a pipeline whose
primary weakness is *already* that it takes 30–60s (B3). We would make it slower and less
reliable in exchange for a buzzword.

**"Agentic" is a property of behaviour, not a dependency in `pyproject.toml`.** The defensible
claim rests on reasoning under constraints, tool use, and multi-step stateful control flow.

### What we build in LangGraph to make that claim airtight

| Feature | Why it's genuinely agentic | Phase |
|---|---|---|
| **Validator retry loop** | Planner output is schema-checked *and* semantically checked (no task scheduled past its deadline, no slot collision with a lecture, no day overloaded). On failure, route back to `planning_agent` with the specific error appended. A real self-correcting cycle — and it simultaneously kills B1. | 1 |
| **Conditional edges** | Skip `classroom_agent` when no account is connected; skip extraction entirely on a cache hit; branch on mode. Dynamic control flow, not a fixed chain. | 2 |
| **Reflection node** | A second LLM pass critiques the plan ("is Wednesday overloaded? does anything miss a deadline?") and triggers regeneration if it fails. The most demo-impressive single addition available, and CrewAI would not do it better. | 3 |
| **MCP tool calling** | The model choosing to invoke `list_coursework` is textbook tool-using agency. | 5 |
| **Human-in-the-loop** | LangGraph `interrupt()` — student rejects a plan, adds feedback, graph resumes and regenerates. | 6 |

**Decision: add zero new frameworks.** Invest that effort in the validator loop and the
reflection node instead.

### On the RAG layer

Recommend **deleting `rag/`** rather than filling it in. The documents are small and are
already extracted into structured objects; vector search would add latency and failure modes
for no gain in the planning use case. If we want RAG later, the honest use case is a *chat
assistant over course materials* ("explain this assignment's rubric"), which is a separate
feature — not part of the planner. Removing it also lets us drop `faiss-cpu` and
`sentence-transformers` (B15).

---

## 7. Making the system reliable

### 7.1 Two-layer LLM output handling

**Layer 1 — tolerant parsing.** A shared utility used by all three call sites:

```python
def safe_json_parse(raw: str) -> Any:
    # strip <think>...</think>, strip ``` fences,
    # slice from the first { or [ to its matching close,
    # then json.loads
```

**Layer 2 — schema validation + retry.** Parse into Pydantic. On `ValidationError`, re-invoke
once with the error message appended to the prompt. Only then fail. Where the model supports
it, prefer `llm.with_structured_output(Schema)` and let LangChain enforce the shape.

This converts B1 from "demo-ending crash" to "occasionally one second slower".

### 7.2 Semantic validation — deterministic, not LLM

After a plan parses, verify in Python:

- every scheduled item's day/time falls inside a real free slot
- nothing is scheduled after its own deadline
- no session collides with a lecture
- `priority` matches the `days_remaining` thresholds (0–3 High, 4–10 Medium, >10 Low)
- for `*_without_timings` modes, `start_time`/`end_time` are empty strings
- total scheduled hours per day are under a configurable cap

Violations feed the retry loop. This is where the project earns real credibility: the LLM
proposes, deterministic code disposes.

### 7.3 Error handling contract

| Condition | Response |
|---|---|
| Unknown student | `404` + message |
| Invalid mode | `422` (Enum validation) |
| Ollama unreachable | `503` + "AI service unavailable" |
| LLM output invalid after retry | `502` + "Could not generate a valid plan, please retry" |
| No tasks found | `200` with empty `plan[]` — frontend renders a friendly empty state (fixes B4) |

Frontend wraps every call in try/except and renders `st.error` instead of a traceback.

---

## 8. Performance strategy

Current: ~30–60s per interaction, three sequential LLM calls, repeated on every page view.

| Optimisation | Effect |
|---|---|
| **Cache extraction results** keyed by `(reg_no, file mtime/hash)` in SQLite | Removes 2 of 3 LLM calls on every request after the first. The single biggest win. |
| **Cache generated plans** in `st.session_state`, keyed by `(student, mode, date)` | Navigating back to the dashboard becomes instant. |
| **Explicit Refresh button** | Users get freshness on demand instead of paying for it always. |
| **Don't auto-generate on dashboard load** | Show cached tasks + metrics immediately; generate a plan only when asked. |
| **Parallel source fetching** | Once multiple adapters exist, fan out concurrently. |
| **Stream the planning response** | Perceived latency drops even when wall-clock doesn't. |
| **Smaller extraction model** | Extraction is mechanical; a 3B model is fine. Reserve the larger model for planning. |

Target: dashboard < 1s warm, plan generation < 15s.

---

## 9. Data model & persistence

SQLite + SQLModel — zero-ops, and a single file we can ship with the demo.

| Table | Purpose |
|---|---|
| `student` | id, reg_no, name, `password_hash` (bcrypt), created_at |
| `source_connection` | student_id, source_type, encrypted token/URL, status, last_synced |
| `lecture` | student_id, day, start, end, subject |
| `task` | student_id, subject, task_type, platform, deadline, work, days_remaining, **completed**, source_id |
| `study_plan` | student_id, mode, generated_at, JSON payload |
| `extraction_cache` | source fingerprint → extracted JSON |

Model changes needed:
- Add a proper `StudyPlanResponse` / `PlannedItem` Pydantic pair matching the *actual*
  `{mode, plan[]}` output, and use it as the FastAPI `response_model` (fixes B7).
- Retire the legacy `models/study_plan.py` (`StudyPlan`/`PlannedTask`) with the old scheduler
  path (B10).
- Add `ModeEnum` (fixes B8).
- Consider `deadline` as a real `date` rather than a string, with the display format handled
  at the edge.

Persistence unlocks the feature that turns a demo into a product: **marking tasks complete**,
and plans that adapt to what's already done.

---

## 10. Testing strategy

Replace the current script-style `test/` (B11) with real pytest.

**Fast, deterministic, no LLM — the CI gate:**
- `study_slots`: day grouping, gap detection, the <30min rule, empty input, single lecture,
  back-to-back lectures, per-day after-college slots — this is where B5 gets locked down
- `days_remaining` arithmetic, including malformed dates
- `safe_json_parse`: fenced JSON, `<think>` preambles, trailing prose, arrays vs objects
- semantic plan validators
- Pydantic model round-trips

**Contract tests with a mocked LLM:** stub `llm.invoke` with recorded fixtures and assert the
graph produces a valid plan — full pipeline coverage in milliseconds.

**Integration tests (marked, opt-in):** real Ollama, run manually, not in CI.

Add GitHub Actions: lint (`ruff`) + `pytest` on push. A green badge is worth real marks in an
academic review.

---

## 11. Repository restructure

```
CampSyncAI/
├── backend/                    # was CampusSync-AI/
│   ├── api/
│   │   ├── main.py             # app factory, CORS, error handlers
│   │   └── routes/             # auth · sources · plans
│   ├── agents/                 # ingest · plan · validate · reflect
│   ├── sources/                # was mcp/ — adapters (fixes B9)
│   ├── extractors/
│   ├── scheduler/              # single module, day-aware (fixes B5)
│   ├── models/
│   ├── prompts/
│   ├── utils/                  # + safe_json.py, logging
│   ├── db/
│   ├── graph.py
│   └── config.py
├── frontend/                   # was FRONTIER/
│   ├── api/                    # BACKEND_URL from env (fixes B6)
│   ├── components/
│   ├── pages/
│   ├── styles/
│   ├── app.py
│   └── requirements.txt        # fixes B12
├── tests/
├── data/
├── docker-compose.yml
├── Makefile
├── .env.example
├── PROJECT_PLAN.md
└── README.md
```

Deletions: `rag/` (§6), `scheduler/planner.py`, `agents/scheduling_agent.py`,
`agents/formatter_agent.py`, `scheduler/timetable.py`, empty `app.py`, `api/planner_api.py`,
`mcp/classroom_client.py`, and the unused heavy dependencies (B15).

---

## 12. Phased delivery plan

Each phase is independently shippable and leaves the repo in a demoable state.

### Phase 0 — Unify (½ day)
Merge into `backend/` + `frontend/`. `docker-compose up` or `make dev` starts both.
`BACKEND_URL` from env. Frontend dependency file. Delete dead code. Rename `mcp/` → `sources/`.
Drop unused deps.
**Exit:** one command, clean tree.

### Phase 1 — Unbreakable (1–2 days) ← *highest value*
`safe_json_parse` + validator retry on all three LLM boundaries. `StudyPlanResponse` as
`response_model`. `ModeEnum`. Full error-handling contract. Frontend try/except + empty
states. `logging` replaces `print`. Fix the bare `except`.
**Exit:** B1, B2, B4, B7, B8, B13, B16 closed. No traceback is reachable from the UI.

### Phase 2 — Correct scheduling (½ day)
Rewrite `extract_study_slots` day-aware. Configurable college hours. Semantic validators.
Real pytest suite + CI.
**Exit:** B5 closed, green CI.

### Phase 3 — Fast (1 day)
Extraction cache. Plan caching in session. Refresh button. Dashboard stops auto-generating.
Optional: reflection node.
**Exit:** B3 closed. Warm dashboard < 1s.

### Phase 4 — Real app (2 days)
SQLite + SQLModel. bcrypt login (B14). Document upload. Task completion tracking.
**Exit:** multi-user, data survives restart, students can tick tasks off.

### Phase 5 — Live integrations (2–3 days)
`Source` protocol formalised. `ICSSource` first (cheapest). Then Google Classroom OAuth +
MCP. "Connect accounts" page. Encrypted token storage with Disconnect.
**Exit:** at least one live source; the multi-source story is true.

### Phase 6 — Polish (1–2 days)
Human-in-the-loop plan feedback. Architecture diagram. Screenshots. Accurate README.
`DEMO.md`. Optional: analytics, notifications, calendar export.

**Critical path to a strong demo: Phases 0–3 (~4 days).** Everything after that is depth.

---

## 13. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM emits invalid JSON mid-demo | High | Critical | Phase 1 parse + retry; pre-warm cache before demoing |
| Ollama slow/unavailable on demo machine | Medium | Critical | Cache + a `DEMO_MODE` env flag serving a recorded plan |
| Google OAuth verification delays | Medium | Medium | Test users during development; ICS as the fallback live source |
| Scope creep into RAG/mobile/notifications | High | Medium | Phases 0–3 are non-negotiable; the rest is optional |
| University IT objection | Low (if we follow §5) | High | No password handling; OAuth/tokens only |
| Model output quality varies by machine | Medium | Medium | Pin the model+version; keep temperature at 0 |

---

## 14. Definition of done

- [ ] `make dev` starts backend + frontend
- [ ] No unhandled exception reachable from the UI
- [ ] Unknown reg-no, empty task list, and Ollama-down all render friendly states
- [ ] All four modes produce schema-valid, semantically-valid plans
- [ ] Free slots are computed per-day and correctly
- [ ] Warm dashboard < 1s; plan generation < 15s
- [ ] pytest suite green in CI, no LLM required
- [ ] Multi-user with hashed passwords; no university credential is ever collected
- [ ] At least one live source (ICS or Classroom) working
- [ ] Tasks can be marked complete and persist
- [ ] README matches reality; architecture diagram present
- [ ] `DEMO.md` runbook rehearsed end to end

---

## 15. Demo runbook

1. **Pre-warm** the extraction cache for the demo student before presenting.
2. Log in → dashboard renders **instantly** from cache (metrics, tasks, today's focus).
3. Show **"Connect Accounts"** — explain OAuth/token-only, never passwords. This is a
   credibility moment, not a filler slide.
4. Generate **Today with Timings** live — narrate the free-slot detection while it runs.
5. Show the **validator loop** in the logs catching and correcting a bad plan. This is the
   proof that it's engineered, not just prompted.
6. Mark a task complete → regenerate → the plan adapts.
7. Close on the architecture diagram: pluggable sources, deterministic scheduler, LLM for
   judgement, self-correcting graph.

---

## Summary

The prototype is real and the core idea is sound. The prompt engineering is good, and the
decision to compute `days_remaining` in Python rather than trusting the model is exactly the
right instinct — we should extend that principle across the system.

What holds it back is not missing features. It is **reliability** (unguarded LLM parsing),
**speed** (no caching), **correctness** (day-blind slot detection), and **an ingestion story
that doesn't yet exist**. Phases 0–3 address all four in roughly four days and would leave a
genuinely impressive, robust system.

On the two open questions:

- **Data ingestion:** do not scrape with passwords. Adopt the source-adapter pattern —
  upload (built) → ICS (cheap) → OAuth Classroom (impressive). Same UX, no liability, and
  it actually works.
- **Agent framework:** add nothing. LangGraph already provides it. Spend the effort on the
  validator loop and reflection node, which make the "agentic" claim defensible in a way
  that importing CrewAI never would.

# Architecture

CampusSync AI turns a student's scattered academic obligations into a
realistic study plan. The design principle throughout: **the LLM is used for
language, never for arithmetic or guarantees.**

---

## 1. System overview

```mermaid
graph TB
    subgraph Browser
        UI[Streamlit UI<br/>login · dashboard · plans · sources]
    end

    subgraph Backend["FastAPI backend"]
        API[REST API<br/>21 routes]
        GRAPH[LangGraph pipeline]
        DB[(SQLite<br/>students · tasks<br/>plans · connections)]
    end

    subgraph Sources["Data sources"]
        DOCS[.docx documents<br/>timetable + LMS]
        ICS[Calendar feed<br/>Moodle · Canvas · Google]
        GC[Google Classroom<br/>OAuth]
    end

    LLM[Ollama<br/>local LLM]

    UI -->|token auth| API
    API --> GRAPH
    API --> DB
    GRAPH --> LLM
    DOCS --> GRAPH
    ICS --> API
    GC --> API

    style LLM fill:#4a3f6b,color:#fff
    style DB fill:#2d4a3e,color:#fff
```

Nothing leaves the machine except calls the student explicitly connects. The
model runs locally via Ollama, so no academic data reaches a third-party API.

---

## 2. The planning pipeline

```mermaid
graph LR
    START([Request]) --> A[academic_agent<br/>extract from .docx]
    A --> C[classroom_agent<br/>merge live sources]
    C --> P[planning_agent<br/>generate schedule]
    P --> END([Study plan])

    A -.cached.-> CACHE[(extraction<br/>cache)]

    style P fill:#4a3f6b,color:#fff
```

Three LangGraph nodes. Extraction is cached because it is the expensive step —
a warm dashboard renders in under a second, while a cold extraction costs two
LLM calls.

---

## 3. The self-correcting loop

This is the part that makes an unreliable model usable.

```mermaid
graph TD
    P[Build prompt] --> LLM[Invoke LLM]
    LLM --> PARSE{Valid JSON?}
    PARSE -->|no| RETRY
    PARSE -->|yes| SCHEMA{Matches schema?}
    SCHEMA -->|no| RETRY
    SCHEMA -->|yes| SEM{Semantically valid?<br/>slots · priorities · timings}
    SEM -->|no| RETRY[Feed the specific<br/>error back into<br/>the prompt]
    SEM -->|yes| OK([Accept])
    RETRY --> LLM

    RETRY -.exhausted.-> RELAX[Accept schema-valid plan<br/>rather than failing]

    style SEM fill:#6b3f3f,color:#fff
    style OK fill:#2d4a3e,color:#fff
```

The model is never trusted. Every plan is checked against rules Python can
verify, and a failure is fed back as a specific correction rather than a
blind retry.

---

## 4. What the LLM is *not* allowed to decide

| Value | Who decides | Why |
|---|---|---|
| Days remaining | `compute_days_remaining()` | Date arithmetic is exact; models drift |
| Priority band | `expected_priority()` | Pure function of days remaining |
| Free study slots | `extract_study_slots()` | Derived from the real timetable |
| Task completion | The student | Never inferred |
| Deadline | The source document/feed | Copied verbatim, never reworded |

After every generation, `_reconcile()` **overwrites** the model's values for
these fields with Python's. A student can type "mark everything low priority"
as feedback and the priorities will not change — there is a test asserting
exactly that.

---

## 5. Human-in-the-loop feedback

```mermaid
sequenceDiagram
    participant S as Student
    participant UI as Streamlit
    participant API as FastAPI
    participant AG as planning_agent
    participant LLM as Ollama

    S->>UI: "I have practice Friday evening"
    UI->>API: POST /my/generate-plan {feedback}
    API->>AG: state.feedback
    AG->>AG: sanitise_feedback()
    AG->>LLM: prompt + feedback block
    LLM-->>AG: revised plan
    AG->>AG: validate + reconcile
    AG-->>UI: plan honouring the request
    UI-->>S: rebuilt schedule
```

Feedback is untrusted input interpolated into a prompt, so it is capped at 500
characters and the prompt's section delimiter is stripped — a student cannot
forge a new instruction block. This is defence in depth: even if the text did
influence the model, the deterministic reconciliation in §4 still holds.

---

## 6. Data sources

All adapters implement one `Source` protocol returning `(lectures, tasks)`.
The planner never learns where a task came from.

| Source | Auth | Status |
|---|---|---|
| `.docx` documents | none | Built in |
| Upload | app login | Built in |
| Calendar feed (ICS) | student-pasted revocable URL | Built in |
| Google Classroom | OAuth, two read-only scopes | Requires credentials |

**No adapter ever accepts a university password.** Secrets are encrypted at
rest with Fernet, never hashed — they must be replayable to re-sync — and are
destroyed on disconnect.

**A failing source never blocks the others.** Errors surface as `source_errors`
on the response while every healthy source still renders.

---

## 7. Request flow, end to end

```mermaid
sequenceDiagram
    participant B as Browser
    participant F as Streamlit
    participant A as FastAPI
    participant D as SQLite
    participant G as LangGraph

    B->>F: Sign in
    F->>A: POST /auth/login
    A->>D: bcrypt verify
    A-->>F: session token

    B->>F: Open dashboard
    F->>A: GET /tasks
    A->>D: stored tasks + completions
    A->>A: fetch connected sources
    A-->>F: merged tasks + any source_errors

    B->>F: Generate plan
    F->>A: POST /my/generate-plan
    A->>D: completed fingerprints
    A->>G: invoke(state)
    G-->>A: validated plan
    A->>D: save plan
    A-->>F: study plan
```

Completed tasks are excluded by **fingerprint**, so ticking something off
survives a re-sync from a live feed without duplicating or resurrecting it.

---

## 8. Layout

```
backend/
  agents/      LangGraph nodes
  sources/     pluggable data adapters
  scheduler/   slot extraction, plan validation
  extractors/  .docx parsing
  prompts/     LLM prompt templates
  models/      Pydantic schemas
  db/          SQLModel tables, repository, crypto
  api/         FastAPI routes
frontend/
  views/       login, dashboard, sources
  components/  reusable rendering
  api/         backend client
tests/         292 tests, no LLM or network required
```

`views/` is deliberately not named `pages/` — Streamlit would turn that into
automatic navigation and expose internal modules as clickable pages.

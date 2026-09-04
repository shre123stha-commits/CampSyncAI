# Demo runbook

A rehearsed 8-minute walkthrough of CampusSync AI, plus the failure drills.

---

## Before you present

Work through this the day before, not five minutes before.

- [ ] `git pull` — you are on the latest commit
- [ ] Ollama is running: `ollama list` shows your model
- [ ] Backend starts and logs `Application startup complete.`
- [ ] Frontend loads the login page
- [ ] **Pre-warm the cache** — generate a plan once for your demo student. The
      first extraction costs two LLM calls; every later request is instant.
- [ ] Register your demo account so you are not typing a password on stage
- [ ] Connect a calendar feed if you are showing live sources
- [ ] `pytest` is green: `cd backend && uv run pytest ../tests -q`

### Starting up

**Terminal 1**
```bash
cd backend
uv run uvicorn api.main:app --port 8000 --reload
```

**Terminal 2**
```bash
streamlit run frontend/app.py --server.port 8501
```

On Windows without `make`, those two commands are exactly what `make backend`
and `make frontend` run.

---

## The 8-minute script

### 1 · The problem (45 seconds)

> "A student's deadlines live in four places: a timetable document, the LMS,
> Google Classroom, and a WhatsApp group. Nobody holds all of it. Work gets
> missed because it was invisible, not because it was hard."

Do not open the app yet. Let the problem land.

### 2 · Sign in (30 seconds)

Log in as your demo student.

**Point at the banner:**

> "This password is CampusSync's own. We never ask for a university password —
> that was a deliberate decision, and I will come back to it."

### 3 · The dashboard (90 seconds)

Show the task list.

- Deadlines with **days remaining and a priority colour**
- Point out an overdue item: *"overdue by 4 days"* — real, not a rounding bug
- Tick a task complete → it greys out

> "Completion is stored by fingerprint. When the calendar re-syncs in a
> minute, this stays ticked and does not duplicate."

### 4 · Connect a live source (90 seconds)

Go to **Connect accounts**. Paste a Moodle calendar URL.

> "This is a revocable, read-only link the student generates themselves. No
> password, no scraping, no IT approval. Revoke it in Moodle and we lose
> access instantly."

Connect → tasks appear. Return to the dashboard: the ticked task is still
ticked.

### 5 · Generate a plan (2 minutes) ← **the centrepiece**

Pick **Weekly Timed Study Plan**.

While it generates:

> "It is reading the real timetable, finding genuine free periods between
> lectures, and scheduling around them. Deadlines and priorities are computed
> in Python — the model only decides wording and arrangement."

When it lands, walk one card: subject, slot, deadline, priority, reason.

### 6 · Human-in-the-loop (90 seconds) ← **the differentiator**

Open **"Not quite right? Tell the planner what to change"**.

Type something real:

> `I have football practice Friday evening, move that work earlier`

Click **Rebuild my plan**.

> "The plan is a suggestion, not an instruction. But notice what did *not*
> change — the deadlines and priority bands are identical. Those are computed
> in Python and reconciled after every generation. A student can ask for
> anything; they cannot talk the system into lying about a deadline."

That distinction is the strongest single point in the demo.

### 7 · Close (45 seconds)

> "Four sources behind one interface, a local model so nothing leaves the
> machine, 301 tests that run without an LLM or a network, and a hard rule
> that we never touch a university credential."

---

## Failure drills

Rehearse these. Something will go wrong.

### Ollama is down or slow

**Symptom:** *"The AI service is unavailable."*

**Recover:** The dashboard still works — tasks, completion and calendar
sources are all independent of the LLM. Say so plainly:

> "The planner needs the local model, which isn't up on this machine. Notice
> the rest of the app degraded honestly instead of showing a blank page — one
> dead dependency doesn't take the product down."

That is a genuine engineering point, not a save.

### A source fails mid-demo

**Symptom:** a warning banner naming the source.

**Say:** *"One source is unreachable and the others carried on. That is
deliberate — there is a regression test for it."*

### Certificate error on a university LMS

**Symptom:** *"Could not verify the security certificate…"*

**Cause:** some university servers omit an intermediate certificate.
`pip install truststore` fixes it. Have the feed **already connected** before
presenting so this never appears.

### Plan generation is slow

Pre-warming prevents this. If it still drags, narrate the pipeline —
extraction, merge, planning, validation — rather than watching a spinner.

---

## Questions you will be asked

**"Why not just collect their LMS password?"**

> Google and Microsoft block password authentication outright, so it would not
> even work for two of the four sources. Beyond that, storing a reusable
> university password means storing it reversibly, and it trains students to
> hand credentials to any app that asks. We use OAuth, revocable URLs and
> uploads instead. It is the same reason no bank asks for your email password.

**"What stops the AI from hallucinating a deadline?"**

> It never sets one. Deadlines are copied verbatim from the source and
> overwritten in Python after generation, along with days remaining and
> priority. There is a test that feeds the model hostile input and asserts the
> computed values survive.

**"Does this send student data to OpenAI?"**

> No. The model runs locally through Ollama. Nothing leaves the machine except
> requests to sources the student explicitly connected.

**"What happens when the LLM returns malformed JSON?"**

> It is parsed tolerantly, validated against a schema, then checked
> semantically — do sessions fit real free slots, are priorities right. A
> failure feeds the *specific* error back into the prompt and retries. If
> retries are exhausted we accept a schema-valid plan rather than failing.

**"Is this just a wrapper around ChatGPT?"**

> The interesting part is everything around the model: the validation loop,
> the pluggable source layer, deterministic reconciliation, fingerprinted
> completion that survives re-sync. Swap the model out and the product still
> works. Remove the validation and it stops being trustworthy.

---

## Numbers

| | |
|---|---|
| Tests | 301, no LLM or network required |
| API routes | 21 |
| Data sources | 4 |
| Warm dashboard | under 1 second |
| University passwords collected | zero |

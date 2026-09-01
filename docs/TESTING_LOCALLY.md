# Running CampusSync on your own laptop

For Windows PowerShell, at `C:\Users\Lenovo\OneDrive\Desktop\CampSyncAI`.

You need **two PowerShell windows** open at the same time — one for the
backend (the brain), one for the website. Both must stay open while you test.
Closing a window stops that half of the app.

---

## One-time setup

Open PowerShell in the project folder and run these once:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

If `py -3.12` is not recognised, plain `py -m venv .venv` is fine as long as
`py --version` shows 3.12 or newer.

> If PowerShell blocks the activate script with a security error, run
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, answer `Y`, then
> try again.

### Get an AI key (2 minutes, free)

Everything except **plan generation** works without this. But plan generation
is the main feature, so you want it.

1. [console.groq.com](https://console.groq.com) → sign in with Google
2. **API Keys** → **Create API Key** → copy it (starts with `gsk_`)

Create a file named `.env` in the project folder containing:

```
LLM_PROVIDER=openai
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_API_KEY=gsk_paste_your_key_here
PLANNING_MODEL=llama-3.3-70b-versatile
```

Do not commit this file — it is already in `.gitignore`.

---

## Starting it up, every time

**Window 1 — the backend:**

```powershell
cd C:\Users\Lenovo\OneDrive\Desktop\CampSyncAI
.\.venv\Scripts\Activate.ps1
cd backend
python -m uvicorn api.main:app --reload --port 8000
```

Wait for `Application startup complete.`

**Window 2 — the website:**

```powershell
cd C:\Users\Lenovo\OneDrive\Desktop\CampSyncAI
.\.venv\Scripts\Activate.ps1
streamlit run frontend/app.py
```

Your browser opens at **http://localhost:8501**. That is the app.

To stop either one, click its window and press `Ctrl+C`.

---

## The test checklist

Work down this list. Each item says what you should see, so you can tell a
genuine bug from expected behaviour.

### 1 · Sign-up and the recovery code

- Register with `24BAI1127` and any password you like
- **A recovery code appears, formatted like `6EPT-D7WF-UFT4-WPK4`**
- Screenshot it — this is deliberately shown only once
- You should not reach the dashboard until you acknowledge it

Use one of these five registration numbers, since they are the ones with
sample data loaded: `24BAI1127`, `24BCE1085`, `24BCS1028`, `24BEC1043`,
`24BME1001`.

### 2 · The dashboard

- Your timetable and assignments appear
- Deadlines read as `⏳ 3d left`, `⏳ due today`, or `⚠️ overdue by 2 day(s)`
- Nothing shows a raw negative number like `-4d left`

### 3 · Plan generation — the main event

- Pick a mode (try **day without timings** first, it is quickest)
- Click generate, wait 10–30 seconds
- **Tasks due soonest should be High priority, distant ones Low**
- Try a **week** mode and confirm it spreads across days

If you skipped the AI key, this is where you get *"The AI service is
unavailable"* — that is the expected message, not a crash.

### 4 · Marking things done

- Mark a task complete
- Regenerate the plan
- **The completed task must not reappear.** This is the bit most likely to
  break, so check it properly.

### 5 · Password reset

- Sign out → **Forgot password** tab
- Enter your registration number and the recovery code from step 1
- Type it sloppily on purpose: **lowercase, no dashes**. It should still work
- Set a new password → **you get a brand-new recovery code** (save it)
- Confirm the **old password now fails** and the new one works
- Try the **old recovery code again — it must be rejected**

### 6 · Rate limiting

- Sign out and enter a wrong password about ten times
- Around the 9th–10th attempt you should be told to wait
- **Then log in correctly as a different student — that must still work.**
  One person being locked out must never lock out everyone.

### 7 · Uploading your own documents

- Go to Sources → upload a `.docx` timetable or assignment sheet
- It gets parsed and the tasks join your dashboard

### 8 · Connecting a real calendar (optional)

- Sources → paste a Moodle ICS link
- In VIT Moodle: Calendar → Export calendar → *All events* → **Get calendar URL**
- Real deadlines appear alongside the sample ones

Google Classroom and Teams will show **Unavailable** — that is correct. They
need OAuth keys set up first; see `GOOGLE_CLASSROOM_SETUP.md` and
`MICROSOFT_TEAMS_SETUP.md`.

---

## Running the automated tests

This checks 340 things in about 45 seconds and needs no AI key:

```powershell
.\.venv\Scripts\Activate.ps1
cd backend
python -m pytest ..\tests -q
```

Expect `340 passed`.

---

## When something goes wrong

**"The AI service is unavailable"** — your `.env` is missing, or the key is
wrong. It must sit in the project root, not in `backend\`. Restart Window 1
after editing it, since `.env` is only read at startup.

**Website loads but every action errors** — Window 1 is not running or
crashed. Look at it for a red error.

**"Port already in use"** — an old copy is still running:
```powershell
Get-Process python | Stop-Process -Force
```

**Locked out of an account** — you hit the rate limiter. Wait 15 minutes, or
restart Window 1, which clears the counters since they live in memory.

**Want a clean slate** — stop both windows and delete `backend\campussync.db`.
That wipes all accounts and tasks; the sample documents are untouched.

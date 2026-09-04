# Publishing the app so anyone can connect Google Classroom

Follow this when you want people to connect Classroom **without you adding
their email address first**.

Until you publish, your app is in **Testing** mode: only Google accounts you
list can connect, capped at 100. Publishing removes that entirely.

**Cost: free.** Your two scopes are *sensitive*, not *restricted*, so there
is no paid CASA security audit — that only applies to full Gmail/Drive
access.

**Time:** about 2 hours of your effort, then 2–6 weeks of waiting on Google.

---

## Before you start: is this actually necessary?

Publishing is only needed for **Google Classroom**. Uploading documents and
pasting a Moodle calendar link work for anyone, right now, with no Google
involvement at all.

VIT runs Moodle, so check whether your friends genuinely use Classroom before
committing to a multi-week review. If they do, continue.

---

## The order matters

Google reviewers check that your privacy policy and homepage are **live and
reachable** at the moment they look. Deploy first, submit second. A submission
pointing at a dead link is rejected, and rejection means re-queuing.

```
1. Deploy the app          -> you get a public URL
2. Publish the two pages   -> privacy policy + homepage, both live
3. Record a demo video     -> shows the consent flow
4. Submit for verification -> then wait
```

---

## Step 1 · Deploy

Follow [`HOSTING.md`](HOSTING.md) to get the app running on Render's free
tier. You need a public HTTPS URL before anything else, because Google will
not accept `localhost`.

Note both URLs when it finishes:

- Website: `https://campussync-web-xxxx.onrender.com`
- API: `https://campussync-api-xxxx.onrender.com`

## Step 2 · Put the privacy policy online

[`PRIVACY.md`](PRIVACY.md) in this repo is written for this purpose and
already covers the Limited Use disclosure Google requires.

The simplest way to host it free:

1. Push this repo to GitHub (already done)
2. Repository **Settings** → **Pages**
3. Source: **Deploy from a branch** → branch `main` → folder `/docs`
4. Save, wait a minute

Your policy is then at:

```
https://shre123stha-commits.github.io/CampSyncAI/PRIVACY
```

Open it in a private browser window to confirm it genuinely loads for someone
who is not signed in as you.

> Read the policy before submitting and correct anything that is not true of
> your deployment. Submitting an inaccurate privacy policy is the fastest way
> to get rejected, and reviewers do check the claims against observed
> behaviour.

## Step 3 · Update the OAuth client for production

In Google Cloud Console → **Clients** → your web client, add the production
callback alongside the localhost one:

```
https://campussync-api-xxxx.onrender.com/sources/classroom/callback
```

Keep `http://localhost:8000/sources/classroom/callback` too — both can
coexist, so local development keeps working.

Then in Render → `campussync-api` → **Environment**, set
`GOOGLE_REDIRECT_URI` to the production URL and redeploy.

**Verify the deployed flow works before submitting.** Sign in to the live
site as an existing test user and connect Classroom end to end. Reviewers
will try exactly this, and if it fails for them you are rejected.

## Step 4 · Fill in Branding

Google Cloud Console → **Google Auth Platform** → **Branding**:

| Field | Value |
|---|---|
| App name | `CampusSync AI` |
| User support email | your email |
| App logo | optional, 120×120 PNG |
| Application home page | `https://campussync-web-xxxx.onrender.com` |
| Privacy policy link | `https://shre123stha-commits.github.io/CampSyncAI/PRIVACY` |
| Authorised domains | `onrender.com` and `github.io` |
| Developer contact | your email |

Every URL must be live. Reviewers click them.

## Step 5 · Record the demo video

This is mandatory for sensitive scopes and the most common reason for
rejection. Upload it unlisted to YouTube.

It must show, in one continuous unedited take:

1. The **OAuth consent screen** with the URL bar visible, so the reviewer can
   read your client ID
2. Every requested scope being granted
3. **What your app does with the data afterwards** — this is the part people
   omit. Show the coursework appearing on the dashboard and a study plan
   being generated from it.

Narrate it: *"The user clicks Connect Google Classroom. Google asks for
permission to view courses and coursework, both read-only. After approving,
their assignments appear here, and the app uses those due dates to build a
study schedule."*

Three to four minutes is plenty. Phone screen-recording is fine — production
value is irrelevant, completeness is not.

## Step 6 · Submit

**Audience** tab → **Publish app** → confirm.

Then → **Verification centre** → **Prepare for verification**. You supply:

- The demo video link
- A justification for each scope

Write the justifications specifically. Vague ones get bounced:

> **`classroom.courses.readonly`** — CampusSync AI displays the student's
> course names next to each assignment so they can tell which subject a
> deadline belongs to. Without course names, tasks are unlabelled and the
> study plan cannot group work by subject.

> **`classroom.coursework.me.readonly`** — This is the core function of the
> app. It reads the student's own assignment titles and due dates in order to
> generate a prioritised study schedule. Read-only and limited to the
> student's own coursework; we never write to Classroom and never access
> other students' data.

Submit.

---

## What happens next

Google emails you, usually within a few days, and often asks a follow-up
question. **Answer quickly** — the clock effectively restarts each time a
reply is pending, and slow replies are the main cause of multi-month
timelines.

Expect 2–6 weeks overall for sensitive scopes.

**Your app keeps working throughout.** Existing test users are unaffected,
and every non-Classroom feature is entirely unaffected. This runs in the
background.

---

## While you wait

Users outside the test list see an **"This app isn't verified"** warning.
They can still proceed via **Advanced → Go to CampusSync AI (unsafe)**, which
looks alarming and most people will not do.

So during the wait, keep adding friends as test users — that path has no
warning at all. The 100-user cap is far above what you need.

---

## Common rejection reasons

| Reason | Avoid it by |
|---|---|
| Privacy policy unreachable | Open it in a private window first |
| Video omits the consent screen | Show the browser URL bar during consent |
| Video omits post-consent usage | Show the dashboard and a generated plan |
| Homepage does not explain the app | The landing page should say what it does |
| Scope justification too vague | Explain the specific feature that needs it |
| Domain not in Authorised domains | Add every domain you reference |
| Slow replies | Answer Google's emails within a day or two |

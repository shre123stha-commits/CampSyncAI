# Putting this online for your friends

Goal: ten people can use CampusSync from their own phones and laptops,
whenever they want, without your computer being on.

Cost: **free**. Time: **about 30 minutes**, most of it waiting.

---

## Step 1 · Get a free AI key (5 minutes)

The app needs an AI service. Groq is free, fast, and needs no card.

1. Go to [console.groq.com](https://console.groq.com) and sign in with Google
2. **API Keys** → **Create API Key**
3. Copy it — it starts with `gsk_`. It is shown once.

Keep it somewhere safe for a moment. Never put it in a screenshot or commit
it to GitHub.

> Free tier is roughly 14,400 requests a day. Ten friends generating a few
> plans each will use a tiny fraction of that.

## Step 2 · Deploy (15 minutes, mostly waiting)

1. Go to [render.com](https://render.com) → sign up with GitHub
2. **New** → **Blueprint**
3. Choose your `CampSyncAI` repository
4. Render reads `render.yaml` and shows three services: a database, the API,
   and the website
5. It will ask for **`OPENAI_API_KEY`** — paste the Groq key from Step 1
6. **Apply**

Now wait. The first build takes 5–10 minutes. When all three go green, click
the `campussync-web` service and open its URL. That link is what you send
your friends.

## Step 3 · Test it yourself first

Open the URL, create an account, and **save the recovery code it shows you**.
Generate a plan. If that works, it works for everyone.

---

## What to tell your friends

> Here's the link: `https://campussync-web-xxxx.onrender.com`
>
> Create an account with your registration number and any password you like —
> **not** your VIT password, this is a separate thing.
>
> It'll show you a recovery code once. Screenshot it. That's the only way
> back in if you forget your password; there's no email reset.
>
> First load might take a minute if nobody's used it recently. That's normal
> on the free tier.

---

## Things that will happen, so you are not surprised

**It falls asleep.** After 15 minutes with nobody using it, Render shuts the
service down. The next person to visit waits 30–60 seconds while it wakes.
Everything after that is fast. This is the main cost of "free".

**The database expires after 30 days.** Render's free Postgres is deleted
after a month. You will need to create a new one and redeploy. Accounts and
tasks are lost unless you export first:

```bash
# from the Render dashboard: Database -> Connect -> PSQL Command
pg_dump "<your connection string>" > backup.sql
```

Set a calendar reminder for day 25. If this becomes annoying, Render's paid
database is a few dollars a month and does not expire.

**Sessions last a week.** Set in `render.yaml` as `SESSION_TTL_HOURS: 168`,
so nobody re-signs in daily. Lower it if you would rather they did.

---

## Adding Google Classroom or Teams later

Both need their redirect URLs updated to your real address, because they
were set up for `localhost`:

1. In the provider console, add the redirect URI with your Render URL:
   ```
   https://campussync-api-xxxx.onrender.com/sources/classroom/callback
   ```
2. In Render → `campussync-api` → **Environment**, add the matching
   `GOOGLE_REDIRECT_URI` (and the client id/secret)
3. Redeploy

See [`GOOGLE_CLASSROOM_SETUP.md`](GOOGLE_CLASSROOM_SETUP.md) and
[`MICROSOFT_TEAMS_SETUP.md`](MICROSOFT_TEAMS_SETUP.md).

The ICS calendar feed needs none of this — it already works.

---

## If something breaks

**Build failed.** Render → the service → **Logs**. The error is usually in
the last twenty lines.

**Website loads but nothing works.** The API is probably still waking. Wait a
minute and refresh. If it persists, check `campussync-api` is green.

**"AI service unavailable".** Your Groq key is wrong or expired. Render →
`campussync-api` → Environment → update `OPENAI_API_KEY` → redeploy.

**Someone forgot their password and their recovery code.** There is no way
back in — that is the trade-off of having no email service. Delete the
account from the database and let them re-register. Their tasks are lost;
their connected calendar can be reconnected in a minute.

---

## Costs, honestly

| | Free tier | If you outgrow it |
|---|---|---|
| Hosting | ₹0, sleeps when idle | ~₹600/month, always on |
| Database | ₹0, expires monthly | ~₹600/month, permanent |
| AI | ₹0 (Groq) | Pennies with OpenAI |

For ten friends, free is genuinely fine. The sleeping is the only real
irritation, and the first person of the day absorbs it.

# Google Classroom Setup

How to get `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` so the Google
Classroom source becomes available in CampusSync AI.

**Time:** ~15 minutes. **Cost:** free.

Until these are set, the app cleanly marks Classroom as *Unavailable* — nothing
breaks, so there is no rush, but the Google review process can take days if you
want non-testers to use it. Start early.

---

## What we are creating

An **OAuth client** — a public `client_id` and a private `client_secret` that
identify *your app* to Google. When a student clicks "Connect Google
Classroom":

1. They are sent to Google's own sign-in page (never ours)
2. They approve two read-only permissions
3. Google redirects back to our `/sources/classroom/callback`
4. We receive a **refresh token**, encrypted and stored

We never see their Google password. This is why the OAuth setup is worth the
effort — there is no shortcut that is also safe.

---

## Step 1 — Create a Google Cloud project

1. Go to <https://console.cloud.google.com/>
2. Sign in with the Google account that will own the app (use a personal or
   team account — a university-managed account may have admin restrictions)
3. Click the project dropdown at the top → **New Project**
4. Name it `CampusSync AI` → **Create**
5. Make sure the new project is selected in the dropdown before continuing

---

## Step 2 — Enable the Classroom API

1. Go to <https://console.cloud.google.com/apis/library>
2. Search for **Google Classroom API**
3. Click it → **Enable**

If you skip this, OAuth will appear to work and then fail with
`Google Classroom API has not been used in project …`.

---

## Step 3 — Configure the consent screen

This is what students see when they approve access.

1. Go to <https://console.cloud.google.com/apis/credentials/consent>
2. **User Type:**
   - **External** — anyone with a Google account. Choose this unless your
     university runs Google Workspace *and* you only need students in it.
   - **Internal** — only your Workspace organisation. Simpler (no verification
     needed) but only visible if you are signed in with a Workspace account.
3. Click **Create** and fill in:

| Field | Value |
|---|---|
| App name | `CampusSync AI` |
| User support email | your email |
| Developer contact | your email |

Logo and links are optional while testing.

4. **Scopes** — click **Add or remove scopes**, then **Manually add scopes**
   and paste these two, exactly:

```
https://www.googleapis.com/auth/classroom.courses.readonly
https://www.googleapis.com/auth/classroom.coursework.me.readonly
```

   Click **Update** → **Save and continue**.

   These are the *only* scopes the code requests. They are read-only and
   coursework-specific: the token cannot read Gmail, cannot modify anything,
   and cannot see other students' work. Keeping the list minimal also makes
   Google's review far easier.

5. **Test users** — click **Add users** and add every Google account that will
   demo the app, including your own.

   > ⚠️ **This is the step people forget.** While the app is in *Testing*
   > status, only listed test users can complete the OAuth flow. Everyone else
   > gets `Error 403: access_denied`. You can add up to 100.

6. **Save and continue** → **Back to dashboard**

---

## Step 4 — Create the OAuth client

1. Go to <https://console.cloud.google.com/apis/credentials>
2. **Create credentials** → **OAuth client ID**
3. **Application type: Web application** (not "Desktop" — our flow is
   server-side and needs a redirect URI)
4. Name: `CampusSync AI backend`
5. Under **Authorised redirect URIs**, click **Add URI** and paste **exactly**:

```
http://localhost:8000/sources/classroom/callback
```

   > This must match `GOOGLE_REDIRECT_URI` character for character — no
   > trailing slash, correct port, `http` not `https` for localhost. A mismatch
   > gives `Error 400: redirect_uri_mismatch`, which is the single most common
   > problem with this setup.

6. Click **Create**
7. Copy the **Client ID** and **Client secret** from the dialog

The secret can be viewed again later from the same credentials page, so don't
panic if you close it.

---

## Step 5 — Put them in your `.env`

In the repo root:

```bash
cp .env.example .env
```

Then edit `.env`:

```ini
GOOGLE_CLIENT_ID=1234567890-abcdefghijklmnop.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-secret-here
GOOGLE_REDIRECT_URI=http://localhost:8000/sources/classroom/callback

# Also set this if you have not already - it encrypts stored tokens
SECRET_KEY=generate-a-long-random-string-here
```

Generate a `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> 🔐 `.env` is already in `.gitignore`. **Never commit it.** If a client secret
> is ever pushed to GitHub, delete the OAuth client in the console and create
> a new one — rotating is quick, and leaked secrets get scraped within minutes.

---

## Step 6 — Restart and verify

**`.env` is only read when the backend starts.** Editing it while the server
is running changes nothing — this is the second most common reason people
think the setup failed. Stop the backend with `Ctrl+C` and start it again.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
cd backend
python -m uvicorn api.main:app --reload --port 8000
```

macOS / Linux:

```bash
source .venv/bin/activate
cd backend
python -m uvicorn api.main:app --reload --port 8000
```

The quickest check needs no token — just confirm the app now considers
Classroom configured:

```powershell
cd backend
python -c "import config; print(config.classroom_configured())"
```

`True` means the credentials were found. If it prints `False`, see the
troubleshooting note below — **both** the client ID *and* the secret must be
set; one alone is not enough.

You can also check the running server:

```bash
curl -s localhost:8000/sources/status -H "Authorization: Bearer <your-token>"
```

You want `"classroom_available": true`.

Then in the UI: **Connect accounts** → the Google Classroom card should now
show a **Connect Google Classroom** button instead of "Unavailable".

Click it → **Continue to Google →** → sign in as a **test user** → approve →
you should land on a "Google Classroom connected" page. Return to the
dashboard and refresh; coursework appears alongside your other tasks.

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `redirect_uri_mismatch` | The URI in the console differs from `GOOGLE_REDIRECT_URI` | Compare character by character — port, trailing slash, http vs https |
| `403: access_denied` | Your account is not a test user | Add it under consent screen → Test users |
| `Classroom API has not been used` | API not enabled | Step 2 |
| Card still says "Unavailable" | `.env` not loaded, or only one of the two values is set | Restart the backend — `.env` is read only at startup. Both `GOOGLE_CLIENT_ID` *and* `GOOGLE_CLIENT_SECRET` must be non-empty. Verify with `python -c "import config; print(config.classroom_configured())"` from `backend/` |
| Card still says "Unavailable" after a restart | The file is named `.env.txt` | Windows hides known extensions. In Explorer turn on **View → File name extensions** and rename it to exactly `.env` |
| `Google did not return a refresh token` | Google only sends one on first consent | Revoke at <https://myaccount.google.com/permissions>, then reconnect |
| `Stored credential could not be decrypted` | `SECRET_KEY` changed | Disconnect and reconnect the source |
| No coursework appears | Classroom account has no active courses | Test with an account that is enrolled in a course with assignments |

---

## Going beyond test users

While in **Testing**, only your listed test users can connect — which is
completely fine for a demo, a submission, or a project review.

To let *anyone* connect you must **Publish** the app and pass Google's
verification: a demo video, a privacy policy URL, and a domain you own.
Because our scopes are read-only and non-sensitive this is a lighter review
than most, but it still takes **several days to a few weeks**.

**Recommendation:** stay in Testing mode and add your evaluators as test users.
Publishing is only worth it if you intend to run this as a real service.

---

## For deployment

When the backend is no longer on localhost:

1. Add the production callback to **Authorised redirect URIs**, e.g.
   `https://api.yourdomain.com/sources/classroom/callback`
2. Set `GOOGLE_REDIRECT_URI` to match in the deployed environment
3. Keep the localhost URI too — both can coexist for local development
4. Set a strong `SECRET_KEY` in the production environment and **do not**
   reuse the development one

---

## Security summary

Worth being able to state plainly if you are asked about this in a review:

- We request **two read-only scopes** and nothing else
- The student authenticates on **Google's own domain**; we never see a password
- We store only a **refresh token**, encrypted at rest with Fernet
- The student can disconnect in our UI, or revoke at
  <https://myaccount.google.com/permissions>, at any time
- Disconnecting **destroys** the stored token

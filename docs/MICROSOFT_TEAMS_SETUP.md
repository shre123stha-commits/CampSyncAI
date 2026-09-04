# Microsoft Teams setup

Connecting Teams assignments needs an app registration in Microsoft Entra ID
(formerly Azure AD). Read the constraint below **before** you start — it
determines whether this integration can work at your university at all.

---

## The constraint you cannot engineer around

Every Microsoft Graph education permission — including the read-only
`EduAssignments.ReadBasic` — is marked **AdminConsentRequired: Yes**.

A student cannot approve it. Your university's Microsoft 365 administrator
must grant it for the whole tenant. There is no supported workaround; if the
tenant blocks user consent, you will loop on a "Need admin approval" screen
forever.

**So this adapter uses two routes:**

| Route | Permission | Admin consent | What you get |
|---|---|---|---|
| Assignments | `EduAssignments.ReadBasic` | **Required** | Real Teams assignments with due dates |
| Calendar | `Calendars.Read` | Not by default | Class calendar events, which carry most due dates |

The adapter tries assignments first and **falls back to the calendar** on a
403. A student in an unapproved tenant still gets deadlines.

> If your tenant also blocks `Calendars.Read` (some do, via a blanket consent
> policy), neither route works and you need IT. The app will say so plainly
> rather than showing an empty list.

---

## 1 · Register the application

1. Go to [entra.microsoft.com](https://entra.microsoft.com) →
   **Applications** → **App registrations** → **New registration**
2. Name: `CampusSync AI`
3. **Supported account types:**
   - *Accounts in any organizational directory and personal Microsoft
     accounts* — most flexible, works for testing
   - *Single tenant* — restrict to your university only
4. **Redirect URI:** platform **Web**, value exactly:

```
http://localhost:8000/sources/teams/callback
```

Character for character. A mismatch gives `AADSTS50011`.

5. **Register**

Copy the **Application (client) ID** from the overview page.

## 2 · Create a client secret

**Certificates & secrets** → **New client secret** → set an expiry →
**Add**.

Copy the **Value** immediately — not the Secret ID. It is shown once and
becomes unrecoverable the moment you leave the page.

## 3 · Add permissions

**API permissions** → **Add a permission** → **Microsoft Graph** →
**Delegated permissions**. Add all four:

| Permission | Why |
|---|---|
| `offline_access` | Without it Microsoft never issues a refresh token |
| `User.Read` | Identifies the signed-in student |
| `Calendars.Read` | The fallback route |
| `EduAssignments.ReadBasic` | The direct route |

The education permission will show **"Admin consent required: Yes"** with a
warning triangle. That is expected — leave it. The app works through the
calendar until an administrator approves it.

**If you are the tenant admin** (or your university will cooperate), click
**Grant admin consent for &lt;tenant&gt;**. Both routes then work.

## 4 · Configure CampusSync

In `.env` at the project root:

```ini
MS_CLIENT_ID=00000000-0000-0000-0000-000000000000
MS_CLIENT_SECRET=<the Value from step 2>
MS_REDIRECT_URI=http://localhost:8000/sources/teams/callback
MS_TENANT=common
```

`MS_TENANT=common` allows any work, school or personal account. Set it to
your tenant ID to restrict sign-in to one university.

Restart the backend. **Connect accounts** → the Teams card gains a Connect
button.

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `AADSTS50011` redirect mismatch | URI differs from the registration | Compare character by character |
| `AADSTS65001` / "Need admin approval" | Tenant requires consent | Ask IT, or rely on the calendar fallback |
| `AADSTS7000215` invalid client secret | You copied the Secret ID, not the Value | Create a new secret, copy the Value |
| No refresh token returned | `offline_access` missing | Add it, then revoke at [myapplications.microsoft.com](https://myapplications.microsoft.com) and reconnect |
| Connects but no assignments | Education scope denied | Expected — check whether calendar events appeared instead |

---

## Asking your IT department

If you want the full assignments route, send them this:

> I am running a student study-planning application that reads Microsoft
> Teams assignment due dates. It requests the delegated, **read-only**
> permission `EduAssignments.ReadBasic` — assignments without grades, only
> for the signed-in student's own classes. It cannot write, cannot submit,
> cannot read other students' data, and cannot access mail or files.
> Microsoft requires tenant admin consent for all education permissions,
> which is why I need your approval. The app registration is
> `<your client ID>`.

Give them the tenant-wide consent URL:

```
https://login.microsoftonline.com/<tenant-id>/adminconsent?client_id=<your-client-id>
```

**Realistically:** university IT departments are slow to approve third-party
apps, and a student project is unlikely to clear that bar quickly. The
calendar fallback exists precisely so the integration is useful without them.

---

## Security notes

- **No Microsoft password ever reaches this application.** The student
  authenticates on Microsoft's own page; we store only a refresh token,
  encrypted with Fernet at rest and destroyed on disconnect.
- All requested scopes are **read-only**.
- The student can revoke access at any time at
  [myapplications.microsoft.com](https://myapplications.microsoft.com),
  independently of this app.
- Never commit `.env`. If a client secret reaches GitHub, delete it in Entra
  and create a new one — leaked secrets are scraped within minutes.

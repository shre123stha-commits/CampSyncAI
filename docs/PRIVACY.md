# Privacy Policy — CampusSync AI

**Last updated:** 4 September 2026

CampusSync AI is a study planner for students. It reads your coursework
deadlines and produces a suggested study schedule. This page explains exactly
what data it touches and why.

---

## What we collect

**Your account.** A registration number, a display name if you give one, and
a password. The password is stored only as a bcrypt hash — it cannot be read
back, by us or by anyone with database access.

**Coursework you connect.** If you connect Google Classroom, we read your
course names, assignment titles, and due dates. If you connect a calendar
feed or upload a document, we read the deadlines it contains.

**Study plans.** The schedules generated for you, so they persist between
visits.

We do **not** collect your email address, contacts, files, photos, browsing
activity, or any advertising identifier.

---

## Google user data

CampusSync AI requests exactly two Google OAuth scopes, both read-only:

| Scope | What it permits |
|---|---|
| `classroom.courses.readonly` | See the names of courses you are enrolled in |
| `classroom.coursework.me.readonly` | See your own coursework and its due dates |

**What this means in practice:**

- We can read your coursework. We **cannot** create, edit, or delete anything
  in Google Classroom — there is no write access of any kind.
- We can see only **your own** coursework. We cannot see other students'
  work, submissions, or grades.
- These scopes grant no access to Gmail, Drive, Contacts, Photos, or any
  other Google service.

### How Google data is used

Course names and due dates are used for one purpose: **building your study
plan**. Assignment titles and deadlines are sent to a large language model
(Groq, running Llama) to generate the schedule. Nothing else is transmitted —
no account identifiers, no name, no registration number.

### How Google data is stored

Your Google refresh token is encrypted at rest using Fernet (AES-128-CBC with
HMAC authentication) before it is written to the database. Coursework itself
is stored as plain task records so your dashboard loads without re-querying
Google every time.

### What we never do with Google data

CampusSync AI's use of information received from Google APIs adheres to the
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including the Limited Use requirements. Specifically, we do **not**:

- Sell, rent, or trade your data
- Use it for advertising, remarketing, or profiling
- Transfer it to third parties except the LLM provider named above, solely to
  generate your plan
- Allow any human to read it, except where you have explicitly asked us for
  support and given permission
- Use it to train any machine learning model

---

## Who else sees your data

**The LLM provider** (Groq) receives assignment titles and due dates in order
to generate your plan. It receives no identifying information about you.

**Nobody else.** There are no analytics trackers, no advertising networks,
and no data brokers. We do not sell data, and we have no business model that
would create an incentive to.

---

## How long we keep it

Data persists until you delete it. You can:

- **Disconnect a source** — deletes the stored token immediately, and we stop
  reading that source
- **Revoke access at Google** — visit
  [myaccount.google.com/permissions](https://myaccount.google.com/permissions)
  and remove CampusSync AI. This works even if our site is unreachable.
- **Delete your account** — contact the address below and everything
  associated with it is removed

---

## Security

- Passwords and recovery codes are bcrypt-hashed, never reversible
- OAuth tokens are encrypted at rest
- Session tokens are stored only as SHA-256 hashes
- All traffic is served over HTTPS
- Rate limiting protects accounts against brute-force attempts

No system is perfectly secure, and it is worth being honest about that. This
is a student project rather than a commercial service, which is precisely why
it requests the narrowest possible permissions: even in the worst case, the
data exposed is your assignment due dates, not your email or your files.

---

## Children

CampusSync AI is intended for university students and is not directed at
children under 13.

---

## Changes

Material changes to this policy will be reflected in the "last updated" date
above. Continued use after a change constitutes acceptance.

---

## Contact

Questions, deletion requests, or privacy concerns:

**Repository:** <https://github.com/shre123stha-commits/CampSyncAI>
**Contact:** open an issue on the repository above.

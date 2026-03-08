# Security Findings

Findings from internal API security review conducted 2026-03-08. All endpoints tested
against an admin key and a regular user key with a live server instance.

---

## Open Issues

### [MEDIUM] Open Registration — No Admin Gate

**Endpoint:** `POST /auth/register`

Anyone with network access can register an account with no authorization, invite token,
or admin approval. Upon registration, the new user immediately has full read/write access
to all resources.

**Confirmed:** Registered `attacker@evil.com` with no credentials. Account was created
and returned a valid session.

**Recommendation:** Add admin-controlled registration (invite tokens or an approval queue),
or an environment flag (e.g. `REGISTRATION_DISABLED`) to lock down the endpoint after
initial setup.

---

### [MEDIUM] No Resource-Level Ownership — Any User Can Modify or Delete Any Resource

**Endpoints:** `PUT /api/resources/{id}`, `DELETE /api/resources/{id}`

There is no ownership model on resources. Any authenticated user can update or delete
any resource, regardless of who created it.

**Confirmed:** Regular user (Jimmy) successfully updated a resource created by the admin:
```
PUT /api/resources/1  →  200 OK
```

**Recommendation:** Add a `created_by` FK to the `Resource` model and restrict
update/delete to the creator or an admin. Alternatively, treat all write operations
as admin-only and let regular users have read-only access.

---

### [LOW] User Enumeration via Two Vectors

**1. Registration endpoint** returns a distinct error for duplicate emails:
```
POST /auth/register  →  409 "An account with that email already exists."
```
An attacker can brute-force email addresses to confirm which are registered.

**2. Login timing** — measurable difference between an existing account with a wrong
password (~1.2s, bcrypt comparison runs) vs. a non-existent account (~1.0s, early
return before bcrypt):
```
Existing user, wrong password:  ~1.20s
Non-existent user:              ~1.01s
```

**Recommendation:**
- Registration: return a generic response regardless of whether the email exists.
- Login: always run a bcrypt comparison (e.g. hash a dummy value for missing users)
  to normalize response time.

---

### [LOW] Weak Password Policy

Only a minimum length of 8 characters is enforced. No complexity requirements.
Passwords like `12345678` are accepted.

**Recommendation:** Require at least one uppercase letter, one digit, and one special
character — or check against a common password blocklist (e.g. zxcvbn or HaveIBeenPwned).

---

## Informational

### [INFO] Role Update Endpoint Uses Query Parameter Instead of Request Body

**Endpoint:** `PUT /admin/users/{id}/role`

The `is_admin` field is expected as a **query parameter** (`?is_admin=true`) rather than
a JSON request body. Sending it as a JSON body returns a confusing 422. Not a security
vulnerability but inconsistent with the rest of the API.

**Recommendation:** Accept `is_admin` from a JSON body like other write endpoints.

---

## Confirmed Not Vulnerable

| Test | Result |
|------|--------|
| Unauthenticated access to protected endpoints | 401 / 303 on all endpoints |
| Regular user accessing any `/admin/*` endpoint | 403 on all 11 endpoints |
| IDOR: user deleting another user's API key | 404 (keys scoped to owner only) |
| Mass assignment: `is_admin=true` in registration body | Field silently ignored |
| SQL injection in query parameters | Blocked by Pydantic type validation |
| `file://` scheme in webhook-test | Rejected by httpx |
| Admin self-deletion | 400 error |
| API key values in responses | Only 4-char prefix exposed, never full key |
| Settings input validation boundaries | All boundary conditions enforced |
| Last-admin demotion protection | Blocked correctly |

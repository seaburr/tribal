# Security Findings

Findings from internal API security review conducted 2026-03-08, supplemented by
automated fuzz/injection testing conducted 2026-03-15. All endpoints tested against
an admin key and a regular user key with a live server instance (MySQL backend).

---

## Open Issues

### [LOW] Unhandled `httpx.InvalidURL` in Webhook-Test Endpoints → 500

**Endpoints:** `POST /api/resources/webhook-test`, `POST /admin/webhook-test`

Both webhook-test handlers catch `httpx.RequestError` but not `httpx.InvalidURL`.
`httpx.InvalidURL` inherits from `ValueError`, not `RequestError`, so malformed URLs
that are syntactically invalid (e.g. octal IP notation `http://0177.0.0.1/`, an
empty host, embedded newlines) bypass the handler and propagate as an unhandled
exception, returning a 500.

**Confirmed:**
```
POST /api/resources/webhook-test  {"webhook_url": "http://0177.0.0.1/"}  →  500
POST /admin/webhook-test          {"webhook_url": "http://0177.0.0.1/"}  →  500
```

The root cause (reproduced locally):
```
httpx.InvalidURL: Invalid IPv4 address: '0177.0.0.1'
```

**Recommendation:** Broaden the `except` clause to also catch `httpx.InvalidURL`
(or catch `Exception` as a fallback) and return `400` instead.

---

### [LOW] Integer Overflow in Audit-Log Offset → 500

**Endpoint:** `GET /admin/audit-log?offset=<value>`

The `offset` query parameter is typed `int` with no upper-bound constraint. Python
integers are arbitrary precision, so FastAPI accepts values far beyond MySQL's 64-bit
signed integer range (max 9,223,372,036,854,775,807). When the value is passed to
SQLAlchemy's `.offset()`, MySQL rejects it with a range error that is not caught,
returning a 500.

**Confirmed:**
```
GET /admin/audit-log?offset=99999999999999999999  →  500
```

**Recommendation:** Add a reasonable upper bound to the parameter, e.g.:
```python
offset: int = Query(default=0, ge=0, le=10_000_000)
```

---

### [LOW] MySQL VARCHAR Constraint Violation on API Key Name → 500

**Endpoint:** `POST /api/keys/`

The `ApiKey.name` column is `String(255)` in the ORM model, and MySQL enforces this
strictly. The Pydantic schema (`ApiKeyCreate`) has no `max_length` constraint, so a
name longer than 255 characters passes validation but causes MySQL to raise "Data too
long for column 'name'" — an unhandled `OperationalError` that returns a 500.

**Confirmed:**
```
POST /api/keys/  {"name": "A" * 10000}  →  500
```

**Recommendation:** Add `max_length=255` to the `ApiKeyCreate.name` field (Pydantic
will then return a 422 before the DB is touched), or catch `OperationalError` in the
handler.

---


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

### ~~[LOW] Weak Password Policy~~ — RESOLVED

~~Only a minimum length of 8 characters is enforced.~~ Testing on 2026-03-15 confirms
that `auth.py` now enforces digit + special-character requirements in addition to the
8-character minimum. Passwords like `12345678`, `Passw0rd`, `!!!!!!!!` are all
correctly rejected with 422. No action needed.

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
| SQLi in login email/password | 422 (Pydantic EmailStr validation) |
| SQLi in resource string fields (name, dri, purpose) | 422 (Pydantic validation) |
| SQLi in resource_id path parameter | 404 / 422 (FastAPI int coercion) |
| `alg=none` JWT bypass | 401 |
| Bogus/empty API keys | 401 on all variants |
| Low-priv user privilege escalation | 403 on all attempts |
| Oversized inputs (100k-char name, 10k-char name) | 422 (Pydantic `max_length`) |
| Null bytes in string fields | 422 |
| Unicode / emoji in string fields | 422 |
| XSS payloads in resource fields (API layer) | 422 (strict type enum enforced) |
| Bad date formats (99/99/9999, negative, ISO datetime, etc.) | 422 on all |
| Invalid resource types (script tags, SQL, path traversal) | 422 on all |
| SSRF via webhook-test (AWS metadata, GCP metadata, localhost, IPv4 decimal) | 400 on all (httpx connection error) |
| SSRF via cert-lookup (localhost, metadata IPs, file://) | 400 on all |
| Certificate upload: private key in .pem | 400 |
| Certificate upload: .key / .p12 / .p7b / .pfx extensions | 400 |
| Certificate upload: 10 MB file | 400 / 413 |
| HTTP method fuzzing (PATCH, TRACE, OPTIONS, etc.) | 405 on all |
| Form-encoded body on JSON endpoints | 422 |
| Malformed / empty JSON body | 422 |
| Deeply nested JSON (500 levels) | 422 |
| Weak passwords (no digit, no special, common words) | 422 on all |
| Invalid email formats (no domain, injection, header injection) | 422 on all |

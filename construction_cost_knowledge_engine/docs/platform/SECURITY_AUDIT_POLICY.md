# Security Audit Policy

## Event Model

`app_security_event` is append-only and records Tenant, user, action, object type/id, result, sanitized reason, client IP, user agent, request ID, correlation ID, actor, and timestamp.

Required events include login success/failure, logout, Session revocation, password change/reset, user create/disable, role assign/remove, permission denial, CSRF rejection, Tenant rejection, and break-glass use.

## Data Minimization

The audit writer accepts explicit fields and rejects secret-like reason content through redaction. Events and samples must never contain:

- plaintext passwords or password hashes;
- raw Session or CSRF tokens;
- Cookie or Authorization values;
- database connection strings or internal file paths.

Login attempts may retain normalized username, client IP, user agent, result, and a generic reason code for rate-limit analysis. Unknown-user failures do not produce different client messages.

## Integrity and Access

PostgreSQL triggers reject UPDATE and DELETE on login attempts, password history, and security events. Security history downgrade is destructive and requires prior export, authorization, and retention review. `audit.read` is granted only to administrator by default.

Break-glass events use result `override`, require a reason, and must identify Tenant and actor. They are never silent and do not alter the normal role catalog.

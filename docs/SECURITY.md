# Security and responsible-operation notes

- Secrets are supplied by environment variables and excluded from Git.
- FIRMS keys must never appear in logs, URLs shown to users, commits or screenshots.
- CORS is restricted to configured console origins.
- Write endpoints are unauthenticated in the local Datathon prototype; do not expose them directly to the public internet.
- Decision outputs are advisory-only and require a recorded human review.
- RSI candidates cannot modify the active model and always retain a rollback boundary.
- Audit entries freeze payloads before hashing, preventing later in-memory mutations from rewriting earlier evidence.
- Raw source licenses and redistribution rules must be recorded when the city data package is created.
- CI uses read-only repository permissions and Dependabot monitors Python, npm and GitHub Actions dependencies.

For an operational deployment, add authentication/authorization, TLS, rate limiting, request-size limits, centralized secrets, signed images, vulnerability scanning, encrypted storage, backup/restore tests, incident response and independently reviewed human-factors procedures.

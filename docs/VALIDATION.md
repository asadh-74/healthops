# Validation record

Locally verified during implementation:

- 11 API integration tests pass on SQLite: authentication/roles, concurrent last-dose reservations, cancellation retry, approval/stock conservation, automation authentication/deduplication, expiry enforcement, fictional-reference validation, rollback of duplicate booking, rescheduling, wastage, failed transfer rollback, all four workflow actions and audit records.
- TypeScript compilation and Vite production build pass.
- Ruff checks pass.
- Alembic migration runs against a fresh SQLite database and can be run again without duplicating tables.
- Workflow JSON parses and ships inactive, without embedded credentials or outbound notification nodes.

CI is configured to repeat the API tests on SQLite and PostgreSQL 16, compile/build the frontend, build the Docker image, and run Trivy. A configured check is not a claim that its latest run passed; consult GitHub Actions for results.

Not verified in the authoring environment: browser rendering/interactions, Docker Compose startup, n8n editor import/execution, Grafana UI, PostgreSQL runtime, public deployment, penetration testing or load testing. Docker and browser verification tools were unavailable. Validate these before recording the final portfolio demo.

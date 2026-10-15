# Demo security model

- Store only fictional DEMO-prefixed patient references. There are no patient name, phone, email, or national-ID fields.
- Notification delivery is structurally restricted to database inbox writes: no outbound mail/SMS transport exists.
- Setup generates separate local database, JWT, automation, Grafana, n8n encryption, and demo-password values. `.env` is ignored and excluded from Docker context.
- Tokens expire after two hours and are held in React memory, not persistent browser storage. Refreshing the page requires sign-in. Passwords use salted scrypt.
- API authorization is enforced independently of UI visibility. The automation credential only grants the four demo workflow actions, not stock changes or interactive access.
- Stock and transfers use guarded SQL updates and database transactions. PostgreSQL row locks serialize cancellation/rescheduling. Demo inbox event keys are unique.
- Nginx limits login requests and blocks `/metrics`; direct API ports are not published. Protect infrastructure access: applications inside the Compose network can reach internal services.
- n8n is owner-managed and starts without imported credentials or active schedules. Keep its encrypted credential volume and encryption key private.
- Roles span the whole demo network. No tenant isolation, clinic-specific access grants, password reset, user administration UI, MFA, session revocation, or compliance certification is claimed.
- Before public hosting, configure TLS, secure n8n cookies, credential rotation, verified backups, access logging, and resource limits. Do not expose the local Compose configuration directly to the internet.

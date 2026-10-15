# Free Render app + Aiven MySQL

The Render service hosts both the React build and FastAPI. Aiven stores application data. No database credentials belong in GitHub or chat.

1. Create an **Aiven for MySQL Free** service in https://console.aiven.io/ (choose Free, not a time-limited paid trial).
2. In Connection information, note Host, Port, User, Password and Database. Download the CA certificate. Do not share password screenshots.
3. Create a Render Docker web service from this repository and the `feature/healthops-fullstack` branch. Choose **Free**, health check `/health`, Docker command `python scripts/start_render.py`.
4. Copy the environment variable keys from `render.yaml` into Render. Set the MYSQL values from Aiven. `MYSQL_SSL_CA` is the full multiline PEM certificate including BEGIN/END lines. Set three separate random values of at least 32 characters for JWT_SECRET, AUTOMATION_TOKEN and DEMO_PASSWORD if creating manually; Blueprint generates them.
5. Set `SEED_DEMO=true` for this fictional-data-only demo. Startup runs migrations and seeds only if no user exists. Never connect this demo to an existing clinical database.
6. Deploy and open `/health`, then `/`. Sign in as demo.admin using DEMO_PASSWORD from Render's private Environment panel. Set SEED_DEMO=false after the first successful seed. Later password env changes do not update existing users.

TLS validates the CA and hostname. No insecure TLS fallback exists. Small connection pools limit usage. Use separate MYSQL variables to avoid password URL-encoding mistakes. Local Compose still uses PostgreSQL; MySQL is an additional supported deployment target.

The Blueprint is on a feature branch while PR #1 is pending; use manual service creation with that branch for preview. After merge, change the configured branch to main. Do not use a main-branch Blueprint link until render.yaml is merged.

## Free-tier boundaries

- Render free web services sleep after 15 minutes without inbound traffic; first visits can be slow. Usage is shared with other free services in the workspace. Do not use keep-alive pings to imply always-on reliability.
- Render free local files are ephemeral. Application data goes to Aiven; there is no local SQLite in the hosted configuration.
- This deploy runs FastAPI directly behind Render's TLS proxy, not the Compose Nginx/Grafana/Prometheus services. The app enforces a bounded per-username login throttle (10 attempts/minute) in its single worker. Hosted /metrics is disabled by default; Compose explicitly enables internal metrics.
- n8n is separate. Keep it in local Docker with its persistent volume for free demonstrations; update imported workflow URLs to `https://YOUR-APP.onrender.com/api/automation/KIND` and configure the private Header Auth credential. Workflows run only while your local n8n instance is running.
- n8n 2 does not support MySQL for its own storage. Do not point n8n's internal database at Aiven MySQL. Its HTTP workflows can still call this MySQL-backed HealthOps API.
- Aiven free MySQL has limited capacity and may pause inactive services. Monitor free-tier usage; no availability guarantees are claimed.

References: https://aiven.io/docs/products/mysql/concepts/mysql-free-tier ; https://render.com/docs/free ; https://docs.n8n.io/hosting/configuration/supported-databases-settings/

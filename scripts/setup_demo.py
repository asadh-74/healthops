"""Generate local configuration without printing secrets; never overwrite it."""

from pathlib import Path
import secrets

p = Path(".env")
if p.exists():
    raise SystemExit(".env already exists; left unchanged.")
p.write_text(
    "\n".join(
        ["POSTGRES_USER=healthops", "POSTGRES_DB=healthops"]
        + [
            f"{key}={secrets.token_hex(24)}"
            for key in [
                "POSTGRES_PASSWORD",
                "GRAFANA_PASSWORD",
                "JWT_SECRET",
                "AUTOMATION_TOKEN",
                "DEMO_PASSWORD",
                "N8N_ENCRYPTION_KEY",
            ]
        ]
    )
    + "\n"
)
p.chmod(0o600)
print("Created .env. Read DEMO_PASSWORD locally to sign in; never share this file.")

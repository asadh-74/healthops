"""Single-instance free Render startup: migrate, optionally seed, then serve."""

import os
import subprocess
import sys

if not os.getenv("MYSQL_HOST") and not os.getenv("DATABASE_URL"):
    raise SystemExit("Configure a persistent database before deployment.")
subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
if os.getenv("SEED_DEMO", "false").lower() == "true":
    subprocess.run([sys.executable, "-m", "app.seed"], check=True)
os.execvp(
    "uvicorn",
    ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", os.getenv("PORT", "10000"), "--workers", "1"],
)

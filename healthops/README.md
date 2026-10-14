# 🏥 HealthOps — Public Health Vaccination & Stock Platform (DevOps Project)

![CI](https://github.com/YOUR_USERNAME/healthops/actions/workflows/ci.yml/badge.svg)

A production-style, fully containerised platform for a **government health department** to manage
vaccination appointments and monitor clinic vaccine stock — built to demonstrate an end-to-end
**DevOps workflow**: containerisation, CI/CD, security scanning, reverse proxy and observability.

## The real-world problem

District clinics often run out of vaccines unnoticed, while patients are booked for doses that don't exist.
Health officials have no live view of stock across facilities. HealthOps solves this:

- Booking an appointment **atomically decrements stock** and rejects bookings when stock is exhausted.
- `/stock/low` shows which facilities need urgent resupply.
- Live **Grafana dashboards** track total doses per vaccine and API health.
- **No PII is stored** — patients are referenced by pseudonymous IDs (privacy-by-design).

## Architecture

```mermaid
flowchart LR
  U[Client / Clinic App] --> N[Nginx<br/>rate-limit + security headers]
  N --> A[FastAPI API<br/>non-root container]
  A --> D[(PostgreSQL 16<br/>persistent volume)]
  P[Prometheus] -- scrapes /metrics --> A
  G[Grafana] --> P
  GH[GitHub Actions] -- test · lint · Trivy scan · push --> R[(GHCR image registry)]
```

## DevOps features

| Area | Implementation |
|---|---|
| Containerisation | Multi-stage Dockerfile, slim base, **non-root user**, `HEALTHCHECK` |
| Orchestration | Docker Compose with health-gated startup (`depends_on: service_healthy`) |
| Network security | API not exposed directly; isolated `backend`/`frontend` networks; `/metrics` blocked at proxy |
| Reverse proxy | Nginx with rate limiting, security headers, hidden version |
| CI/CD | GitHub Actions: Ruff lint → Pytest → Docker build → **Trivy CVE scan** → push to GHCR |
| Observability | Prometheus metrics (request latency, errors, custom stock gauge) + Grafana |
| Secrets | `.env` based config, never committed |
| Testing | Pytest integration tests of the booking flow |

## Quick start

```bash
git clone https://github.com/YOUR_USERNAME/healthops.git && cd healthops
cp .env.example .env          # edit the passwords
docker compose up -d --build
```

| Service | URL |
|---|---|
| API docs (Swagger) | http://localhost/docs |
| Health check | http://localhost/health |
| Grafana | http://localhost:3000 (user `admin`) |

### Try it

```bash
curl -X POST localhost/facilities -H 'Content-Type: application/json' \
  -d '{"name":"Rural Clinic A","district":"North"}'
curl -X PUT localhost/stock -H 'Content-Type: application/json' \
  -d '{"facility_id":1,"vaccine":"MMR","doses":100}'
curl -X POST localhost/appointments -H 'Content-Type: application/json' \
  -d '{"facility_id":1,"patient_ref":"p-10001","vaccine":"MMR","slot":"2026-11-01T09:00:00"}'
curl "localhost/stock/low?threshold=200"
```

In Grafana → Explore, query `healthops_total_doses` or `rate(http_requests_total[1m])`.

## Run tests locally

```bash
make test
```

## Roadmap / production hardening

- Alembic migrations, JWT/OIDC auth with role-based access (nurse / district officer)
- TLS via Let's Encrypt (Traefik/Caddy), Terraform for AWS (ECS/EC2 + RDS)
- Alertmanager rules for low stock and 5xx rate, centralised logging (Loki)
- Kubernetes manifests / Helm chart

## Tech stack
Python 3.12 · FastAPI · SQLAlchemy · PostgreSQL · Docker · Docker Compose · Nginx · Prometheus · Grafana · GitHub Actions · Trivy

# Portfolio presentation

## Title
HealthOps — Full-Stack Clinic Operations & n8n Automation

## Upwork description
Designed and implemented a full-stack clinic operations demonstration using React, TypeScript, FastAPI, PostgreSQL, and Docker. The application includes role-based access, vaccine batch and expiry tracking, transactional booking, stock transfers with approval, and audit history. Four importable n8n workflows automate operational checks and produce deduplicated notifications in a safe demo inbox. GitHub Actions runs API tests, builds the frontend, and scans the container image.

## CV bullets
- Built a React/TypeScript and FastAPI clinic operations platform with role-based access, batch inventory, appointment management, and approval-based stock transfers.
- Integrated n8n workflow templates for low-stock checks, appointment reminders, expiry reviews, and daily reports, with authenticated API access and duplicate-event protection.
- Added transactional stock reservations, audit history, automated integration tests, Docker packaging, and CI/CD checks.

Use these statements after reviewing and demonstrating the implementation yourself. Do not claim real clinical deployment, healthcare compliance, customer adoption, or measured business improvements.

## Three-minute walkthrough
1. Sign in with the configured demo admin account. Show overview and fictional clinic labels.
2. Receive a vaccine batch and explain expiry tracking.
3. Book a DEMO patient appointment; show the available stock decrease. Cancel it and show restoration.
4. Request a transfer, approve it as administrator, and show the source/destination balance.
5. Run a low-stock preview, then show the demo inbox and audit history.
6. In n8n, show an imported workflow with the credential selector closed. Execute it and show the deduplication result.
7. Briefly show the CI run and architecture. Clearly label the demo as fictional.

Never capture `.env`, tokens, the password input, credential editors, private email addresses, or real patient information. Screenshots should come from the running application, not a design mockup.

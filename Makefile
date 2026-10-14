up:      ; docker compose up -d --build
down:    ; docker compose down
logs:    ; docker compose logs -f api
test:    ; pip install -q -r requirements-dev.txt && pytest -q
lint:    ; ruff check .

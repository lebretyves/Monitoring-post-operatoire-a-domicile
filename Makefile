up:
	docker compose up --build

start-demo:
	powershell -ExecutionPolicy Bypass -File .\start-demo.ps1

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

seed:
	docker compose exec backend python /workspace/scripts/seed_patients.py

validate-rules:
	python scripts/validate_rules.py

test-backend:
	docker compose exec backend pytest app/tests -q

refresh-alerts:
	docker compose exec backend python /workspace/scripts/backfill_alert_uncertainty.py

llm-up:
	docker compose up -d ollama

llm-pull:
	powershell -ExecutionPolicy Bypass -File .\scripts\setup_ollama_model.ps1

# Type checking et qualité de code
check-frontend:
	cd services/frontend && npm run typecheck

check-backend:
	docker compose exec backend mypy app/

lint-backend:
	docker compose exec backend ruff check app/

format-backend:
	docker compose exec backend ruff format app/

check-all: check-frontend check-backend lint-backend

pre-commit: check-all test-backend
	@echo "✓ Toutes les vérifications passées"


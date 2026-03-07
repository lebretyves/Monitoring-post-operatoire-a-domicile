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
	docker compose --profile llm up -d ollama

llm-download:
	powershell -ExecutionPolicy Bypass -File .\scripts\download_meditron_gguf.ps1

llm-import:
	powershell -ExecutionPolicy Bypass -File .\scripts\setup_ollama_model.ps1

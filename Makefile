.PHONY: up down logs migrate seed test

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f brain-core

db-shell:
	docker compose exec db psql -U brain -d secondbrain

api-shell:
	docker compose exec brain-core bash

restart:
	docker compose restart brain-core

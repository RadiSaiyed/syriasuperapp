.PHONY: run db up down test

run:
	uvicorn app.main:app --reload --host $${APP_HOST:-0.0.0.0} --port $${APP_PORT:-8092}

db:
	docker compose -f docker-compose.yml up -d db

up:
	docker compose -f docker-compose.yml up --build api

down:
	docker compose -f docker-compose.yml down

test:
	pytest -q


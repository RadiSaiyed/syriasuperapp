run:
	uvicorn app.main:app --host $${APP_HOST:-0.0.0.0} --port $${APP_PORT:-8095} --reload

up:
	docker compose up --build api

db:
	docker compose up -d db

down:
	docker compose down -v


run:
	uvicorn app.main:app --host $${APP_HOST:-0.0.0.0} --port $${APP_PORT:-8096} --reload

db:
	docker compose up -d db

api:
	docker compose up --build api


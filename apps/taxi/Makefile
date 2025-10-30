SHELL := /bin/sh

compose := docker compose
compose_dev := docker compose -f docker-compose.yml -f docker-compose.override.yml
DB_URL_COMPOSE := postgresql+psycopg2://postgres:postgres@db:5432/taxi

.PHONY: up-db build migrate up-api logs health down clean e2e test-container test-one test-host

up-db:
	$(compose) up -d db

build:
	$(compose) build api

migrate:
	mkdir -p alembic/versions
	$(compose) run --rm -v "$(PWD)":/app api sh -lc '
	  DB_URL=$(DB_URL_COMPOSE) alembic revision --autogenerate -m "init" || true && \
	  DB_URL=$(DB_URL_COMPOSE) alembic upgrade head'

up-api:
	$(compose) up -d api

logs:
	$(compose) logs -f api

health:
	curl -sS http://localhost:8081/health || true

down:
	$(compose) down

clean:
	$(compose) down -v

# --- Testing helpers ---
test-container:
	@echo "[tests] Starting dev deps (db, redis) and running pytest in container...";
	$(compose_dev) up -d db redis >/dev/null ; \
	$(compose_dev) run --rm --entrypoint "" api bash -lc 'pytest -q /app/apps/taxi/tests'

test-one:
	@[ -n "$(F)" ] || (echo "Usage: make test-one F=test_file.py" && exit 1)
	@echo "[tests] Running single test $(F) in container...";
	$(compose_dev) up -d db redis >/dev/null ; \
	$(compose_dev) run --rm --entrypoint "" api bash -lc 'pytest -q /app/apps/taxi/tests/$(F)'

test-host:
	@set -e; \
	export PYTHONPATH="$(PWD)/../../libs/superapp_shared"; \
	pytest -q

e2e:
	@set -e; \
	BASE=http://localhost:8081; \
	$(compose) up -d db api >/dev/null; \
	TS=$$(date +%s); A="+9639002$${TS%100000}"; B="+9639003$${TS%100000}"; \
	curl -s $$BASE/auth/request_otp -H 'Content-Type: application/json' -d '{"phone":"'"$$A"'"}' >/dev/null || true; \
	TOK_A=$$(curl -s $$BASE/auth/verify_otp -H 'Content-Type: application/json' -d '{"phone":"'"$$A"'","otp":"123456","name":"Ali"}' | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))'); \
	curl -s $$BASE/auth/request_otp -H 'Content-Type: application/json' -d '{"phone":"'"$$B"'"}' >/dev/null || true; \
	TOK_B=$$(curl -s $$BASE/auth/verify_otp -H 'Content-Type: application/json' -d '{"phone":"'"$$B"'","otp":"123456","name":"Driver"}' | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))'); \
	curl -s -X POST $$BASE/driver/apply -H "Authorization: Bearer $$TOK_B" -H 'Content-Type: application/json' -d '{"vehicle_make":"Toyota","vehicle_plate":"ABC"}' >/dev/null; \
	curl -s -X PUT $$BASE/driver/status -H "Authorization: Bearer $$TOK_B" -H 'Content-Type: application/json' -d '{"status":"available"}' >/dev/null; \
	curl -s -X PUT $$BASE/driver/location -H "Authorization: Bearer $$TOK_B" -H 'Content-Type: application/json' -d '{"lat":33.5138, "lon":36.2765}' >/dev/null; \
	RID=$$(curl -s -X POST $$BASE/rides/request -H "Authorization: Bearer $$TOK_A" -H 'Content-Type: application/json' -d '{"pickup_lat":33.5138,"pickup_lon":36.2765,"dropoff_lat":33.52,"dropoff_lon":36.28}' | python3 -c 'import sys,json; print(json.load(sys.stdin).get("id",""))'); \
	curl -s -X POST $$BASE/rides/$$RID/accept -H "Authorization: Bearer $$TOK_B" | sed -n '1p'; \
	curl -s -X POST $$BASE/rides/$$RID/start -H "Authorization: Bearer $$TOK_B" | sed -n '1p'; \
	curl -s -X POST $$BASE/rides/$$RID/complete -H "Authorization: Bearer $$TOK_B" | sed -n '1p'

.PHONY: e2e-full
e2e-full:
	@set -e; \
	# Start Payments and Taxi services
	cd ../payments && docker compose up -d db redis api >/dev/null; \
	cd - >/dev/null; \
	$(compose) up -d db redis api >/dev/null; \
	bash ../../tools/e2e/taxi_payments_e2e.sh

.PHONY: wallet-smoke
wallet-smoke:
	@set -e; \
	# Start Taxi service (DB+API) then run wallet smoke
	$(compose) up -d db api >/dev/null; \
	bash ../../tools/e2e/taxi_wallet_smoke.sh

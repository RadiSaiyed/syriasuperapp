.PHONY: run db up down test test-container test-one test-host

SHELL := /bin/sh

compose := docker compose
compose_dev := docker compose -f docker-compose.yml -f docker-compose.override.yml

run:
	uvicorn app.main:app --reload --host $${APP_HOST:-0.0.0.0} --port $${APP_PORT:-8092}

db:
	$(compose) -f docker-compose.yml up -d db

up:
	$(compose) -f docker-compose.yml up --build api

down:
	$(compose) -f docker-compose.yml down

test:
	pytest -q

# --- Testing helpers ---
test-container:
	@echo "[tests] Starting dev deps (db, redis) and running pytest in container...";
	$(compose_dev) up -d db redis >/dev/null ; \
	$(compose_dev) run --rm --entrypoint "" api bash -lc 'pytest -q /app/apps/flights/tests'

test-one:
	@[ -n "$(F)" ] || (echo "Usage: make test-one F=test_file.py" && exit 1)
	@echo "[tests] Running single test $(F) in container...";
	$(compose_dev) up -d db redis >/dev/null ; \
	$(compose_dev) run --rm --entrypoint "" api bash -lc 'pytest -q /app/apps/flights/tests/$(F)'

test-host:
	@set -e; \
	export PYTHONPATH="$(PWD)/../../libs/superapp_shared"; \
	pytest -q

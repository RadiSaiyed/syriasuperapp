SHELL := /bin/sh

compose := docker compose
compose_dev := docker compose -f docker-compose.yml -f docker-compose.override.yml

.PHONY: run up db down test-container test-one test-host

run:
	uvicorn app.main:app --host $${APP_HOST:-0.0.0.0} --port $${APP_PORT:-8091} --reload

up:
	$(compose) up --build api

db:
	$(compose) up -d db

down:
	$(compose) down -v

# --- Testing helpers ---
test-container:
	@echo "[tests] Reset DB volume and run pytest in container...";
	$(compose_dev) down -v >/dev/null 2>&1 || true; \
	$(compose_dev) up -d db redis >/dev/null ; \
	$(compose_dev) run --rm --entrypoint "" api bash -lc 'pytest -q /app/apps/chat/tests'

test-one:
	@[ -n "$(F)" ] || (echo "Usage: make test-one F=test_file.py" && exit 1)
	@echo "[tests] Running single test $(F) in container...";
	$(compose_dev) up -d db redis >/dev/null ; \
	$(compose_dev) run --rm --entrypoint "" api bash -lc 'pytest -q /app/apps/chat/tests/$(F)'

test-host:
	@set -e; \
	export PYTHONPATH="$(PWD)/../../libs/superapp_shared"; \
	pytest -q

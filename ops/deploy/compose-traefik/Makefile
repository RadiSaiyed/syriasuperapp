SHELL := /bin/bash
COMPOSE := docker compose --env-file .env.prod -f docker-compose.yml

.PHONY: up down logs ps restart images pull

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f --tail=200

ps:
	$(COMPOSE) ps

restart:
	$(COMPOSE) down
	$(COMPOSE) up -d

images:
	@echo "Build and push all images via tools/docker_push_all.sh"
	@echo "Example: ORG=myorg TAG=$$(git rev-parse --short HEAD) bash ../../tools/docker_push_all.sh"

# --- Backups (Postgres) ---
.PHONY: backup backup-all

# Usage:
#  make backup APP=payments [PGPASSWORD=secret]
#  make backup-all
backup:
	@set -euo pipefail; \
	set -a; [ -f .env.prod ] && . ./.env.prod || true; set +a; \
	APP_VAL="$(APP)"; \
	if [ -z "$$APP_VAL" ]; then echo "Provide APP=<payments|taxi|automarket|bus|chat|commerce|doctors|food|freight|jobs|stays|utilities>" >&2; exit 2; fi; \
	# Map app -> host/db inside 'internal' network
	db_host_for() { case "$$1" in \
	  payments) echo payments-db;; \
	  taxi) echo taxi-db;; \
	  automarket|carmarket) echo automarket-db;; \
	  bus) echo bus-db;; \
	  chat) echo chat-db;; \
	  commerce) echo commerce-db;; \
	  doctors) echo doctors-db;; \
	  food) echo food-db;; \
	  freight) echo freight-db;; \
	  jobs) echo jobs-db;; \
	  stays) echo stays-db;; \
	  utilities) echo utilities-db;; \
	  *) echo "";; esac; }; \
	db_name_for() { case "$$1" in \
	  payments) echo payments;; \
	  taxi) echo taxi;; \
	  automarket|carmarket) echo automarket;; \
	  bus) echo bus;; \
	  chat) echo chat;; \
	  commerce) echo commerce;; \
	  doctors) echo doctors;; \
	  food) echo food;; \
	  freight) echo freight;; \
	  jobs) echo jobs;; \
	  stays) echo stays;; \
	  utilities) echo utilities;; \
	  *) echo "";; esac; }; \
	H=$$(db_host_for "$$APP_VAL"); DB=$$(db_name_for "$$APP_VAL"); \
	if [ -z "$$H" ] || [ -z "$$DB" ]; then echo "Unknown APP=$$APP_VAL" >&2; exit 2; fi; \
	mkdir -p backups; TS=$$(date -u +%Y%m%d_%H%M%S); OUT=backups/$$APP_VAL_$${TS}.dump; \
	PGPASS=$${PGPASSWORD:-postgres}; \
	echo "[backup] $$APP_VAL -> $$OUT"; \
	docker run --rm --network internal -e PGPASSWORD="$$PGPASS" -v "$$PWD/backups:/backups" postgres:16-alpine \
	  sh -lc "pg_dump -h $$H -U postgres -p 5432 -d $$DB -Fc -Z 9 -f /backups/$$(basename \"$$OUT\")"; \
	if [ -n "$${S3_BUCKET:-}" ]; then \
	  echo "[backup] Uploading $$OUT to s3://$${S3_BUCKET}/$${S3_PREFIX:-superapp}/"; \
	  docker run --rm -v "$$PWD/backups:/backups" --network none \
	    -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN -e AWS_DEFAULT_REGION \
	    amazon/aws-cli:2.18.18 s3 cp \
	    "/backups/$$(basename \"$$OUT\")" \
	    "s3://$${S3_BUCKET}/$${S3_PREFIX:-superapp}/$$(basename \"$$OUT\")" --only-show-errors \
	    || { echo "[error] S3 upload failed" >&2; exit 1; }; \
	fi; \
	echo "[backup] Done: $$OUT"

backup-all:
	@set -euo pipefail; \
	for a in payments taxi automarket bus chat commerce doctors food freight jobs stays utilities; do \
	  $(MAKE) backup APP=$$a || { echo "[warn] backup failed for $$a" >&2; }; \
	done

# Chat-only helpers
.PHONY: up-chat down-chat logs-chat ps-chat restart-chat up-traefik

up-chat:
	$(COMPOSE) up -d traefik chat-db chat-redis chat-api

down-chat:
	$(COMPOSE) rm -sf chat-api chat-redis chat-db

logs-chat:
	$(COMPOSE) logs -f --tail=200 chat-api

ps-chat:
	$(COMPOSE) ps chat-api chat-redis chat-db traefik

restart-chat:
	$(COMPOSE) rm -sf chat-api
	$(COMPOSE) up -d chat-api

up-traefik:
	$(COMPOSE) up -d traefik

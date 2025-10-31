SHELL := /bin/sh

.PHONY: help e2e taxi-e2e e2e-full payments-up taxi-up tests freight-tests freight-up stays-up stays-seed food-seed

# Defaults
STAYS_DB_URL ?= postgresql+psycopg2://postgres:postgres@localhost:5441/stays
FOOD_DB_URL ?= postgresql+psycopg2://postgres:postgres@localhost:5443/food
# Default BFF base for local dev; can be overridden: make core-reseed BFF_BASE=http://127.0.0.1:8070
BFF_BASE ?= http://localhost:8070

help:
	@echo "Targets:"
	@echo "  payments-up  - start Payments (db, redis, api)"
	@echo "  taxi-up      - start Taxi (db, redis, api)"
	@echo "  taxi-e2e     - run Taxi local e2e (apps/taxi: e2e)"
	@echo "  taxi-demo    - demo Taxi flow via BFF (rider+driver on same token)"
	@echo "  e2e-full     - run cross-service E2E (Payments + Taxi)"
	@echo "  tests        - run Taxi test suite"
	@echo "  freight-up   - start Freight (db, redis, api)"
	@echo "  freight-tests- run Freight API tests"
	@echo "  stays-up     - start Stays (db, redis, api)"
	@echo "  stays-seed   - seed demo data for Stays"
	@echo "  food-seed    - seed demo data for Food"
	@echo "  stays-reset  - drop+create Stays schema (DANGEROUS)"
	@echo "  stays-reset-seed - reset then seed demo data"
	@echo "  ios-create-ipad - create 'Demo iPad' simulator (best effort)"
	@echo "  run-superapp-ipad - run Super‑App on 'Demo iPad' simulator"
	@echo "  ios-create-iphone - create 'Demo iPhone' simulator (best effort)"
	@echo "  run-superapp-iphone - run Super‑App on 'Demo iPhone' with prod defines"
	@echo "  run-superapp-iphone-dev - run Super‑App on 'Demo iPhone' against local BFF ($(BFF_BASE))"
	@echo "  bff-up       - start BFF (Backend for Frontend)"
	@echo "  bff-down     - stop BFF"
	@echo "  bff-run      - run BFF via Python (local)"
	@echo "  up-all       - start Payments + Food (db, redis, api)"
	@echo "  seed-all     - seed demo data (Food)"
	@echo "  down-all     - stop Payments + Food"
	@echo "  prod-audit   - static production readiness audit"
	@echo "  prod-env     - generate deploy/.env.prod with strong secrets"
	@echo "  prod-build   - build & push images (ORG=your_dockerhub_user TAG=$(git rev-parse --short HEAD))"
	@echo "  prod-deploy  - bring up Traefik + services via deploy compose"
	@echo "  clean-all    - remove build/cache artifacts repo-wide"
	@echo "  scaffold-alembic - add Alembic templates to apps/*"
	@echo "  hetzner-env  - load Hetzner env and prep SSH key"
	@echo "  hetzner-ssh  - SSH into Hetzner server from .env"
	@echo "  hetzner-hcloud - list Hetzner servers (hcloud CLI)"
	@echo "  hetzner-tf-init  - terraform init (Hetzner)"
	@echo "  hetzner-tf-plan  - terraform plan (Hetzner)"
	@echo "  hetzner-tf-apply - terraform apply (Hetzner)"
	@echo "  hetzner-tf-output - terraform output (Hetzner)"
	@echo "  hetzner-cloud-init - render cloud-init from .env"
	@echo "  hetzner-tf-apply-cloudinit - apply with rendered cloud-init"
	@echo "  hetzner-tf-apply-dns-zone - apply and create DNS zone (manage_zone=true)"
	@echo "  hetzner-dns-apply-core - apply DNS for payments,taxi via API"
	@echo "  hetzner-deploy-remote - rsync compose bundle to Hetzner host and up"
	@echo "  health       - run monorepo health check (tools/health_check.sh)"
	@echo "  deploy-health - run health checks against deploy compose (APP=payments|STACK=core)"
	@echo "  taxi-driver-up - start Taxi Driver operator API"
	@echo "  food-operator-up - start Food Operator API"
	@echo "  food-courier-up - start Food Courier API"
	@echo "  bus-operators-up - start Bus Operators API"
	@echo "  stays-host-up - start Stays Host API"
	@echo "  realestate-owner-up - start Real Estate Owner API"
	@echo "  doctors-doctor-up - start Doctors (Doctor) API"
	@echo "  livestock-seller-up - start Livestock Seller API"
	@echo "  freight-shipper-up - start Freight Shipper API"
	@echo "  freight-carrier-up - start Freight Carrier API"
	@echo "  jobs-employer-up - start Jobs Employer API"
	@echo "  agriculture-farmer-up - start Agriculture Farmer API"
	@echo "  taxi-partners-up - start Taxi Partners API"
	@echo "  payments-merchant-up - start Payments Merchant API"
	@echo "  taxi-driver-migrate - run Taxi Driver DB migrations"
	@echo "  taxi-partners-migrate - run Taxi Partners DB migrations"
	@echo "  payments-merchant-migrate - run Payments Merchant DB migrations"

payments-up:
	cd apps/payments && docker compose up -d db redis api

taxi-up:
	cd apps/taxi && docker compose up -d db redis api

taxi-e2e:
	$(MAKE) -C apps/taxi e2e

e2e-full:
	$(MAKE) -C apps/taxi e2e-full

tests:
	PYTHONPATH=apps/taxi:libs/superapp_shared \
	DB_URL=postgresql+psycopg2://postgres:postgres@localhost:5434/taxi \
	pytest -q apps/taxi/tests

# Quick Taxi demo: verify OTP via BFF, apply as driver, topup wallet, request a ride, accept, start, complete
taxi-demo:
	@set -e; \
	BFF=$(BFF_BASE); \
	PHONE=$${PHONE:-+963901234568}; \
	NAME=$${NAME:-Dev User}; \
	echo "[taxi-demo] BFF=$$BFF"; \
	TOK=$$(curl -fsS -X POST "$$BFF/auth/verify_otp" -H 'Content-Type: application/json' -d '{"phone":"'"$$PHONE"'","otp":"123456","name":"'"$$NAME"'"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'); \
	H="Authorization: Bearer $$TOK"; \
	echo "[taxi-demo] Apply driver..."; \
	curl -fsS -X POST "$$BFF/taxi/driver/apply" -H "$$H" -H 'Content-Type: application/json' -d '{"vehicle_make":"Toyota","vehicle_plate":"ABC-123"}' | jq -c '.'; \
	echo "[taxi-demo] Set available..."; \
	curl -fsS -X PUT "$$BFF/taxi/driver/status" -H "$$H" -H 'Content-Type: application/json' -d '{"status":"available"}' | jq -c '.'; \
	echo "[taxi-demo] Topup taxi wallet..."; \
	curl -fsS -X POST "$$BFF/taxi/driver/taxi_wallet/topup" -H "$$H" -H 'Content-Type: application/json' -d '{"amount_cents":1000}' | jq -c '.'; \
	echo "[taxi-demo] Request ride..."; \
	RID=$$(curl -fsS -X POST "$$BFF/taxi/rides/request" -H "$$H" -H 'Content-Type: application/json' -d '{"pickup_lat":33.5138,"pickup_lon":36.2765,"dropoff_lat":33.5000,"dropoff_lon":36.3000}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])'); \
	echo "[taxi-demo] Accept ride $$RID ..."; \
	curl -fsS -X POST "$$BFF/taxi/rides/$$RID/accept" -H "$$H" | jq -c '.'; \
	echo "[taxi-demo] Start ride..."; \
	curl -fsS -X POST "$$BFF/taxi/rides/$$RID/start" -H "$$H" | jq -c '.'; \
	echo "[taxi-demo] Move near drop and complete..."; \
	curl -fsS -X PUT "$$BFF/taxi/driver/location" -H "$$H" -H 'Content-Type: application/json' -d '{"lat":33.5000,"lon":36.3000}' | jq -c '.'; \
	curl -fsS -X POST "$$BFF/taxi/rides/$$RID/complete" -H "$$H" | jq -c '.'; \
	echo "[taxi-demo] done"

freight-up:
	cd apps/freight && docker compose up -d db redis api

freight-tests:
	PYTHONPATH=apps/freight:libs/superapp_shared \
	DB_URL=postgresql+psycopg2://postgres:postgres@localhost:5438/freight \
	pytest -q apps/freight/tests

stays-up:
	cd apps/stays && docker compose up -d db redis api

stays-seed:
	PYTHONPATH=apps/stays DB_URL=$(STAYS_DB_URL) python3 apps/stays/seed_demo.py

food-seed:
	PYTHONPATH=apps/food DB_URL=$(FOOD_DB_URL) python3 apps/food/seed_demo.py

stays-reset:
	PYTHONPATH=apps/stays DB_URL=$(STAYS_DB_URL) python3 apps/stays/reset_demo.py

stays-reset-seed:
	$(MAKE) stays-reset
	$(MAKE) stays-seed

ios-create-ipad:
	@set -e; \
	rid=$$(xcrun simctl list runtimes | awk -F'[()]' '/iOS /{id=$$2} END{print id}'); \
	if [ -z "$$rid" ]; then echo 'No iOS runtime found'; exit 0; fi; \
	dt=$$(xcrun simctl list devicetypes | awk -F'[()]' '/iPad \(10th generation\)/{print $$2; found=1} END{if(!found){exit 1}}') || dt=$$(xcrun simctl list devicetypes | awk -F'[()]' '/^\s*iPad /{print $$2; exit}'); \
	name='Demo iPad'; \
	if ! xcrun simctl list devices available | grep -q "$$name"; then xcrun simctl create "$$name" "$$dt" "$$rid" && echo Created $$name; fi

run-superapp-ipad:
	open -a Simulator || true
	$(MAKE) ios-create-ipad
	- xcrun simctl boot "Demo iPad"
	cd clients/superapp_flutter && ../../tools/flutter/bin/flutter pub get
	@DEVICE=$$(../../tools/flutter/bin/flutter devices | awk '/Demo iPad/{print $$1}' | head -n1); \
	 if [ -z "$$DEVICE" ]; then DEVICE="Demo iPad"; fi; \
	 cd clients/superapp_flutter && ../../tools/flutter/bin/flutter run -d "$$DEVICE" -t lib/main.dart

ios-create-iphone:
	@set -e; \
	rid=$$(xcrun simctl list runtimes | awk -F'[()]' '/iOS /{id=$$2} END{print id}'); \
	if [ -z "$$rid" ]; then echo 'No iOS runtime found'; exit 0; fi; \
	dt=$$(xcrun simctl list devicetypes | awk -F'[()]' '/iPhone 15 Pro/{print $$2; found=1} END{if(!found){exit 1}}') || dt=$$(xcrun simctl list devicetypes | awk -F'[()]' '/^\s*iPhone /{print $$2; exit}'); \
	name='Demo iPhone'; \
	if ! xcrun simctl list devices available | grep -q "$$name"; then xcrun simctl create "$$name" "$$dt" "$$rid" && echo Created $$name; fi

run-superapp-iphone:
	open -a Simulator || true
	$(MAKE) ios-create-iphone
	- BOOT=$$(xcrun simctl list devices | awk -F'[()]' '/Demo iPhone/{print $$2; exit}'); if [ -n "$$BOOT" ]; then xcrun simctl boot "$$BOOT"; fi || true
	cd clients/superapp_flutter/ios && pod install || true
	cd clients/superapp_flutter && ../../tools/flutter/bin/flutter pub get
	@DEVICE=$$(tools/flutter/bin/flutter devices | awk '/Demo iPhone/{print $$1}' | head -n1); \
	 if [ -z "$$DEVICE" ]; then DEVICE="Demo iPhone"; fi; \
	cd clients/superapp_flutter && ../../tools/flutter/bin/flutter run -d "$$DEVICE" --release --dart-define-from-file=dart_defines/prod.json

run-superapp-iphone-dev:
	open -a Simulator || true
	$(MAKE) ios-create-iphone
	- BOOT=$$(xcrun simctl list devices | awk -F'[()]' '/Demo iPhone/{print $$2; exit}'); if [ -n "$$BOOT" ]; then xcrun simctl boot "$$BOOT"; fi || true
	cd clients/superapp_flutter/ios && pod install || true
	cd clients/superapp_flutter && ../../tools/flutter/bin/flutter pub get
	@DEVICE=$$(tools/flutter/bin/flutter devices | awk '/Demo iPhone/{print $$1}' | head -n1); \
	 if [ -z "$$DEVICE" ]; then DEVICE="Demo iPhone"; fi; \
	cd clients/superapp_flutter && ../../tools/flutter/bin/flutter run -d "$$DEVICE" -t lib/main.dart --dart-define=SUPERAPP_API_BASE=$(BFF_BASE)

bff-up:
	cd apps/bff && docker compose up -d --build

bff-down:
	cd apps/bff && docker compose down || true

bff-run:
	ENV=dev APP_PORT=8070 PYTHONPATH=. python3 -m apps.bff.app.main

# Core stack helpers (Payments, Chat, Commerce, Stays, BFF)
core-up:
	cd apps/payments && docker compose up -d db redis api
	cd apps/chat && docker compose up -d db redis api
	cd apps/commerce && docker compose up -d db redis api
	cd apps/stays && docker compose up -d db redis api
	cd apps/bff && docker compose up -d --build

core-down:
	cd apps/bff && docker compose down || true
	cd apps/stays && docker compose down || true
	cd apps/commerce && docker compose down || true
	cd apps/chat && docker compose down || true
	cd apps/payments && docker compose down || true

smoke-core:
	./tools/dev_smoke.sh $(BFF_BASE)

core-reseed:
	@set -e; \
	BFF=$(BFF_BASE); \
	PHONE=${PHONE:-+963901234568}; \
	NAME=${NAME:-Dev User}; \
	echo "[reseed] BFF=$$BFF"; \
	TOK=$$(curl -fsS -X POST "$$BFF/auth/verify_otp" -H 'Content-Type: application/json' -d '{"phone":"'"$$PHONE"'","otp":"123456","name":"'"$$NAME"'"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'); \
	curl -fsS -X POST "$$BFF/stays/dev/seed" -H "Authorization: Bearer $$TOK" -H 'Content-Type: application/json' | jq -c '.'; \
	curl -fsS -X POST "$$BFF/chat/dev/seed" -H "Authorization: Bearer $$TOK" -H 'Content-Type: application/json' | jq -c '.'; \
	echo "[reseed] done"

core-logs:
	@echo "Tailing core logs (Ctrl-C to stop)"; \
	docker logs -f payments-api & \
	docker logs -f chat-api & \
	docker logs -f commerce-api & \
	docker logs -f stays-api & \
	docker logs -f superapp-bff & \
	wait

up-all:
	cd apps/payments && docker compose up -d db redis api
	cd apps/food && docker compose up -d db redis api

seed-all:
	$(MAKE) food-seed

down-all:
	cd apps/food && docker compose down || true
	cd apps/payments && docker compose down || true

food-migrate:
	cd apps/food && DB_URL=postgresql+psycopg2://postgres:postgres@localhost:5443/food alembic upgrade head

operator-demo:
	@set -e; \
	FOOD=http://localhost:8090; OP=http://localhost:8095; \
	echo '[demo] ensure stacks up'; \
	cd apps/food && docker compose up -d db redis api >/dev/null; cd - >/dev/null; \
	cd operators/food_operator && docker compose up -d api >/dev/null; cd - >/dev/null; \
	echo '[demo] create owner and user tokens'; \
	OWNER_TOKEN=$$(curl -fsS -X POST $$FOOD/auth/verify_otp -H 'Content-Type: application/json' -d '{"phone":"+963911111111","otp":"123456","name":"Owner"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'); \
	USER_TOKEN=$$(curl -fsS -X POST $$FOOD/auth/verify_otp -H 'Content-Type: application/json' -d '{"phone":"+963922222222","otp":"123456","name":"Customer"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'); \
	H_OWNER="Authorization: Bearer $$OWNER_TOKEN"; H_USER="Authorization: Bearer $$USER_TOKEN"; \
	RID=$$(curl -fsS $$FOOD/restaurants -H "$$H_OWNER" | python3 -c 'import json,sys; print(json.load(sys.stdin)[-1]["id"])'); \
	echo '[demo] become owner of' $$RID; \
	curl -fsS -X POST "$$FOOD/admin/dev/become_owner?restaurant_id=$$RID" -H "$$H_OWNER" >/dev/null; \
	MI=$$(curl -fsS $$FOOD/restaurants/$$RID/menu -H "$$H_USER" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])'); \
	echo '[demo] place order'; \
	curl -fsS -X POST $$FOOD/cart/items -H "$$H_USER" -H 'Content-Type: application/json' -d '{"menu_item_id":"'$$MI'","qty":1}' >/dev/null; \
	OID=$$(curl -fsS -X POST $$FOOD/orders/checkout -H "$$H_USER" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'); \
	echo '[demo] order id' $$OID; \
	OP_TOKEN=$$(curl -fsS -X POST $$OP/auth/verify_otp -H 'Content-Type: application/json' -d '{"phone":"+963900000012","otp":"123456","name":"Operator"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'); \
	H_OP="Authorization: Bearer $$OP_TOKEN"; \
	curl -fsS -X POST $$OP/operator/dev/become_admin -H "$$H_OP" >/dev/null; \
	echo '[demo] advance statuses'; \
	for s in accepted preparing out_for_delivery delivered; do curl -fsS -X POST "$$OP/operator/orders/$$OID/status?status_value=$$s" -H "$$H_OP" >/dev/null; done; \
	echo '[demo] SLA:'; \
	curl -fsS "$$OP/operator/reports/sla?days=7" -H "$$H_OP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d)'; \
	echo '[demo] Summary:'; \
	curl -fsS "$$OP/operator/reports/summary?days=7" -H "$$H_OP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d)'; \
	echo '[demo] Done.'

prod-audit:
	python3 tools/prod_audit.py

prod-env:
	python3 tools/gen_prod_env.py --out ops/deploy/compose-traefik/.env.prod

prod-build:
	@if [ -z "$$ORG" ]; then echo "Set ORG env var (Docker Hub org/username)" >&2; exit 1; fi; \
	TAG=$${TAG:-$$(git rev-parse --short HEAD)}; \
	REGISTRY=$${REGISTRY:-docker.io}; \
	REGISTRY="$$REGISTRY" ORG="$$ORG" TAG="$$TAG" bash tools/docker_push_all.sh

prod-deploy:
	./sup deploy up

scaffold-alembic:
	python3 tools/scaffold_alembic.py

# --- Hetzner helpers ---
hetzner-env:
	bash -lc 'source ops/deploy/hetzner/env.sh'

# --- Cleanup helpers ---
.PHONY: clean-all clean-caches clean-files

clean-caches:
	@echo "[clean] Removing common cache/build folders..."
	@find . \
	  -type d \( \
	    -name '__pycache__' -o \
	    -name '.pytest_cache' -o \
	    -name '.mypy_cache' -o \
	    -name '.ruff_cache' -o \
	    -name 'node_modules' -o \
	    -name 'dist' -o \
	    -name 'build' -o \
	    -name '.dart_tool' -o \
	    -name '.gradle' -o \
	    -name 'Pods' -o \
	    -name 'DerivedData' -o \
	    -name '.parcel-cache' -o \
	    -name '.turbo' -o \
	    -name '.next' -o \
	    -name '.nuxt' -o \
	    -name '.svelte-kit' -o \
	    -name '.idea' -o \
	    -name '.vscode' \
	  \) -prune -exec rm -rf {} +

clean-files:
	@echo "[clean] Removing temp files..."
	@find . -type f \( -name '.DS_Store' -o -name '*.log' -o -name '*.tmp' -o -name '*.swp' -o -name '*.swo' -o -name '*.pid' -o -name '.coverage*' -o -name 'coverage.xml' -o -name 'junit*.xml' \) -delete

clean-all: clean-caches clean-files
	@echo "[clean] Done."

hetzner-ssh:
	bash -lc 'source ops/deploy/hetzner/env.sh && USER=${HETZNER_SSH_USER:-root}; if [ -z "${HETZNER_IPV4:-}" ]; then echo "Missing HETZNER_IPV4 in .env" >&2; exit 1; fi; ssh $HETZNER_SSH_OPTS "$$USER@${HETZNER_IPV4}"'

hetzner-hcloud:
	bash -lc 'source ops/deploy/hetzner/env.sh && command -v hcloud >/dev/null 2>&1 || { echo "Install hcloud CLI: https://github.com/hetznercloud/cli"; exit 1; }; hcloud server list'

hetzner-tf-init:
	bash -lc 'source ops/deploy/hetzner/env.sh && cd ops/deploy/hetzner/terraform && terraform init'

hetzner-tf-plan:
	bash -lc 'source ops/deploy/hetzner/env.sh && cd ops/deploy/hetzner/terraform && terraform plan'

hetzner-tf-apply:
	bash -lc 'source ops/deploy/hetzner/env.sh && cd ops/deploy/hetzner/terraform && terraform apply'

hetzner-tf-output:
	bash -lc 'cd ops/deploy/hetzner/terraform && terraform output'

hetzner-cloud-init:
	bash -lc 'ops/deploy/hetzner/render_cloud_init.sh'

hetzner-tf-apply-cloudinit:
	bash -lc 'source ops/deploy/hetzner/env.sh && CI_FILE=$$(ops/deploy/hetzner/render_cloud_init.sh) && export TF_VAR_user_data="$$(cat $$CI_FILE)" && cd ops/deploy/hetzner/terraform && terraform apply'

hetzner-tf-apply-dns-zone:
	bash -lc 'source ops/deploy/hetzner/env.sh && cd ops/deploy/hetzner/terraform && TF_VAR_manage_zone=true terraform apply'

hetzner-dns-apply-core:
	bash -lc 'source ops/deploy/hetzner/env.sh && python3 ops/deploy/hetzner/dns_apply.py payments taxi'

hetzner-deploy-remote:
	bash -lc 'ops/deploy/hetzner/remote_deploy.sh'

taxi-driver-up:
	cd operators/taxi_driver && docker compose up -d db redis api

food-operator-up:
	cd operators/food_operator && docker compose up -d api

food-with-operator-up:
	cd apps/food && docker compose up -d db redis api
	cd operators/food_operator && docker compose up -d api

food-with-operator-seed:
	$(MAKE) food-with-operator-up
	$(MAKE) food-seed

food-courier-up:
	cd operators/food_courier && docker compose up -d db redis api

bus-operators-up:
	cd operators/bus_operators && docker compose up -d db redis api

stays-host-up:
	cd operators/stays_host && docker compose up -d db redis api

realestate-owner-up:
	cd operators/realestate_owner && docker compose up -d db api

doctors-doctor-up:
	cd operators/doctors_doctor && docker compose up -d db redis api

livestock-seller-up:
	cd operators/livestock_seller && docker compose up -d db redis api

freight-shipper-up:
	cd operators/freight_shipper && docker compose up -d db redis api

freight-carrier-up:
	cd operators/freight_carrier && docker compose up -d db redis api

jobs-employer-up:
	cd operators/jobs_employer && docker compose up -d db redis api

agriculture-farmer-up:
	cd operators/agriculture_farmer && docker compose up -d db redis api

taxi-partners-up:
	cd operators/taxi_partners && docker compose up -d db redis api

payments-merchant-up:
	cd operators/payments_merchant_api && docker compose up -d db redis api

taxi-driver-migrate:
	cd operators/taxi_driver && docker compose run --rm migrate

taxi-partners-migrate:
	cd operators/taxi_partners && docker compose run --rm migrate

payments-merchant-migrate:
	cd operators/payments_merchant_api && docker compose run --rm migrate

# --- Health helpers ---
health:
	bash tools/health_check.sh

# --- iOS Payments demo ---
.PHONY: ios-payments-demo
ios-payments-demo:
	bash tools/start_ios_payments_sims.sh

deploy-health:
	@set -euo pipefail; \
	cd ops/deploy/compose-traefik; \
	APP_VAL="$(APP)"; STACK_VAL="$(STACK)"; \
	if [ -z "$$APP_VAL$$STACK_VAL" ]; then APP_VAL=payments; fi; \
	# Mapping helpers
	svc_url() { case "$$1" in \
	  payments-api) echo http://payments-api:8080/health;; \
	  taxi-api) echo http://taxi-api:8081/health;; \
	  automarket-api) echo http://automarket-api:8086/health;; \
	  bus-api) echo http://bus-api:8082/health;; \
	  chat-api) echo http://chat-api:8091/health;; \
	  commerce-api) echo http://commerce-api:8083/health;; \
	  doctors-api) echo http://doctors-api:8089/health;; \
	  food-api) echo http://food-api:8090/health;; \
	  freight-api) echo http://freight-api:8085/health;; \
	  jobs-api) echo http://jobs-api:8087/health;; \
	  stays-api) echo http://stays-api:8088/health;; \
	  utilities-api) echo http://utilities-api:8084/health;; \
	  *) echo "";; esac; }; \
	svcs_for_app() { case "$$1" in \
	  payments) echo "payments-api payments-worker payments-beat";; \
	  taxi) echo "taxi-api taxi-reaper";; \
	  food) echo "food-api";; \
	  freight) echo "freight-api";; \
	  bus) echo "bus-api";; \
	  commerce) echo "commerce-api";; \
	  doctors) echo "doctors-api";; \
	  automarket|carmarket) echo "automarket-api";; \
	  utilities) echo "utilities-api";; \
	  stays) echo "stays-api";; \
	  chat) echo "chat-api";; \
	  jobs) echo "jobs-api";; \
	  *) echo "";; esac; }; \
	svcs_for_stack() { case "$$1" in \
	  core) echo "payments-api payments-worker payments-beat";; \
	  food) echo "food-api";; \
	  commerce) echo "commerce-api";; \
	  taxi) echo "taxi-api taxi-reaper";; \
	  doctors) echo "doctors-api";; \
	  bus) echo "bus-api";; \
	  freight) echo "freight-api";; \
	  utilities) echo "utilities-api";; \
	  automarket|carmarket) echo "automarket-api";; \
	  chat) echo "chat-api";; \
	  stays) echo "stays-api";; \
	  jobs) echo "jobs-api";; \
	  *) echo "";; esac; }; \
	if [ -n "$$STACK_VAL" ]; then SVCS=$$(svcs_for_stack "$$STACK_VAL"); else SVCS=$$(svcs_for_app "$$APP_VAL"); fi; \
	if [ -z "$$SVCS" ]; then echo "Unknown APP/STACK. Use APP=payments or STACK=core,food,…" >&2; exit 1; fi; \
	for s in $$SVCS; do \
	  URL=$$(svc_url "$$s"); \
	  [ -z "$$URL" ] && { echo "[skip] $$s (no HTTP health)"; continue; }; \
	  echo "[health] $$s -> $$URL"; \
	  docker run --rm --network internal curlimages/curl:8.10.1 -fsS -m 5 $$URL >/dev/null || { echo "Health check failed for $$s" >&2; exit 1; }; \
	done

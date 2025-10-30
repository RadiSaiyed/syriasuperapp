SHELL := /bin/sh

compose := docker compose
compose_dev := docker compose -f docker-compose.yml -f docker-compose.override.yml

.PHONY: networks payments-up food-up up down health food-webhook e2e

networks:
	@docker network create web >/dev/null 2>&1 || true
	@docker network create internal >/dev/null 2>&1 || true

payments-up: networks
	@echo "[payments] Starting db, redis, api..."
	@cd ../payments && $(compose) up -d db redis api
	@echo "[payments] Health:"; curl -sS http://localhost:8080/health || true

food-up: networks
	@echo "[food] Starting db, redis, api..."
	@$(compose_dev) up -d db redis api
	@echo "[food] Health:"; curl -sS http://localhost:8090/health || true

up: payments-up food-up

down:
	@cd ../payments && $(compose) down -v || true
	@$(compose_dev) down -v || true

health:
	@curl -sS http://localhost:8080/health || true
	@curl -sS http://localhost:8090/health || true

food-webhook:
	@set -e; \
	BASE="http://localhost:8080"; \
	FEE="+963999999999"; \
	SECRET="demo_secret"; \
	URL="http://host.docker.internal:8090/payments/webhooks"; \
	echo "[payments] Login fee wallet $$FEE"; \
	TOK=$$(curl -s $$BASE/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"'"$$FEE"'","otp":"123456","name":"Operator"}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('access_token',''))
PY
); \
	[ -n "$$TOK" ] || { echo "[payments] could not obtain token"; exit 1; }; \
	curl -s -X POST $$BASE/payments/dev/become_merchant -H "Authorization: Bearer $$TOK" >/dev/null; \
	echo "[payments] Register webhook $$URL"; \
	curl -s -X POST "$$BASE/webhooks/endpoints?url=$$URL&secret=$$SECRET" -H "Authorization: Bearer $$TOK" | sed -n '1p';

# E2E: customer adds a menu item and checks out -> Payments request -> accept in Payments -> verify orders
e2e:
	@set -e; \
	FOOD=http://localhost:8090; PAY=http://localhost:8080; \
	# Login users
	TOK_C=$$(curl -s $$FOOD/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"+963900000001","otp":"123456","name":"Customer"}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('access_token',''))
PY
); \
	TOK_O=$$(curl -s $$FOOD/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"+963900000010","otp":"123456","name":"Owner"}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('access_token',''))
PY
); \
	# Try find restaurant & menu; if none, create minimal via operator+admin
	RID=$$(curl -s $$FOOD/restaurants -H "Authorization: Bearer $$TOK_C" | python3 - <<'PY'
import sys,json
arr=json.load(sys.stdin) or []
print(arr[0]['id'] if arr else '')
PY
); \
	if [ -z "$$RID" ]; then \
	  echo "[food] No restaurants found; creating one..."; \
	  curl -s -X POST $$FOOD/operator/dev/become_admin -H "Authorization: Bearer $$TOK_O" >/dev/null; \
	  RID=$$(curl -s -X POST "$$FOOD/operator/restaurants?name=Demo%20Resto&city=Damascus&address=Main" -H "Authorization: Bearer $$TOK_O" | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('id',''))
PY
); \
	  curl -s -X POST "$$FOOD/admin/dev/become_owner?restaurant_id=$$RID" -H "Authorization: Bearer $$TOK_O" >/dev/null; \
	fi; \
	MI=$$(curl -s $$FOOD/restaurants/$$RID/menu -H "Authorization: Bearer $$TOK_C" | python3 - <<'PY'
import sys,json
arr=json.load(sys.stdin) or []
print(arr[0]['id'] if arr else '')
PY
); \
	if [ -z "$$MI" ]; then \
	  echo "[food] No menu items; creating one as owner..."; \
	  MI=$$(curl -s -X POST "$$FOOD/admin/restaurants/$$RID/menu?name=Kebab&price_cents=20000" -H "Authorization: Bearer $$TOK_O" | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('id',''))
PY
); \
	fi; \
	echo "[food] Add to cart & checkout"; \
	curl -s -X POST $$FOOD/cart/items -H "Authorization: Bearer $$TOK_C" -H 'Content-Type: application/json' --data-raw '{"menu_item_id":"'"$$MI"'","qty":1}' >/dev/null; \
	ORD=$$(curl -s -X POST $$FOOD/orders/checkout -H "Authorization: Bearer $$TOK_C" | sed -n '1p'); echo $$ORD; \
	PR=$$(echo $$ORD | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('payment_request_id',''))
PY
); \
	if [ -n "$$PR" ]; then \
	  TOKU=$$(curl -s $$PAY/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"+963900000001","otp":"123456","name":"Customer"}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('access_token',''))
PY
); \
	  curl -s -X POST $$PAY/requests/$$PR/accept -H "Authorization: Bearer $$TOKU" | sed -n '1p'; \
	fi; \
	echo "[food] My orders:"; curl -s $$FOOD/orders -H "Authorization: Bearer $$TOK_C" | sed -n '1p'


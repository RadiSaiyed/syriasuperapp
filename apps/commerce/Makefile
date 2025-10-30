SHELL := /bin/sh

compose := docker compose
compose_dev := docker compose -f docker-compose.yml -f docker-compose.override.yml

.PHONY: networks payments-up commerce-up up down health e2e

networks:
	@docker network create web >/dev/null 2>&1 || true
	@docker network create internal >/dev/null 2>&1 || true

payments-up: networks
	@echo "[payments] Starting db, redis, api..."
	@cd ../payments && $(compose) up -d db redis api
	@echo "[payments] Health:"; curl -sS http://localhost:8080/health || true

commerce-up: networks
	@echo "[commerce] Starting db, redis, api..."
	@$(compose_dev) up -d db redis api
	@echo "[commerce] Health:"; curl -sS http://localhost:8083/health || true

up: payments-up commerce-up

down:
	@cd ../payments && $(compose) down -v || true
	@$(compose_dev) down -v || true

health:
	@curl -sS http://localhost:8080/health || true
	@curl -sS http://localhost:8083/health || true

# E2E: user picks a product and checks out -> Payments request -> accept in Payments
e2e:
	@set -e; \
	BASE=http://localhost:8083; PAY=http://localhost:8080; \
	TOK=$$(curl -s $$BASE/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"+963900000001","otp":"123456","name":"Buyer"}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('access_token',''))
PY
); \
	# Find a product (shops endpoint seeds demo data if empty)
	SID=$$(curl -s $$BASE/shops -H "Authorization: Bearer $$TOK" | python3 - <<'PY'
import sys,json; arr=json.load(sys.stdin) or []
print(arr[0]['id'] if arr else '')
PY
); \
	PID=$$(curl -s $$BASE/shops/$$SID/products -H "Authorization: Bearer $$TOK" | python3 - <<'PY'
import sys,json; arr=json.load(sys.stdin) or []
print(arr[0]['id'] if arr else '')
PY
); \
	echo "[commerce] Add to cart & checkout"; \
	curl -s -X POST $$BASE/cart/items -H "Authorization: Bearer $$TOK" -H 'Content-Type: application/json' --data-raw '{"product_id":"'"$$PID"'","qty":1}' >/dev/null; \
	ORD=$$(curl -s -X POST $$BASE/orders/checkout -H "Authorization: Bearer $$TOK" | sed -n '1p'); echo $$ORD; \
	PR=$$(echo $$ORD | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('payment_request_id',''))
PY
); \
	if [ -n "$$PR" ]; then \
	  TOKU=$$(curl -s $$PAY/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"+963900000001","otp":"123456","name":"Buyer"}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('access_token',''))
PY
); \
	  curl -s -X POST $$PAY/requests/$$PR/accept -H "Authorization: Bearer $$TOKU" | sed -n '1p'; \
	fi; \
	echo "[commerce] My orders:"; curl -s $$BASE/orders -H "Authorization: Bearer $$TOK" | sed -n '1p'


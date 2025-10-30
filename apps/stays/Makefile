SHELL := /bin/sh

compose := docker compose
compose_dev := docker compose -f docker-compose.yml -f docker-compose.override.yml

.PHONY: networks payments-up stays-up up down health stays-webhook e2e

networks:
	@docker network create web >/dev/null 2>&1 || true
	@docker network create internal >/dev/null 2>&1 || true

payments-up: networks
	@echo "[payments] Starting db, redis, api..."
	@cd ../payments && $(compose) up -d db redis api
	@echo "[payments] Health:"; curl -sS http://localhost:8080/health || true

stays-up: networks
	@echo "[stays] Starting db, redis, api..."
	@$(compose_dev) up -d db redis api
	@echo "[stays] Health:"; curl -sS http://localhost:8088/health || true

up: payments-up stays-up

down:
	@cd ../payments && $(compose) down -v || true
	@$(compose_dev) down -v || true

health:
	@curl -sS http://localhost:8080/health || true
	@curl -sS http://localhost:8088/health || true

stays-webhook:
	@set -e; \
	BASE="http://localhost:8080"; \
	FEE="+963999999999"; \
	SECRET="demo_secret"; \
	URL="http://host.docker.internal:8088/payments/webhooks"; \
	echo "[payments] Login fee wallet $$FEE"; \
	TOK=$$(curl -s $$BASE/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"'"$$FEE"'","otp":"123456","name":"Operator"}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('access_token',''))
PY
); \
	[ -n "$$TOK" ] || { echo "[payments] could not obtain token"; exit 1; }; \
	curl -s -X POST $$BASE/payments/dev/become_merchant -H "Authorization: Bearer $$TOK" >/dev/null; \
	echo "[payments] Register webhook $$URL"; \
	curl -s -X POST "$$BASE/webhooks/endpoints?url=$$URL&secret=$$SECRET" -H "Authorization: Bearer $$TOK" | sed -n '1p';

# E2E: host creates property+unit, guest reserves -> Payment Request -> accept in Payments
e2e:
	@set -e; \
	ST=http://localhost:8088; PAY=http://localhost:8080; \
	# Login host & guest
	TOK_H=$$(curl -s $$ST/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"+963900000010","otp":"123456","name":"Host","role":"host"}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('access_token',''))
PY
); \
	TOK_G=$$(curl -s $$ST/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"+963900000001","otp":"123456","name":"Guest","role":"guest"}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('access_token',''))
PY
); \
	# Create property (idempotent enough for dev)
	PROP=$$(curl -s -X POST $$ST/host/properties -H "Authorization: Bearer $$TOK_H" -H 'Content-Type: application/json' --data-raw '{"name":"Demo Apt","type":"apartment","city":"Damascus","description":"Demo","address":"Main","latitude":33.51,"longitude":36.28}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('id',''))
PY
); \
	# Create a unit
	UNIT=$$(curl -s -X POST $$ST/host/properties/$$PROP/units -H "Authorization: Bearer $$TOK_H" -H 'Content-Type: application/json' --data-raw '{"name":"Unit A","capacity":2,"total_units":5,"price_cents_per_night":20000,"min_nights":1,"cleaning_fee_cents":2000,"amenities":["wifi","ac"]}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('id',''))
PY
); \
	# Reserve for 1 night starting tomorrow
	CI=$$(python3 - <<'PY'
import datetime; print((datetime.date.today()+datetime.timedelta(days=1)).isoformat())
PY
); \
	CO=$$(python3 - <<'PY'
import datetime; print((datetime.date.today()+datetime.timedelta(days=2)).isoformat())
PY
); \
	RES=$$(curl -s -X POST $$ST/reservations -H "Authorization: Bearer $$TOK_G" -H 'Content-Type: application/json' --data-raw '{"unit_id":"'"$$UNIT"'","check_in":"'"$$CI"'","check_out":"'"$$CO"'","guests":1}' | sed -n '1p'); echo $$RES; \
	PR=$$(echo $$RES | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('payment_request_id',''))
PY
); \
	if [ -n "$$PR" ]; then \
	  TOKU=$$(curl -s $$PAY/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"+963900000001","otp":"123456","name":"Guest"}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('access_token',''))
PY
); \
	  curl -s -X POST $$PAY/requests/$$PR/accept -H "Authorization: Bearer $$TOKU" | sed -n '1p'; \
	fi; \
	echo "[stays] My reservations:"; curl -s $$ST/reservations -H "Authorization: Bearer $$TOK_G" | sed -n '1p'


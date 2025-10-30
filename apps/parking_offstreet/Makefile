SHELL := /bin/sh

compose := docker compose
compose_dev := docker compose -f docker-compose.yml -f docker-compose.override.yml

.PHONY: networks payments-up offstreet-up up down health payments-webhook e2e-reservation e2e-exit e2e logs

networks:
	@docker network create web >/dev/null 2>&1 || true
	@docker network create internal >/dev/null 2>&1 || true

payments-up: networks
	@echo "[payments] Starting db, redis, api..."
	@cd ../payments && $(compose) up -d db redis api
	@echo "[payments] Health:"; curl -sS http://localhost:8080/health || true

offstreet-up: networks
	@echo "[offstreet] Starting db, api..."
	@$(compose_dev) up -d db api
	@echo "[offstreet] Health:"; curl -sS http://localhost:8097/health || true

up: payments-up offstreet-up

down:
	@cd ../payments && $(compose) down -v || true
	@$(compose_dev) down -v || true

health:
	@curl -sS http://localhost:8080/health || true
	@curl -sS http://localhost:8097/health || true

# Registers Off-Street webhook in Payments and ensures fee wallet is a merchant.
# Uses defaults from apps/payments/.env and apps/parking_offstreet/docker-compose.override.yml
payments-webhook:
	@set -e; \
	BASE="http://localhost:8080"; \
	FEE="+963999999999"; \
	SECRET="demo_secret"; \
	URL="http://host.docker.internal:8097/payments/webhooks"; \
	echo "[payments] Login fee wallet $$FEE"; \
	TOK=$$(curl -s $$BASE/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"'"$$FEE"'","otp":"123456","name":"Operator"}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('access_token',''))
PY
); \
	[ -n "$$TOK" ] || { echo "[payments] could not obtain token"; exit 1; }; \
	curl -s -X POST $$BASE/payments/dev/become_merchant -H "Authorization: Bearer $$TOK" >/dev/null; \
	echo "[payments] Register webhook $$URL"; \
	curl -s -X POST "$$BASE/webhooks/endpoints?url=$$URL&secret=$$SECRET" -H "Authorization: Bearer $$TOK" | sed -n '1p';

# E2E: create reservation -> Payment Request -> accept in Payments -> status in Off-Street
e2e-reservation:
	@set -e; \
	OFFBASE="http://localhost:8097"; PAYBASE="http://localhost:8080"; \
	# JWT for Off-Street
	JWT=$$(python3 - <<'PY'
import jwt,time
print(jwt.encode({"sub":"00000000-0000-0000-0000-000000000002","phone":"+963900000001","exp":int(time.time())+3600}, "change_me_in_dev", algorithm="HS256"))
PY
); \
	# Facility
	FAC=$$(curl -s "$$OFFBASE/facilities/near?lat=33.5100&lon=36.2750" -H "Authorization: Bearer $$JWT" | python3 - <<'PY'
import sys,json; arr=json.load(sys.stdin); print(arr[0]['id'] if arr else '')
PY
); \
	[ -n "$$FAC" ] || { echo "[offstreet] no facility found"; exit 1; }; \
	# Times (use python for portability)
	FROM=$$(python3 - <<'PY'
import datetime; print((datetime.datetime.utcnow()+datetime.timedelta(minutes=2)).replace(microsecond=0).isoformat()+"Z")
PY
); \
	TO=$$(python3 - <<'PY'
import datetime; print((datetime.datetime.utcnow()+datetime.timedelta(minutes=122)).replace(microsecond=0).isoformat()+"Z")
PY
); \
	RES=$$(curl -s -X POST $$OFFBASE/reservations -H "Authorization: Bearer $$JWT" -H 'Content-Type: application/json' --data-raw '{"facility_id":"'"$$FAC"'","from_ts":"'"$$FROM"'","to_ts":"'"$$TO"'"}'); \
	echo "[offstreet] reservation:"; echo $$RES | sed -n '1p'; \
	PR=$$(echo $$RES | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('payment_request_id',''))
PY
); \
	[ -n "$$PR" ] || { echo "[offstreet] no payment_request_id returned"; exit 1; }; \
	# Accept in Payments as user
	TOKU=$$(curl -s $$PAYBASE/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"+963900000001","otp":"123456","name":"User"}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('access_token',''))
PY
); \
	curl -s -X POST $$PAYBASE/requests/$$PR/accept -H "Authorization: Bearer $$TOKU" | sed -n '1p'; \
	echo "[offstreet] operator payment_status:"; \
	curl -s "$$OFFBASE/operator/payment_status?request_id=$$PR" -H "Authorization: Bearer $$JWT" | sed -n '1p'

# E2E: start entry -> stop (creates payment request) -> accept -> status
e2e-exit:
	@set -e; \
	OFFBASE="http://localhost:8097"; PAYBASE="http://localhost:8080"; \
	JWT=$$(python3 - <<'PY'
import jwt,time
print(jwt.encode({"sub":"00000000-0000-0000-0000-000000000002","phone":"+963900000001","exp":int(time.time())+3600}, "change_me_in_dev", algorithm="HS256"))
PY
); \
	FAC=$$(curl -s "$$OFFBASE/facilities/near?lat=33.5100&lon=36.2750" -H "Authorization: Bearer $$JWT" | python3 - <<'PY'
import sys,json; arr=json.load(sys.stdin); print(arr[0]['id'] if arr else '')
PY
); \
	EID=$$(curl -s -X POST $$OFFBASE/entries/start -H "Authorization: Bearer $$JWT" -H 'Content-Type: application/json' --data-raw '{"facility_id":"'"$$FAC"'"}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('id',''))
PY
); \
	STOP=$$(curl -s -X POST $$OFFBASE/entries/$$EID/stop -H "Authorization: Bearer $$JWT"); \
	echo "[offstreet] stop:"; echo $$STOP | sed -n '1p'; \
	PR2=$$(echo $$STOP | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('payment_request_id',''))
PY
); \
	[ -n "$$PR2" ] || { echo "[offstreet] no payment_request_id on stop"; exit 1; }; \
	TOKU=$$(curl -s $$PAYBASE/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"+963900000001","otp":"123456","name":"User"}' | python3 - <<'PY'
import sys,json; print(json.load(sys.stdin).get('access_token',''))
PY
); \
	curl -s -X POST $$PAYBASE/requests/$$PR2/accept -H "Authorization: Bearer $$TOKU" | sed -n '1p'; \
	echo "[offstreet] operator payment_status:"; \
	curl -s "$$OFFBASE/operator/payment_status?request_id=$$PR2" -H "Authorization: Bearer $$JWT" | sed -n '1p'

e2e: up payments-webhook e2e-reservation e2e-exit

logs:
	@$(compose_dev) logs -f api


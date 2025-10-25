SHELL := /bin/sh

compose := docker compose
DB_URL_COMPOSE := postgresql+psycopg2://postgres:postgres@db:5432/payments

.PHONY: up-db build migrate up-api logs health down clean cash-demo e2e sbom audit licenses

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
	curl -sS http://localhost:8080/health || true

down:
	$(compose) down

clean:
	$(compose) down -v

cash-demo:
	@set -e; \
	BASE=http://localhost:8080; \
	$(compose) up -d db api >/dev/null; \
	TS=$$(date +%s); SUF=$$(printf "%06d" $$((TS % 1000000))); \
	A="+9639000$${SUF}"; B="+9639001$${SUF}"; \
	echo "Users: $$A (user) and $$B (agent)"; \
	curl -s $$BASE/auth/request_otp -H 'Content-Type: application/json' --data-raw '{"phone":"'"$$A"'"}' >/dev/null || true; \
	TOK_A=$$(curl -s $$BASE/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"'"$$A"'","otp":"123456","name":"User"}' | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))'); \
	curl -s $$BASE/auth/request_otp -H 'Content-Type: application/json' --data-raw '{"phone":"'"$$B"'"}' >/dev/null || true; \
	TOK_B=$$(curl -s $$BASE/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"'"$$B"'","otp":"123456","name":"Agent"}' | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))'); \
	[ -n "$$TOK_A" ] && [ -n "$$TOK_B" ] || { echo "Auth failed"; exit 1; }; \
	echo "Dev become agent"; \
	curl -s -X POST $$BASE/cash/agents/dev/become_agent -H "Authorization: Bearer $$TOK_B" | sed -n '1p'; \
	echo "Topup agent wallet"; \
	curl -s -X POST $$BASE/wallet/topup -H "Authorization: Bearer $$TOK_B" -H 'Content-Type: application/json' --data-raw '{"amount_cents": 100000, "idempotency_key":"agt-topup-'"$$SUF"'"}' | sed -n '1p'; \
	echo "Create cash-in (user)"; \
	CREQ=$$(curl -s -X POST $$BASE/cash/cashin/request -H "Authorization: Bearer $$TOK_A" -H 'Content-Type: application/json' --data-raw '{"amount_cents":20000}'); \
	echo $$CREQ | sed -n '1p'; \
	RID=$$(echo $$CREQ | python3 -c 'import sys,json; print(json.load(sys.stdin).get("id",""))'); \
	echo "Agent accepts cash-in"; \
	curl -s -X POST $$BASE/cash/requests/$$RID/accept -H "Authorization: Bearer $$TOK_B" | sed -n '1p'; \
	echo "Create cash-out (user)"; \
	CREQ2=$$(curl -s -X POST $$BASE/cash/cashout/request -H "Authorization: Bearer $$TOK_A" -H 'Content-Type: application/json' --data-raw '{"amount_cents":15000}'); \
	echo $$CREQ2 | sed -n '1p'; \
	RID2=$$(echo $$CREQ2 | python3 -c 'import sys,json; print(json.load(sys.stdin).get("id",""))'); \
	echo "Agent accepts cash-out"; \
	curl -s -X POST $$BASE/cash/requests/$$RID2/accept -H "Authorization: Bearer $$TOK_B" | sed -n '1p'; \
	echo "Final balances:"; \
	echo A:; curl -s $$BASE/wallet -H "Authorization: Bearer $$TOK_A" | sed -n '1p'; \
	echo B:; curl -s $$BASE/wallet -H "Authorization: Bearer $$TOK_B" | sed -n '1p'

e2e:
	@set -e; \
	BASE=http://localhost:8080; \
	$(compose) up -d db api >/dev/null; \
	TS=$$(date +%s); SUF=$$(printf "%06d" $$((TS % 1000000))); \
	A="+9639000$${SUF}"; B="+9639001$${SUF}"; \
	echo "Users: $$A and $$B"; \
	curl -s $$BASE/auth/request_otp -H 'Content-Type: application/json' --data-raw '{"phone":"'"$$A"'"}' >/dev/null || true; \
	TOK_A=$$(curl -s $$BASE/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"'"$$A"'","otp":"123456","name":"Ali"}' | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))'); \
	curl -s $$BASE/auth/request_otp -H 'Content-Type: application/json' --data-raw '{"phone":"'"$$B"'"}' >/dev/null || true; \
	TOK_B=$$(curl -s $$BASE/auth/verify_otp -H 'Content-Type: application/json' --data-raw '{"phone":"'"$$B"'","otp":"123456","name":"Omar"}' | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))'); \
	[ -n "$$TOK_A" ] && [ -n "$$TOK_B" ] || { echo "Auth failed"; exit 1; }; \
	echo "Dev KYC approve A & B"; \
	curl -s -X POST $$BASE/kyc/dev/approve -H "Authorization: Bearer $$TOK_A" | sed -n '1p'; \
	curl -s -X POST $$BASE/kyc/dev/approve -H "Authorization: Bearer $$TOK_B" | sed -n '1p'; \
	echo "Topup A and B"; \
	curl -s -X POST $$BASE/wallet/topup -H "Authorization: Bearer $$TOK_A" -H 'Content-Type: application/json' --data-raw '{"amount_cents": 200000, "idempotency_key":"topupA-'"$$SUF"'"}' | sed -n '1p'; \
	curl -s -X POST $$BASE/wallet/topup -H "Authorization: Bearer $$TOK_B" -H 'Content-Type: application/json' --data-raw '{"amount_cents": 150000, "idempotency_key":"topupB-'"$$SUF"'"}' | sed -n '1p'; \
	echo "P2P A->B"; \
	curl -s -X POST $$BASE/wallet/transfer -H "Authorization: Bearer $$TOK_A" -H 'Content-Type: application/json' --data-raw '{"to_phone":"'"$$B"'","amount_cents":12345,"idempotency_key":"p2p-'"$$SUF"'"}' | sed -n '1p'; \
	echo "Become merchant (dev) A"; \
	curl -s -X POST $$BASE/payments/dev/become_merchant -H "Authorization: Bearer $$TOK_A" | sed -n '1p'; \
	echo "Create QR"; \
	QR=$$(curl -s -X POST $$BASE/payments/merchant/qr -H "Authorization: Bearer $$TOK_A" -H 'Content-Type: application/json' --data-raw '{"amount_cents":5000}'); \
	echo $$QR | sed -n '1p'; \
	CODE=$$(echo $$QR | python3 -c 'import sys,json; print(json.load(sys.stdin).get("code",""))'); \
	echo "B pays QR"; \
	curl -s -X POST $$BASE/payments/merchant/pay -H "Authorization: Bearer $$TOK_B" -H 'Content-Type: application/json' --data-raw '{"code":"'"$$CODE"'","idempotency_key":"qr-'"$$SUF"'"}' | sed -n '1p'; \
	echo "Payment request A->B"; \
	REQ=$$(curl -s -X POST $$BASE/requests -H "Authorization: Bearer $$TOK_A" -H 'Content-Type: application/json' --data-raw '{"to_phone":"'"$$B"'","amount_cents":2222}'); \
	echo $$REQ | sed -n '1p'; \
	RID=$$(echo $$REQ | python3 -c 'import sys,json; print(json.load(sys.stdin).get("id",""))'); \
	echo "B accepts request"; \
	curl -s -X POST $$BASE/requests/$$RID/accept -H "Authorization: Bearer $$TOK_B" | sed -n '1p'; \
	echo "Final A:"; curl -s $$BASE/wallet -H "Authorization: Bearer $$TOK_A" | sed -n '1p'; \
	echo "Final B:"; curl -s $$BASE/wallet -H "Authorization: Bearer $$TOK_B" | sed -n '1p'

# --- Supply chain & compliance helpers (local) ---
SBOM_DIR ?= sbom

sbom:
	@echo "[sbom] Generating CycloneDX SBOM for Payments..."
	python -m pip install --upgrade cyclonedx-bom >/dev/null
	pip install -r requirements.txt >/dev/null
	mkdir -p $(SBOM_DIR)
	cyclonedx-bom -o $(SBOM_DIR)/sbom-payments.json >/dev/null
	@echo "[sbom] Wrote $(SBOM_DIR)/sbom-payments.json"

audit:
	@echo "[audit] Running pip-audit..."
	python -m pip install --upgrade pip-audit >/dev/null
	pip-audit -r requirements.txt || true

licenses:
	@echo "[licenses] Collecting Python dependency licenses..."
	python -m pip install --upgrade pip-licenses >/dev/null
	pip-licenses --format=markdown --with-urls --with-authors > $(SBOM_DIR)/licenses-payments.md
	@echo "[licenses] Wrote $(SBOM_DIR)/licenses-payments.md"

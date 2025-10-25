# Taxi + Payments Staging Stack

This docker-compose stack spins up the Payments service, Taxi API, and shared Redis/Postgres instances for realistic end-to-end testing.

## Prerequisites

- Docker Desktop 4.19+
- Copy environment templates and edit secrets:

```bash
cp ops/staging/payments.env.example ops/staging/payments.env
cp ops/staging/taxi.env.example ops/staging/taxi.env
# Edit both files and provide strong secrets, phone numbers, and alert emails.
```

## Running the stack

```bash
cd ops/staging
docker compose up -d --build
```

The services come up with the following default ports:

| Service        | URL                     |
| -------------- | ----------------------- |
| Payments API   | http://localhost:9080   |
| Taxi API       | http://localhost:9081   |

Use `docker compose logs -f taxi-api` to tail the Taxi server.

## Running wallet + escrow e2e smoke

Once the stack is healthy run:

```bash
BASE_TAXI=http://localhost:9081 \
BASE_PAYMENTS=http://localhost:9080 \
ADMIN_TOKEN=$(grep '^ADMIN_TOKEN=' taxi.env | cut -d'= ' -f2) \
../../tools/e2e/taxi_wallet_escrow_e2e.sh
```

The script walks through rider/driver onboarding, escrow prepay, driver wallet top-up, ride completion, and optional cron dispatch.

## Teardown

```bash
cd ops/staging
docker compose down
```

Use `docker compose down -v` to wipe databases between runs.

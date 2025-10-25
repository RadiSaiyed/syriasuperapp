# Compose service examples (Traefik + Prometheus reachability)

Prereqs
- External Docker networks exist: `web` (Traefik) and `internal` (Prometheus/Grafana/Alertmanager)
  - `docker network create web`
  - `docker network create internal`

Pattern
- Give the API container a stable `container_name` that matches Prometheus job targets (e.g., `payments-api`).
- Attach the service to `internal` (for Prometheus scraping) and optionally `web` (for Traefik ingress).
- Add Traefik labels for HTTPS routing; set `${BASE_DOMAIN}` in your environment.

Shared networks block to add at the bottom of each app's compose:
```yaml
networks:
  web:
    external: true
    name: web
  internal:
    external: true
    name: internal
```

Payments API (port 8080)
```yaml
services:
  api:
    container_name: payments-api
    networks: [internal, web]
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=web"
      - "traefik.http.routers.payments.rule=Host(`payments.${BASE_DOMAIN}`)"
      - "traefik.http.routers.payments.entrypoints=websecure"
      - "traefik.http.routers.payments.tls.certresolver=letsencrypt"
      - "traefik.http.services.payments.loadbalancer.server.port=8080"
```

Taxi API (port 8081)
```yaml
services:
  api:
    container_name: taxi-api
    networks: [internal, web]
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=web"
      - "traefik.http.routers.taxi.rule=Host(`taxi.${BASE_DOMAIN}`)"
      - "traefik.http.routers.taxi.entrypoints=websecure"
      - "traefik.http.routers.taxi.tls.certresolver=letsencrypt"
      - "traefik.http.services.taxi.loadbalancer.server.port=8081"
```

Bus (8082), Commerce (8083), Utilities (8084), Freight (8085)
```yaml
# replace <name> and <port>
services:
  api:
    container_name: <name>-api   # e.g., bus-api
    networks: [internal, web]
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=web"
      - "traefik.http.routers.<name>.rule=Host(`<name>.${BASE_DOMAIN}`)"
      - "traefik.http.routers.<name>.entrypoints=websecure"
      - "traefik.http.routers.<name>.tls.certresolver=letsencrypt"
      - "traefik.http.services.<name>.loadbalancer.server.port=<port>"
```

Carmarket (8086), Jobs (8087), Stays (8088), Doctors (8089), Food (8090), Chat (8091)
- Apply the same pattern as above with the respective ports.

Flights (8092), Agriculture (8093), Livestock (8094), Carrental (8095)
- Apply the same pattern with ports.

AI Gateway (8099)
```yaml
services:
  api:
    container_name: ai-gateway
    networks: [internal, web]
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=web"
      - "traefik.http.routers.ai.rule=Host(`ai.${BASE_DOMAIN}`)"
      - "traefik.http.routers.ai.entrypoints=websecure"
      - "traefik.http.routers.ai.tls.certresolver=letsencrypt"
      - "traefik.http.services.ai.loadbalancer.server.port=8099"
```

Notes
- Prometheus scrape targets are defined in `ops/observability/prometheus/prometheus.yml`. Ensure your `container_name` matches those hostnames (e.g., `payments-api:8080`).
- If you cannot set `container_name`, alternatively add a static DNS name via an external Docker network alias on `internal`.
- Keep ports published (`ports:`) for local access; Traefik routes traffic via the `web` network directly to the container port.

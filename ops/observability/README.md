Observability Stack (Prometheus, Grafana, Alertmanager)

Start
- docker compose -f ops/observability/docker-compose.yml up -d
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (set GF_SECURITY_ADMIN_* env to login)
- Alertmanager: http://localhost:9093

Dashboards
- Loaded from ops/observability/grafana/dashboards via provisioning
- Highlights:
  - SuperApp Overview: overall req/s, error rate, p90/p99 latency by service
  - Payments, Taxi, Commerce, Doctors: domain dashboards incl. latency panels
  - Minimal per-service boards: Req/s + p90/p99

Scrape Config (jobs → dashboards)
- See ops/observability/prometheus/prometheus.yml
- Ensure job names match dashboard queries (job label): payments, taxi, bus, commerce, utilities, freight, carmarket, jobs, stays, doctors, food, chat, flights, ai_gateway, agriculture, carrental, livestock, realestate

Alerts
- Generic: ServiceDown, HighErrorRate, HighLatencyP99 (warning), HighLatencyP99Critical (critical)
- Service SLOs: PaymentsHighLatencyP95(+Critical), Taxi/Commerce/Doctors p95 warnings
- Configure Alertmanager env for Slack/Email in docker-compose env


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

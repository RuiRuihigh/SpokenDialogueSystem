COMPOSE_LOCAL=docker compose -f docker-compose.yml -f docker-compose.local-dev.yml
COMPOSE_ONLINE=docker compose -f docker-compose.yml -f docker-compose.online-dev.yml

.PHONY: local_dev online_dev local_down online_down

local_dev:
	$(COMPOSE_LOCAL) up --build

online_dev:
	$(COMPOSE_ONLINE) up --build

local_down:
	$(COMPOSE_LOCAL) down

online_down:
	$(COMPOSE_ONLINE) down

# TransparentRO — comenzi uzuale. Necesită Docker (cu docker compose v2) și GNU make.
COMPOSE = docker compose
ETL = $(COMPOSE) --profile etl run --rm etl
TEST_DB = postgresql+psycopg://tro:tro@db:5432/tro_test

.PHONY: help env up down logs build migrate etl etl-real etl-sample etl-synthetic etl-onrc etl-prod risk \
        test test-api lint e2e clean ps

help:
	@echo "make up             - pornește db + api + web (http://localhost:3000, API http://localhost:8000/docs)"
	@echo "make etl            - import date REALE pentru județele din TARGET_COUNTIES (SEAP+BNR+ANAF+semnale)"
	@echo "make etl-sample     - import real rapid: un singur trimestru (2025 T4)"
	@echo "make etl-synthetic  - generează date SINTETICE (marcate is_synthetic) pentru dezvoltare"
	@echo "make etl-onrc       - completează firmele din registrul ONRC (descarcă ~1 GB)"
	@echo "make etl-prod       - import complet de pe acest calculator direct în baza de PRODUCȚIE (Neon)"
	@echo "make test           - teste pytest (ETL + API) în container"
	@echo "make e2e            - teste Playwright (stack-ul trebuie să ruleze)"
	@echo "make lint           - ruff + mypy"
	@echo "make down / clean   - oprește / șterge și volumele"

env:
	@test -f .env || cp .env.example .env

build: env
	$(COMPOSE) build

up: env
	$(COMPOSE) up -d --build db api web
	@echo "Web: http://localhost:3000  |  API: http://localhost:8000/docs"

down:
	$(COMPOSE) down

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=100

migrate: env
	$(COMPOSE) run --rm api alembic upgrade head

etl: env
	$(ETL) all

etl-real: etl

etl-sample: env
	$(ETL) all --years 2025 --quarters 4

etl-synthetic: env
	$(ETL) synthetic --reset
	$(ETL) risk

# Import în producție (Neon), rulat local: data.gov.ro blochează serverele GitHub.
# Necesită Docker pornit și `vercel login`. Adresa bazei e citită din Vercel într-un fișier
# temporar, șters imediat după citire.
etl-prod: env
	@cd backend && vercel env pull ../.env.prod.tmp --environment production --yes >/dev/null
	@url=$$(grep '^DATABASE_URL_UNPOOLED=' .env.prod.tmp | cut -d= -f2- | tr -d '"\r'); rm -f .env.prod.tmp; \
	  test -n "$$url" || { echo "Nu am găsit DATABASE_URL_UNPOOLED în Vercel"; exit 1; }; \
	  $(COMPOSE) --profile etl run --build --rm -e DATABASE_URL="$$url" etl all

etl-onrc: env
	$(ETL) onrc

risk: env
	$(ETL) risk

test: env
	$(COMPOSE) up -d db
	$(COMPOSE) run --rm -e DATABASE_URL=$(TEST_DB) -e TEST_DATABASE_URL=$(TEST_DB) api pytest -q

lint: env
	$(COMPOSE) run --rm --no-deps api sh -c "ruff check tro tests && ruff format --check tro tests && mypy tro"

e2e:
	cd frontend && npx playwright test

clean:
	$(COMPOSE) --profile etl down -v

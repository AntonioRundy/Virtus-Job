# ─── Virtus Job — Makefile ──────────────────────────────
.PHONY: help setup dev stop clean logs migrate seed test lint format

# Colors
GREEN  := \033[0;32m
YELLOW := \033[0;33m
CYAN   := \033[0;36m
RESET  := \033[0m

help: ## Show this help
	@echo ""
	@echo "$(CYAN)Virtus Job — Development Commands$(RESET)"
	@echo "────────────────────────────────────"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-18s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

setup: ## First-time setup: copy .env, install deps, build containers
	@echo "$(YELLOW)Setting up Virtus Job...$(RESET)"
	@if [ ! -f .env ]; then cp .env.example .env; echo "$(GREEN).env created from .env.example$(RESET)"; fi
	@docker compose build --no-cache
	@echo "$(GREEN)Setup complete. Run 'make dev' to start.$(RESET)"

dev: ## Start all services in development mode
	@echo "$(CYAN)Starting Virtus Job...$(RESET)"
	@docker compose up -d postgres redis
	@sleep 3
	@docker compose up api web

dev-bg: ## Start all services in background
	@docker compose up -d

stop: ## Stop all services
	@docker compose down

clean: ## Stop and remove volumes (destructive)
	@echo "$(YELLOW)Removing all containers and volumes...$(RESET)"
	@docker compose down -v --remove-orphans

logs: ## Tail logs from all services
	@docker compose logs -f

logs-api: ## Tail API logs only
	@docker compose logs -f api

logs-web: ## Tail Web logs only
	@docker compose logs -f web

# ─── Database ───────────────────────────────────────────
migrate: ## Run database migrations
	@docker compose exec api alembic upgrade head

migrate-create: ## Create new migration (usage: make migrate-create MSG="description")
	@docker compose exec api alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Rollback last migration
	@docker compose exec api alembic downgrade -1

seed: ## Seed database with sample data
	@docker compose exec api python -m app.scripts.seed

db-shell: ## Open PostgreSQL shell
	@docker compose exec postgres psql -U virtus -d virtus_job

redis-shell: ## Open Redis CLI
	@docker compose exec redis redis-cli

# ─── Testing & Quality ──────────────────────────────────
test: ## Run all tests
	@docker compose exec api pytest tests/ -v

test-api: ## Run API tests
	@docker compose exec api pytest tests/ -v --tb=short

lint: ## Run linters
	@docker compose exec api ruff check app/
	@docker compose exec web npm run lint

format: ## Format code
	@docker compose exec api ruff format app/
	@docker compose exec web npm run format

typecheck: ## Run type checkers
	@docker compose exec api mypy app/
	@docker compose exec web npm run typecheck

# ─── Utilities ──────────────────────────────────────────
api-shell: ## Open Python shell in API container
	@docker compose exec api python

ps: ## Show running containers
	@docker compose ps

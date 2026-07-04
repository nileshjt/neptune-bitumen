.PHONY: setup start stop crawl logs migrate shell-api shell-crawler

setup:
	cp -n .env.example .env || true
	docker compose pull
	docker compose build

start:
	docker compose up -d
	@echo "Dashboard: http://localhost:3000"
	@echo "API docs:  http://localhost:8000/docs"

stop:
	docker compose down

logs:
	docker compose logs -f

# Trigger all crawlers manually
crawl:
	docker compose exec crawler celery -A tasks call tasks.crawl_all

# Run a specific source: make crawl-source SOURCE=gem_india
crawl-source:
	docker compose exec crawler celery -A tasks call tasks.crawl_source --args '["$(SOURCE)"]'

migrate:
	docker compose exec api alembic upgrade head

shell-api:
	docker compose exec api bash

shell-crawler:
	docker compose exec crawler bash

# Run crawlers locally (requires .env and local postgres/redis)
crawl-local:
	cd crawler && python -c "from tasks import crawl_all; crawl_all()"

# Install dashboard deps locally
dashboard-install:
	cd dashboard && npm install

dashboard-dev:
	cd dashboard && npm run dev

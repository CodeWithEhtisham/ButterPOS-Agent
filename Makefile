.PHONY: up down logs migrate test lint seed

up:
	docker-compose up -d --build

down:
	docker-compose down

logs:
	docker-compose logs -f app

db-shell:
	docker-compose exec db psql -U butterpos -d butterpos_db

redis-shell:
	docker-compose exec redis redis-cli

migrate:
	docker-compose exec app alembic upgrade head

migrate-create:
	docker-compose exec app alembic revision --autogenerate -m "$(msg)"

test:
	docker-compose exec app pytest tests/ -v

lint:
	docker-compose exec app ruff check app/

seed:
	docker-compose exec app python scripts/seed_data.py

format:
	docker-compose exec app ruff format app/

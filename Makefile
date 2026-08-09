.PHONY: install dev build test lint clean docker-up docker-down

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

dev:
	docker compose up -d qdrant
	cd backend && uvicorn app.main:app --reload --port 8000 &
	cd frontend && npm run dev

build:
	cd frontend && npm run build

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down -v

test:
	cd backend && pytest -xvs

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name node_modules -exec rm -rf {} +
	find . -type d -name dist -exec rm -rf {} +

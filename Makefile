.PHONY: install test run frontend-build verify

install:
	python -m venv .venv
	.venv/bin/pip install -r backend/requirements.txt
	cd frontend && npm ci

test:
	.venv/bin/pytest -q

run:
	.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

frontend-build:
	cd frontend && npm run build

verify: test frontend-build


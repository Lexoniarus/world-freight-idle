.PHONY: test coverage frontend-test quality

test:
	pytest

coverage:
	pytest --cov=app --cov-report=term-missing --cov-fail-under=100

frontend-test:
	npm run test:frontend

quality:
	python scripts/quality.py

lint:
	python -m ruff check app tests main.py scripts/quality.py
	python -m ruff format --check app tests main.py scripts/quality.py

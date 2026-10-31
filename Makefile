.PHONY: install parse test test-unit lint
install:
	pip install -e ".[dev]"
parse:
	python scripts/01_parse_statutes.py
	python scripts/02_process_statutes.py
test:
	pytest -q -m "not slow"
test-unit:
	pytest -q -m "unit or contract"
lint:
	ruff check src tests scripts

.PHONY: install run demo lint format test package package-smoke check

install:
	poetry install

run:
	poetry run youai

demo:
	poetry run youai --demo

lint:
	poetry run ruff check .
	poetry run ruff format --check .

format:
	poetry run ruff check --fix .
	poetry run ruff format .

test:
	poetry run pytest

package:
	poetry build --clean --format wheel

package-smoke: package
	poetry run python scripts/smoke_wheel.py

check: lint test package-smoke

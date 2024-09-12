all: format lint test

test:
	pytest

lint: ruff mypy

ruff:
	ruff check --fix .

mypy:
	mypy .

format:
	ruff format .

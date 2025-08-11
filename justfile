all: format lint test-all

test-all: (test 'unit') (test 'integration') (test 'behavior') (test 'e2e')

test TYPE:
	uv run pytest tests/{{TYPE}}/ --cov --cov-report xml
	# NOTE: do not use `.coverage.whatever`, pytest will erase it
	mv coverage.xml coverage.{{TYPE}}.xml

lint: ruff mypy pyright

ruff:
	uv run ruff check --fix .

format:
	uv run ruff format .

mypy:
	uv run mypy .

pyright:
	uv run basedpyright

todo:
	grep --recursive --perl-regexp 'TODO:|FIXME:' ./src/ ./test/

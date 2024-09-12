all: format lint test-all

test-all: (test 'unit') (test 'integration') (test 'behavior') (test 'e2e')

test TYPE:
	pytest tests/{{TYPE}}/ --cov --cov-report xml
	# NOTE: do not use `.coverage.whatever`, pytest will erase it
	mv coverage.xml coverage.{{TYPE}}.xml

lint: ruff mypy

ruff:
	ruff check --fix .

format:
	ruff format .

mypy:
	mypy .

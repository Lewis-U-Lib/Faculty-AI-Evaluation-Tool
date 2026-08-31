.PHONY: all validate build strict review verify test clean

all: validate build

validate:
	python3 scripts/validate.py

strict:
	python3 scripts/validate.py --strict

build:
	python3 scripts/build.py

review:
	python3 scripts/review.py export

verify:
	python3 scripts/verify_sources.py --dois --links --out review/link-report.json

test:
	python3 scripts/selftest.py

clean:
	rm -rf dist review/*.csv

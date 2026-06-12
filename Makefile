.PHONY: help test test-unit test-integration integration

help:
	@echo "Available targets:"
	@echo "  make test             - run full test suite"
	@echo "  make test-unit        - run tests excluding integration"
	@echo "  make test-integration - run Docker/PostgreSQL integration test"
	@echo "  make integration      - alias of test-integration"

# Keep current project workflow by routing through a Python conda pytest launcher.
test:
	python ./scripts/run_pytest_conda.py

test-unit:
	python ./scripts/run_pytest_conda.py -m "not integration"

test-integration:
	python ./scripts/run_pytest_conda.py -q -m integration -rA

integration: test-integration

.PHONY: install dev setup clean lint format test run help

# Default target
help:
	@echo "Available commands:"
	@echo "  setup     - Set up development environment"
	@echo "  install   - Install project dependencies"
	@echo "  dev       - Install project with dev dependencies"
	@echo "  lint      - Run code linting (pycln, isort, black)"
	@echo "  format    - Format code (pycln, isort, black)"
	@echo "  test      - Run tests"
	@echo "  run       - Run the development server"
	@echo "  clean     - Clean up build artifacts"

# Set up development environment
setup: dev
	pre-commit install
	@echo "Development environment set up successfully!"

# Install project dependencies only
install:
	pip install -e .

# Install project with development dependencies
dev:
	pip install -e .[dev]

# Run linting checks
lint:
	pycln --check .
	isort --check-only .
	black --check .

# Format code
format:
	pycln .
	isort .
	black .

# Run tests (update when test framework is added)
test:
	@echo "No tests configured yet"

# Run development server
run:
	uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Clean up build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

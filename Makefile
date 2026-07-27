# Makefile for PTMGenerator2 development tasks

.PHONY: help install install-dev clean clean-pyc test test-cov test-fast lint format \
        type-check pre-commit run build build-clean translations lock lock-check docs

PYTHON ?= python
# Tests select Qt's offscreen platform themselves (see tests/conftest.py), so
# no display or xvfb is needed.
PYTEST ?= $(PYTHON) -m pytest

help:
	@echo "PTMGenerator2 Development Commands"
	@echo "=================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install runtime dependencies"
	@echo "  make install-dev      Install development dependencies"
	@echo "  make lock             Regenerate the per-platform lockfiles"
	@echo "  make lock-check       Verify the lockfiles are up to date"
	@echo ""
	@echo "Code Quality:"
	@echo "  make format           Format code with ruff"
	@echo "  make lint             Run ruff (lint + format check)"
	@echo "  make type-check       Run mypy over core/"
	@echo "  make pre-commit       Run all pre-commit hooks"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run the test suite"
	@echo "  make test-cov         Run with a coverage report"
	@echo "  make test-fast        Run without coverage, stopping at the first failure"
	@echo ""
	@echo "Build:"
	@echo "  make run              Run the application"
	@echo "  make build            Build the executable for this platform"
	@echo "  make build-clean      Remove build artifacts"
	@echo "  make translations     Extract and compile translations"
	@echo "  make docs             Build the Sphinx manual"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean            Remove all generated files"

# -- setup ------------------------------------------------------------------

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e ".[dev,build,docs]"
	pre-commit install

# pyproject.toml declares version RANGES; the lockfiles pin exact versions with
# hashes. Regenerate after changing dependencies.
#
# The locks are PER-PLATFORM, not universal. `--universal` resolves one version
# per package for all three operating systems at once without checking wheel
# coverage, so a package whose wheels differ by platform cannot be expressed --
# pyqt5-qt5 publishes Windows wheels only up to 5.15.2 while Linux and macOS
# reach 5.15.19. Resolving once per platform makes that class of bug impossible.
LOCK_ARGS = --python-version 3.12 --generate-hashes --no-header

lock:
	@command -v uv >/dev/null || { echo "uv is required: pip install uv"; exit 1; }
	@for os in linux windows macos; do \
	  uv pip compile pyproject.toml $(LOCK_ARGS) --python-platform $$os \
	     -o requirements-$$os.lock; \
	  uv pip compile pyproject.toml $(LOCK_ARGS) --python-platform $$os \
	     --extra dev --extra docs -o requirements-dev-$$os.lock; \
	  uv pip compile pyproject.toml $(LOCK_ARGS) --python-platform $$os \
	     --extra build -o requirements-build-$$os.lock; \
	done

lock-check: lock
	@git diff --exit-code -- 'requirements*.lock' \
	  || { echo "Lockfiles are out of date; commit the regenerated files."; exit 1; }

# -- code quality -----------------------------------------------------------

format:
	ruff format .
	ruff check --fix .

lint:
	ruff check --output-format=full .
	ruff format --check --diff .

type-check:
	mypy --config-file pyproject.toml core/

pre-commit:
	pre-commit run --all-files

# -- testing ----------------------------------------------------------------

test:
	$(PYTEST) tests/

test-cov:
	$(PYTEST) tests/ --cov=core --cov=ui --cov-report=term-missing --cov-report=html

test-fast:
	$(PYTEST) tests/ -x -q

# -- build ------------------------------------------------------------------

run:
	$(PYTHON) PTMGenerator2.py

build:
	pyinstaller PTMGenerator2.spec

build-clean:
	rm -rf build dist

# pylupdate5 ships with PyQt5; lrelease does not, so PySide6-Essentials
# provides it as pyside6-lrelease (see the dev extra in pyproject.toml).
translations:
	pylupdate5 PTMGenerator2.py core/*.py ui/*.py \
	  -ts translations/PTMGenerator2_ko.ts translations/PTMGenerator2_en.ts
	pyside6-lrelease translations/PTMGenerator2_ko.ts translations/PTMGenerator2_en.ts

docs:
	$(MAKE) -C docs/manual clean html

# -- maintenance ------------------------------------------------------------

clean-pyc:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete

clean: clean-pyc build-clean
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage coverage.xml

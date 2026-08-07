##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

# ==============================================================================
# Makefile for VECDB Python SDK validation
# ==============================================================================
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := check

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================
# Prefer the platform's explicit Python 3 executable.  Some environments do
# not provide an unversioned `python` command.
PYTHON = python
SOURCE_DIR = src
TARGET_DIRS = $(SOURCE_DIR) tests examples
DOCS_DIR = docs
DOCS_BUILD_DIR = $(DOCS_DIR)/build
DOC_ZIP_PREFIX = $(SDK_NAME)-api-ref

# Optional flag to enable report generation. Use 'gmake <target> REPORT=1'
REPORT ?= 
INTEGRATION_TEST_WORKERS ?= 8
DEBUG ?= 0
INTEGRATION_TEST_PARALLEL_FILES ?= 
# Kept for callers that select a subset of files.  Those files are added to
# the same bounded xdist pool; a second pool oversubscribes the VecDB service.
INTEGRATION_TEST_SERIAL_FILES ?= 
CI_PROJECT_DIR ?= .
WORKER_SCHEDULE ?= worksteal
REPORT_DIR = $(CI_PROJECT_DIR)/reports
LINT_REPORT_DIR = $(REPORT_DIR)/lint
TYPE_CHECK_REPORT_DIR = $(REPORT_DIR)/type_check
UNIT_TEST_REPORT_DIR = $(REPORT_DIR)/unit_test
UNIT_TEST_HTML_REPORT = $(UNIT_TEST_REPORT_DIR)/pytest_report.html
INTEGRATION_TEST_REPORT_DIR = $(REPORT_DIR)/integration_test
INTEGRATION_TEST_HTML_REPORT = $(INTEGRATION_TEST_REPORT_DIR)/pytest_report.html
INTEGRATION_TEST_REPORT_SHARDS_DIR = $(INTEGRATION_TEST_REPORT_DIR)/shards
COVERAGE_REPORT_DIR := $(REPORT_DIR)/coverage
SECURITY_REPORT_DIR := $(REPORT_DIR)/security

# Tools
PYTEST = $(PYTHON) -m pytest
BLACK = black
FLAKE8 = flake8
MYPY = mypy
TOX = tox
BANDIT = bandit

# Build command
BUILD = $(PYTHON) -m build

# Conditional Report Flags
LINT_REPORT_FLAG = $(if $(REPORT), --output-file=$(LINT_REPORT_DIR)/flake8_report.txt,)
TYPE_CHECK_REPORT_FLAG = $(if $(REPORT), --html-report $(TYPE_CHECK_REPORT_DIR)/mypy_html_report,)
UNIT_TEST_JUNIT_FLAG = $(if $(REPORT), --junitxml=$(UNIT_TEST_REPORT_DIR)/pytest_report.xml,)

# Coverage report flags (generated only if REPORT=1)
COVERAGE_XML_FLAG := $(if $(REPORT), --cov-report=xml:$(COVERAGE_REPORT_DIR)/coverage.xml,)
COVERAGE_HTML_FLAG := $(if $(REPORT), --cov-report=html:$(COVERAGE_REPORT_DIR)/html,)
BANDIT_REPORT_FLAG := $(if $(REPORT), -f json -o $(SECURITY_REPORT_DIR)/bandit_report.json,)

SDK_NAME := $(shell $(PYTHON) -c "import pathlib, re, sys; text = pathlib.Path('pyproject.toml').read_text(); match = re.search(r'^name\\s*=\\s*\"([^\"\\n]+)\"', text, re.MULTILINE); print(match.group(1)) if match else sys.exit('name not found in pyproject.toml')")
# Read the version source directly so `make install_dev` works in a freshly
# created environment, before runtime dependencies such as pydantic exist.
SDK_VERSION := $(shell $(PYTHON) -c "import ast, pathlib, sys; version = next((ast.literal_eval(line.split('=', 1)[1].strip()) for line in pathlib.Path('src/oracle_vecdb/version.py').read_text().splitlines() if line.lstrip().startswith('SDK_VERSION')), None); print(version) if version is not None else sys.exit('SDK_VERSION not found in src/oracle_vecdb/version.py')")

.PHONY: all check distribute format format_check lint type_check test integration_test build install_dev clean help reports_dirs security_check generate_docs

# =============================================================================
# 2. CORE TARGETS
# ==============================================================================

all: check ## Run format_check, lint, type_check, security_check and test

check: format_check lint type_check security_check test ## Validate codebase (style, lint, types, security check test)
	@echo "VALIDATION COMPLETE: SUCCESS!"

distribute: check build  ## Full validation and then build distributions
	@echo "RELEASE PREPARATION COMPLETE: Code is validated and packages are built."

# ==============================================================================
# 3. INDIVIDUAL TARGETS
# ==============================================================================

reports_dirs: ## Create reports directories (used when REPORT=1)
ifneq ($(strip $(REPORT)),)
	@mkdir -p "$(LINT_REPORT_DIR)" "$(TYPE_CHECK_REPORT_DIR)" "$(UNIT_TEST_REPORT_DIR)" "$(INTEGRATION_TEST_REPORT_DIR)" "$(COVERAGE_REPORT_DIR)" "$(SECURITY_REPORT_DIR)"
endif

format_check: ## Verify Black formatting
	@echo "Checking code formatting with Black..."
	@$(BLACK) --check $(TARGET_DIRS)
	@echo "   -> Code style verified."

lint: reports_dirs ## Run Flake8 linting
	@echo "Running code linting with Flake8..."
	@$(FLAKE8) $(TARGET_DIRS) $(LINT_REPORT_FLAG)
	@echo "   -> Linting passed: No code quality issues found."

type_check: reports_dirs ## Run MyPy static type checks
	@echo "Running Static Type Checks with MyPy..."
	@$(MYPY) $(TARGET_DIRS) $(TYPE_CHECK_REPORT_FLAG)
	@echo "   -> Type checking successful."

security_check: reports_dirs ## Run Bandit security scan on Python files in src, tests, and examples
	@echo "Running security checks with Bandit..."
	@$(BANDIT) -r $(TARGET_DIRS) $(BANDIT_REPORT_FLAG)
	@echo "   -> Bandit analysis completed successfully."

test: reports_dirs ## Run unit tests with coverage
	@echo "Running unit tests and coverage (pytest)..."
	@set +e; \
	UNIT_TEST_JUNIT_FLAG="$(UNIT_TEST_JUNIT_FLAG)" \
	COVERAGE_XML_FLAG="$(COVERAGE_XML_FLAG)" \
	COVERAGE_HTML_FLAG="$(COVERAGE_HTML_FLAG)" \
	$(TOX); \
	TEST_STATUS=$$?; \
	set -e; \
	if [ -n "$(REPORT)" ] && [ -f "$(UNIT_TEST_REPORT_DIR)/pytest_report.xml" ]; then \
		$(PYTHON) dev-tools/junit_to_html_report.py \
			--junit-xml "$(UNIT_TEST_REPORT_DIR)/pytest_report.xml" \
			--output "$(UNIT_TEST_HTML_REPORT)" \
			--title "VecDB Python SDK Unit Test Report"; \
	fi; \
	exit $$TEST_STATUS
	@echo "   -> All tests passed."

integration_test: reports_dirs ## Run live VecDB integration tests
	@echo "Running VecDB integration tests (pytest-xdist)..."
	@if ! [[ "$(INTEGRATION_TEST_WORKERS)" =~ ^[0-9]+$$ ]] || [ "$(INTEGRATION_TEST_WORKERS)" -lt 1 ]; then \
		echo "Error: INTEGRATION_TEST_WORKERS must be a positive integer."; \
		exit 2; \
	fi
	@if [ -n "$(REPORT)" ]; then \
		rm -rf "$(INTEGRATION_TEST_REPORT_SHARDS_DIR)"; \
		mkdir -p "$(INTEGRATION_TEST_REPORT_SHARDS_DIR)"; \
		rm -f "$(INTEGRATION_TEST_REPORT_DIR)/pytest_report.xml"; \
	fi
	@set +e; \
	export RUN_INTEGRATION_TESTS=true; \
	export VECDB_REQUIRE_INTEGRATION_TEST_ENV=true; \
	export PYTHONPATH="$(abspath $(SOURCE_DIR))"; \
	export VECDB_TEST_RUN_ID="$${VECDB_TEST_RUN_ID:-$$(date +%Y%m%d%H%M%S)}"; \
	TEST_FILES=(); \
	if [ -n "$(INTEGRATION_TEST_PARALLEL_FILES)" ]; then \
		for test_file in $(INTEGRATION_TEST_PARALLEL_FILES); do \
			TEST_FILES+=("$$test_file"); \
		done; \
	else \
		while IFS= read -r test_file; do TEST_FILES+=("$$test_file"); done < <(find dev-tools/tests/integration -type f -name 'test_*.py' -print | sort); \
	fi; \
	for test_file in $(INTEGRATION_TEST_SERIAL_FILES); do \
		if [[ ! " $${TEST_FILES[*]} " =~ " $$test_file " ]]; then TEST_FILES+=("$$test_file"); fi; \
	done; \
	REPORT_ARG=(); \
	if [ -n "$(REPORT)" ]; then \
		REPORT_ARG=(--junitxml "$(INTEGRATION_TEST_REPORT_SHARDS_DIR)/integration.xml"); \
	fi; \
	TEST_STATUS=0; \
	if [ "$${#TEST_FILES[@]}" -gt 0 ] && [ "$(DEBUG)" -gt 0 ]; then \
		MASTER_PID=$$$$ $(PYTEST) \
			-rfE \
			--tb=short \
			--durations=5 \
			-vv \
			-s \
			--capture=tee-sys \
			--color=yes \
			--durations-min=1 \
			-n "$(INTEGRATION_TEST_WORKERS)" \
			--dist=$(WORKER_SCHEDULE) \
			"$${REPORT_ARG[@]}" \
			"$${TEST_FILES[@]}"; \
		TEST_STATUS=$$?; \
	else \
		MASTER_PID=$$$$ $(PYTEST) \
			-rfE \
			--tb=short \
			--durations=5 \
			--color=yes \
			--durations-min=1 \
			-n "$(INTEGRATION_TEST_WORKERS)" \
			--dist=$(WORKER_SCHEDULE) \
			"$${REPORT_ARG[@]}" \
			"$${TEST_FILES[@]}"; \
		TEST_STATUS=$$?; \
	fi; \
	set -e; \
	if [ -n "$(REPORT)" ]; then \
		$(PYTHON) dev-tools/merge_junit_reports.py \
			--input-dir "$(INTEGRATION_TEST_REPORT_SHARDS_DIR)" \
			--output "$(INTEGRATION_TEST_REPORT_DIR)/pytest_report.xml"; \
		if [ -f "$(INTEGRATION_TEST_REPORT_DIR)/pytest_report.xml" ]; then \
			$(PYTHON) dev-tools/junit_to_html_report.py \
				--junit-xml "$(INTEGRATION_TEST_REPORT_DIR)/pytest_report.xml" \
				--output "$(INTEGRATION_TEST_HTML_REPORT)" \
				--title "VecDB Python SDK Integration Test Report"; \
		fi; \
	fi; \
	exit $$TEST_STATUS
	@echo "   -> Integration tests passed."

generate_docs: ## Build SDK docs and package archive
	@echo "Building SDK documentation (Sphinx HTML)..."
	@if [ ! -f "$(DOCS_DIR)/source/conf.py" ]; then \
		echo "Error: Sphinx configuration not found at $(DOCS_DIR)/source/conf.py"; \
		exit 2; \
	fi
	@rm -rf $(DOCS_BUILD_DIR)
	@$(MAKE) -C $(DOCS_DIR) html
	@echo "Packaging HTML documentation archive..."
	@if [ ! -d "$(DOCS_BUILD_DIR)/html" ]; then \
		echo "Error: Expected HTML build directory not found: $(DOCS_BUILD_DIR)/html"; \
		exit 1; \
	fi
	@cd "$(DOCS_BUILD_DIR)/html" && zip -qr "../$(DOC_ZIP_PREFIX)-$(SDK_VERSION).zip" .
	@echo "   -> Documentation archived at $(DOCS_BUILD_DIR)/$(DOC_ZIP_PREFIX)-$(SDK_VERSION).zip"

# ==============================================================================
# 4. UTILITY TARGETS
# ==============================================================================

format: ## Auto-format code with Black
	@echo "Auto-formatting code with Black..."
	@$(BLACK) $(TARGET_DIRS)
	@echo "   -> Format completed."

build: clean ## Build sdist and wheel into dist/
	@echo "Building source and wheel distributions..."
	@$(BUILD) --sdist --wheel
	@echo "   -> Build artifacts created in dist/."

install_dev: ## Install development dependencies
	@echo "Installing/Updating development dependencies..."
	@$(PYTHON) -m pip install -U pip
	@$(PYTHON) -m pip install -e '.[dev,test,doc]'
	@echo "   -> Dependencies updated successfully."

clean: ## Remove build/test caches and reports
	@echo "Cleaning up artifacts..."
	@rm -rf .mypy_cache .pytest_cache .coverage htmlcov/ build dist __parfait__ $(REPORT_DIR) $(DOCS_BUILD_DIR)
	@find . -name "__pycache__" -exec rm -rf {} +
	@echo "   -> Cleanup complete."

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nAvailable targets:\n\n"} /^[a-zA-Z0-9_.-]+:.*##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 } /^.DEFAULT_GOAL/ {printf "\n"}' $(MAKEFILE_LIST)

PYTHON ?= python
VENV ?= .venv
VENV_PYTHON := $(VENV)/Scripts/python.exe
VENV_PIP := $(VENV)/Scripts/pip.exe

.PHONY: help venv install test demo audit ui docker-build docker-up docker-down clean seed-preview seed-create collect overlay audit-real seed-cleanup real

help:
	@echo "IAM Auditor - Windows-friendly commands"
	@echo "  make venv        Create a local virtual environment"
	@echo "  make install     Install project requirements"
	@echo "  make test        Run unit tests"
	@echo "  make demo        Run the offline demo audit"
	@echo "  make audit       Run the IAM audit with rules + LLM"
	@echo "  make ui          Start the Flask dashboard"
	@echo "  make docker-build Build Docker image"
	@echo "  make docker-up   Start Docker Compose stack"
	@echo "  make docker-down Stop Docker Compose stack"
	@echo "  make seed-preview Preview the [TEST] identities (creates nothing)"
	@echo "  make real        Create test users, collect tenant, overlay, audit"
	@echo "  make seed-cleanup Delete all [TEST] objects from the tenant"
	@echo "  make clean       Remove generated output and virtual environment"

venv:
	@if not exist "$(VENV)" $(PYTHON) -m venv $(VENV)

install: venv
	@$(VENV_PIP) install --upgrade pip
	@$(VENV_PIP) install -r requirements.txt

test: venv
	@$(VENV_PYTHON) -m pytest -q tests

demo: venv
	@$(VENV_PYTHON) src/generate_data.py
	@$(VENV_PYTHON) src/audit.py --no-llm

audit: venv
	@$(VENV_PYTHON) src/audit.py

ui: venv
	@$(VENV_PYTHON) app.py

docker-build:
	docker build -t iam-auditor:latest .

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

clean:
	@if exist "outputs" rmdir /s /q outputs
	@if exist "data\iam_inventory_real.json" del /q data\iam_inventory_real.json
	@if exist "data\hr_leavers.txt" del /q data\hr_leavers.txt
	@if exist "data\seed_state.json" del /q data\seed_state.json
	@if exist "$(VENV)" rmdir /s /q "$(VENV)"

seed-preview: venv
	@$(VENV_PYTHON) src/seed_tenant.py create --dry-run

seed-create: venv
	@$(VENV_PYTHON) src/seed_tenant.py create

collect: venv
	@$(VENV_PYTHON) src/collect_entra.py

overlay: venv
	@$(VENV_PYTHON) src/seed_tenant.py overlay

audit-real: venv
	@$(VENV_PYTHON) src/audit.py --input iam_inventory_real.json

seed-cleanup: venv
	@$(VENV_PYTHON) src/seed_tenant.py cleanup

# full pipeline: create users -> read tenant -> inject MFA/dates -> audit
real: seed-create collect overlay audit-real
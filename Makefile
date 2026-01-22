.PHONY: install install-dev run test lint format clean help

PYTHON := python3
VENV := venv
PIP := $(VENV)/bin/pip
PYTHON_VENV := $(VENV)/bin/python

help:
	@echo "Interview Assistant - Available commands:"
	@echo ""
	@echo "  make install      Install production dependencies"
	@echo "  make install-dev  Install development dependencies"
	@echo "  make run          Run the application"
	@echo "  make test         Run tests"
	@echo "  make lint         Run linters"
	@echo "  make format       Format code"
	@echo "  make clean        Clean build artifacts"
	@echo "  make deps-system  Install system dependencies (requires sudo)"
	@echo ""

# Create virtual environment
$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip

# Install production dependencies
install: $(VENV)/bin/activate
	$(PIP) install -e .

# Install development dependencies
install-dev: $(VENV)/bin/activate
	$(PIP) install -e ".[dev]"

# Run the application
run: $(VENV)/bin/activate
	$(PYTHON_VENV) -m interview_assistant

# Run tests
test: $(VENV)/bin/activate
	$(PYTHON_VENV) -m pytest tests/ -v

# Run linters
lint: $(VENV)/bin/activate
	$(PYTHON_VENV) -m ruff check interview_assistant/
	$(PYTHON_VENV) -m mypy interview_assistant/

# Format code
format: $(VENV)/bin/activate
	$(PYTHON_VENV) -m black interview_assistant/
	$(PYTHON_VENV) -m ruff check --fix interview_assistant/

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Install system dependencies (Ubuntu/Debian)
deps-system:
	sudo apt update
	sudo apt install -y \
		libgtk-4-dev \
		gir1.2-gtk-4.0 \
		libadwaita-1-dev \
		gir1.2-adw-1 \
		libgtksourceview-5-dev \
		gir1.2-gtksource-5 \
		libpulse-dev \
		pipewire \
		pipewire-pulse \
		ffmpeg \
		python3-pip \
		python3-venv

# Download Whisper model
download-model:
	$(PYTHON_VENV) -c "from faster_whisper import WhisperModel; WhisperModel('base')"

# Create distribution package
dist: $(VENV)/bin/activate
	$(PIP) install build
	$(PYTHON_VENV) -m build

# Install pre-commit hooks
pre-commit: $(VENV)/bin/activate
	$(PIP) install pre-commit
	$(PYTHON_VENV) -m pre_commit install

SHELL := /bin/bash
PYTHON := /usr/bin/python3
VENV_DIR := .venv
ACTIVATE_VENV := source $(VENV_DIR)/bin/activate

install: venv

venv: $(VENV_DIR)/bin/activate

$(VENV_DIR)/bin/activate: requirements.txt
	$(PYTHON) -m venv $(VENV_DIR)
	$(ACTIVATE_VENV) && pip install --upgrade pip && pip install -r requirements.txt
	touch $(VENV_DIR)/bin/activate

clean:
	rm -rf $(VENV_DIR)
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	rm -rf .pytest_cache
	rm -rf data/models/*

.PHONY: all venv clean test intall run
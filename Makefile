.DEFAULT_GOAL := help ## default command of "Make"

.PHONY: load-laws
load-laws: ## load-laws will load raw data of law (in json form) to graph and vectorDB
	@uv run src/cmd/load_laws/main.py

.PHONY: install-python
install-python: ## install python version of PYTHON_VERSION
	@uv python install ${PYTHON_VERSION}


.PHONY: test
test: ## run unit tests
	@uv run pytest

.PHONY: type-check
type-check: ## run mypy static type checking
	@uv run mypy src/

.PHONY: lint
lint: ## run pycodestyle and mccabe complexity check
	@uv run pycodestyle src/
	@find src/ -name "*.py" | xargs uv run python -m mccabe --min 10

.PHONY:  help
help: ## Show help message
	@echo "Usage: make <target>"
	@echo ""
	@echo "Variables:"
	@awk 'BEGIN{FS="##"} /^[A-Z_]+[ \t]*[:?]?=/ {split($$1,a,/[:?]?=/); printf "\t\033[33m%-20s\033[0m = \033[32m%-15s\033[0m%s\n", a[1], a[2], $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*?## " } /^[a-zA-Z_-]+:.*?## / {printf "\t\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)


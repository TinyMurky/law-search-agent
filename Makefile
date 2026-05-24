.DEFAULT_GOAL := help ## default command of "Make"

.PHONY: load-laws
load-laws: ## load-laws will load raw data of law (in json form) to graph and vectorDB
	@PYTHONPATH=src uv run src/cmd/load_laws/main.py

# Chunk embedding workflow:
#   build-chunks   — 安全的日常指令。DB 已滿時只做本地 ID 查詢（不呼叫 API，~30 秒）；
#                    若上次因 API 配額中斷，會從斷點接續 embed 剩餘條文。
#   rebuild-chunks — 清空 DB 後從零重新 embed 全部 47,065 筆條文（呼叫 Gemini API，~40 分鐘）。

.PHONY: build-chunks
build-chunks: ## resume / show results（DB 已滿則跳過 API；中斷後接續）
	@PYTHONPATH=src uv run src/cmd/build_chunks/main.py

.PHONY: rebuild-chunks
rebuild-chunks: ## 清空 DB 並重新 embed 全部條文（慢，消耗 API 配額）
	@PYTHONPATH=src uv run src/cmd/build_chunks/main.py --force

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


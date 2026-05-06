.PHONY: help install demo judge ui test lint verify-funding update-deployment screenshot clean

VERIFY_FUNDING_ARGS ?=
UPDATE_DEPLOYMENT_ARGS ?= --storage-tx $(STORAGE_TX) --inft-tx $(INFT_TX)

help:
	@printf "XRPFi Stream Ledger commands\n\n"
	@printf "  make install  Install local Python dependencies with uv\n"
	@printf "  make demo     Run the terminal demo flow\n"
	@printf "  make judge    Run the judge-facing demo\n"
	@printf "  make ui       Start the browser UI on http://localhost:8088\n"
	@printf "  make test     Run the test suite\n"
	@printf "  make lint     Run Ruff checks\n"
	@printf "  make verify-funding     Check 0G wallet balance (exit 1 if unfunded)\n"
	@printf "  make update-deployment  Patch deployment docs after funding (args: STORAGE_TX=0x... INFT_TX=0x...)\n"
	@printf "  make clean    Remove local cache and build artifacts\n"

install:
	uv sync --extra dev

demo:
	uv run python demo/run_demo.py

judge:
	uv run python demo/judge_demo.py

ui:
	uv run python web/server.py

test:
	uv run pytest tests/ -q

lint:
	uv run ruff check src/ tests/ demo/ web/

verify-funding:
	uv run python scripts/check_0g_balance.py $(VERIFY_FUNDING_ARGS)

update-deployment:
	uv run python scripts/update_deployment.py $(UPDATE_DEPLOYMENT_ARGS)

screenshot: ## Generate UI screenshot for docs/screenshots/ui-demo.png
	python3 scripts/capture_screenshot.py

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete

.PHONY: help install backend frontend dev test lint clean

help:
	@echo "CampusSync AI"
	@echo ""
	@echo "  make install   Install backend + frontend dependencies"
	@echo "  make dev       Run backend and frontend together"
	@echo "  make backend   Run the FastAPI backend only (port 8000)"
	@echo "  make frontend  Run the Streamlit frontend only (port 8501)"
	@echo "  make test      Run the test suite (no LLM required)"
	@echo "  make lint      Run ruff"
	@echo "  make clean     Remove caches"

install:
	cd backend && uv sync
	pip install -r frontend/requirements.txt

backend:
	cd backend && uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	streamlit run frontend/app.py --server.address 0.0.0.0 --server.port 8501

dev:
	@echo "Starting backend and frontend..."
	@$(MAKE) backend & $(MAKE) frontend; wait

test:
	cd backend && uv run pytest ../tests -v

lint:
	cd backend && uv run ruff check . ../frontend ../tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true

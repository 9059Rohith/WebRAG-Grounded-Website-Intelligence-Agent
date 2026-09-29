.PHONY: install lint typecheck security test check ingest ask serve eval bench diagram smoke docker

install:
	python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-dev.txt
	python -m pip install --no-deps -e .
lint:
	python -m ruff check .
	python -m ruff format --check .
typecheck:
	python -m mypy src/rag_agent evaluation
security:
	python -m bandit -q -r src/rag_agent
	# Embedded Chroma exposes no vulnerable server routes; rationale in SECURITY.md.
	python scripts/audit_dependencies.py
test:
	python -m pytest --cov=rag_agent --cov-report=term-missing --cov-fail-under=85
check: lint typecheck security test
ingest:
	rag ingest
ask:
	rag ask "How do I define a Python function?" --show-context
serve:
	uvicorn rag_agent.api:create_app --factory --host 127.0.0.1 --port 8000
eval:
	rag eval --questions evaluation/questions.json --out evaluation/results
bench:
	rag bench
diagram:
	rag diagram
smoke:
	rag smoke
docker:
	docker compose up --build -d

# Convenient aliases; Windows users can run the equivalent README commands.
.PHONY: setup format cov docker-build docker-run docker-smoke
API_URL ?= http://127.0.0.1:8000
setup: install
format:
	python -m ruff format .
cov: test
docker-build:
	docker compose build
docker-run:
	docker compose up -d
docker-smoke:
	python scripts/verify_live.py --url $(API_URL) --out artifacts/docker-http-smoke.json

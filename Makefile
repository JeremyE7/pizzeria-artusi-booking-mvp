.PHONY: install demo test run docker

install:
	uv venv .venv
	uv pip install --python .venv/bin/python -r requirements-dev.txt

demo:
	.venv/bin/python -m app.demo

test:
	.venv/bin/python -m pytest -q

run:
	DATABASE_URL='sqlite+aiosqlite:///./demo.db' .venv/bin/uvicorn app.main:app --reload --port 8000

docker:
	docker compose up --build

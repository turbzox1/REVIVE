.PHONY: demo seed train evaluate test backend frontend docker

demo: seed train evaluate
	python scripts/run_demo.py

generate:
	python scripts/generate_data.py --n 50000 --seed 42

seed: generate
	cd backend && python -m app.db.init_db
	python scripts/seed_database.py --reset

train:
	python ml/training/train.py

evaluate:
	python scripts/run_evaluation.py --n 2000

test:
	cd backend && python -m pytest tests -q

backend:
	cd backend && uvicorn app.main:app --port 8000 --reload

frontend:
	cd frontend && npm run dev

docker:
	docker compose up --build

up: ## Run Flask locally
	uv run flask --app confetti/app.py --debug run --port 1250

scout-log: ## Tail the scout agent debug log
	tail -f scout_debug.log

discover-log: ## Tail the discover agent debug log
	tail -f discover_debug.log

talk-stats: ## Generate talks/talk_stats.md
	uv run python -m bin.generate_talk_stats

test: ## Run tests
	uv run pytest tests/ -v

lint: ## Lint code
	uv run ruff check --fix .
	uv run black .
	uv run mypy confetti

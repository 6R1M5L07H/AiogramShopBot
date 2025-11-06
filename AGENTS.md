# Repository Guidelines

## Project Structure & Module Organization
- `run.py` wires Aiogram routers, middleware, and kicks off the dispatcher; use it for local CLI entry.
- `bot.py` exposes the FastAPI webhook, schedules background jobs in `jobs/`, and pulls shared logic from `processing/` and `services/`.
- Domain code lives in `handlers/` (user/admin flows), `services/` (business rules), `repositories/` (SQLAlchemy accessors), `models/` and `enums/` (shared types), plus `utils/` for helpers.
- Configuration and integration glue is in `config.py`, `middleware/`, and `crypto_api/`; static assets are under `data/`, i18n strings in `l10n/`, and documentation in `docs/`.
- The `tests/` tree mirrors features with `unit/` and `manual/` folders; refer to `tests/README.md` before adding new suites.

## Build, Test, and Development Commands
```bash
python -m venv .venv && source .venv/bin/activate   # Create & activate virtualenv
pip install -r requirements.txt -r requirements-dev.txt  # Install runtime + test deps
python run.py                                       # Start the bot locally (DEV runtime)
docker-compose -f docker-compose.dev.yml up -d      # Bring up Redis & bot stack for integration work
pytest tests/                                       # Run automated unit & async tests
pytest --cov=services tests/payment/unit/           # Example targeted coverage check
```

## Coding Style & Naming Conventions
- Target Python 3.12, 4-space indentation, and PEP 8 plus typing; mirror existing async patterns for handlers and services.
- Prefer descriptive module names (`services/notification.py`) and keep router objects named `<feature>_router`.
- Tests follow `test_*.py`; manual scripts use verbs (`simulate_*`, `run_*`).
- Logging messages reuse the bracketed tags seen in `bot.py` (`[Startup]`, `[Init]`) to ease tracing.
- Optional formatters (`black`, `isort`, `pylint`) are listed in `requirements-dev.txt`; run them when touching large surfaces.

## Testing Guidelines
- Primary framework is pytest with `pytest-asyncio`; write coroutine tests when interacting with Aiogram.
- Use fixtures from `tests/conftest.py` for Redis, HTTP, and database setup rather than instantiating clients manually.
- Keep automation under the relevant `*/unit/` folder; document interactive flows in `*/manual/` and update `tests/README.md`.
- Manual payment and stock tools require the bot running (`python run.py`) before executing scripts.

## Commit & Pull Request Guidelines
- Follow the conventional commit style visible in history (`feat:`, `fix:`, `refactor:`) and reference tickets with `(#NN)` when applicable.
- Squash noisy commits locally; final messages should describe behavior, not files touched.
- PRs include: purpose summary, deployment/test notes, linked issue, and screenshots or logs for user-facing changes.
- Ensure CI passes (`pytest`) before requesting review; flag configuration or migration changes explicitly.

## Configuration & Security Tips
- Store secrets in `.env`; never commit it. Required values include `TOKEN`, `ADMIN_ID_LIST`, Redis, and crypto gateway keys.
- Set `RUNTIME_ENVIRONMENT` to `DEV` for ngrok tunneling, `PROD` for external IP, and `TEST` when running isolated suites.
- Rotate webhook secrets and keep `WEBHOOK_SECRET_TOKEN` aligned across Telegram and `.env`.
- Database backups default to `./backups`; confirm access controls when enabling in production.

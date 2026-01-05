# Repository Guidelines

## Project Structure & Module Organization
- `app.py` is the Streamlit entry point; `pages/` holds the multi-page UI flows (e.g., `pages/1_Exit_Projection.py`).
- `pages/0_Collaboration_Hub.py` is the team collaboration hub (tasks/docs/calendar/comments/activity).
- `agent/` contains the conversational/autonomous agents and tool wiring; `shared/` holds cross-cutting helpers (`config.py`, `auth.py`, `logging_config.py`) plus JSON templates in `shared/resources/`.
- Collaboration data stores live in `shared/` (`team_tasks.py`, `doc_checklist.py`, `calendar_store.py`, `comments_store.py`, `activity_feed.py`, `collab_assistant.py`) and use Supabase `chat_sessions/chat_messages` with local JSON fallback.
- `scripts/` contains batch generators (`scripts/generate_exit_projection.py`, `scripts/analyze_valuation.py`); `cli.py` exposes the CLI.
- `example/` has sample spreadsheets; `chat_history/`, `feedback/`, and `temp/` are runtime outputs and should stay untracked.

## Build, Test, and Development Commands
- `./run.sh` creates a venv (if missing), installs deps, and starts Streamlit at `http://localhost:8501`.
- `python -m venv venv && source venv/bin/activate` then `pip install -r requirements.txt` for manual setup.
- `streamlit run app.py` launches the web UI.
- `python cli.py chat` for interactive mode; `python cli.py analyze <path>` for quick analysis; `python cli.py goal "..." -f <path>` for autonomous runs.
- `python scripts/generate_exit_projection.py --help` for script-driven batch runs.

## Coding Style & Naming Conventions
- Python 3.12, 4-space indentation; follow PEP 8 with `snake_case` for functions/variables and `CamelCase` for classes.
- Keep Streamlit pages named with numeric prefixes (e.g., `pages/2_Peer_PER_Analysis.py`) to preserve ordering.
- Prefer placing reusable logic in `shared/` and agent/tool logic in `agent/` rather than in UI modules.
- For the collaboration board UX, use a single embedded HTML component (`components.html`) and pass changes back via `streamlit:componentValue` to avoid heavy UI reflows.

## Collaboration Data Conventions
- Team-scoped data is keyed by `team_id` and stored in Supabase `chat_messages` with session IDs:
  - `tasks_<team_id>` (role `team_task`)
  - `docs_<team_id>` (role `team_doc`)
  - `calendar_<team_id>` (role `calendar`)
  - `comments_<team_id>` (role `team_comment`)
- Local fallback files live under `temp/` and mirror the same team IDs.

## Testing Guidelines
- No formal automated test suite is checked in.
- Use `python cli.py test` as a connectivity smoke test for the agent.
- If you add tests, place them under `tests/` with `test_*.py` and wire up pytest explicitly.

## Commit & Pull Request Guidelines
- Commit messages in history are short, imperative summaries (e.g., "Fix session load", "Add diagnosis page"); follow that pattern.
- PRs should include a clear summary, linked issue (if any), and what you ran (e.g., `python cli.py test`). Include a screenshot or brief UI description when modifying Streamlit pages.

## Configuration & Security
- Store API keys in `.env` (`ANTHROPIC_API_KEY=...`) or environment variables; never commit secrets.
- Keep real customer data out of the repo; use `example/` for sanitized sample files and rely on gitignored folders for generated outputs.

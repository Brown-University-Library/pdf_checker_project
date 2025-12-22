# Plan to make `uv run ./run_tests.py` work locally and in GitHub CI

## Findings
- The repository’s canonical instructions are in `django_template_52_project/AGENTS.md`.
- Current test invocation that succeeds: `uv run ./manage.py test` (Django’s test runner).
- Current invocation that fails: `uv run ./run_tests.py -v` with error:
  - ImportError: Start directory is not importable: 'tests'
- Why: `run_tests.py` discovers tests under a top-level `tests/` package (see `run_tests.py` lines 51-64), but this project’s tests live under the Django app path `pdf_checker_app/tests/`.
- Tests depend on Django (use `django.test.SimpleTestCase`, import `django.conf.settings`), so plain `unittest` discovery requires Django to be set up first (`DJANGO_SETTINGS_MODULE` + `django.setup()`).
- `config/settings.py` expects a `.env` file one directory ABOVE the project directory (path is `config/settings.py` → parent.parent.parent → `.env`). This matches local layout (`../.env` exists), but on GitHub CI there will be no parent `.env` by default.
- `LOG_PATH` and `DATABASES_JSON` values in `.env` refer to paths one directory ABOVE the project directory (`../logs/...`, `../DBs/...`). CI must create those directories or adjust the env file.

## Root cause of the failure
- `run_tests.py` assumes a top-level `tests/` package that does not exist in this Django template.
- Additionally, `run_tests.py` does not initialize Django before importing/collecting Django-based tests.

## Plan of changes (no code changes performed yet)

1) Update `run_tests.py` to use Django’s test runner
- Set up Django before running tests:
  - `os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')`
  - `import django; django.setup()`
- Use Django’s `get_runner(settings)` instead of raw `unittest.TestLoader().discover()` so behavior matches `manage.py test`.
- Respect the existing `-v/--verbose` flag and optional dotted targets:
  - If no targets provided, run all tests (empty app label list → all installed apps).
  - If targets provided, pass them through to `run_tests()` (e.g., `pdf_checker_app`, `pdf_checker_app.tests.test_error_check`, or a dotted test path).
- Exit with non-zero on failures as it does now.

## future work -- outside of the scope of just getting `uv run ./run_tests.py` to work

2) Update docs to reflect Django layout
- In `AGENTS.md`, adjust the “How to run” tests section to emphasize:
  - Primary: `uv run ./manage.py test`.
  - Alternate/CI: `uv run ./run_tests.py` (now implemented via Django’s runner).
  - Note that tests live under app directories like `pdf_checker_app/tests/`, not a top-level `tests/` directory.

3) GitHub CI workflow to run tests with `uv run ./run_tests.py`
- Add `.github/workflows/tests.yml` with the following high-level steps:
  - Checkout repo.
  - Setup Python 3.12 and uv (e.g., `astral-sh/setup-uv` or install via script).
  - `uv sync` to create/populate the venv from `pyproject.toml`/`uv.lock`.
  - Change working directory to `./django_template_52_project/` for commands below.
  - Provide environment and dirs expected by settings:
    - `cp ./config/dotenv_example_file.txt ../.env` (this places `.env` one level above the project directory, where `settings.py` looks for it)
    - `mkdir -p ../logs ../DBs`
    - Optionally: `touch ../logs/pdf_checker_project.log` and `touch ../DBs/pdf_checker_project.sqlite` (not strictly required for SimpleTestCase, but safe)
  - Run: `uv run ./run_tests.py -v` (or `uv run ./manage.py test` if you prefer).
- Notes:
  - If you prefer not to place `.env` above the repo root in CI, you could instead set all required environment variables inline in the workflow and modify `settings.py` in the codebase to not assert the external `.env`. The above plan avoids code changes by copying the example dotenv file to the expected location.

4) Local developer convenience (optional)
- Consider adding a `Makefile` target or `taskfile` script for:
  - `make test` → `uv run ./manage.py test`
  - `make test-ci` → runs the same steps as CI (including creating `../.env`, `../logs`, `../DBs`) then `uv run ./run_tests.py`.

## Potential gotchas to watch for during implementation
- If any tests are added that require the database, ensure migrations run or that the test runner can create the test database automatically (Django will do this for sqlite by default). The current tests use `SimpleTestCase` and do not require a DB.
- Logging: `LOG_PATH` points to `../logs/pdf_checker_project.log`. Ensure the parent directory exists in CI before Django loads logging.
- If a future test-only `.env` is desired for CI, you can check in a minimal `.env.ci` and copy it to the parent path during the workflow step.

## Summary
- The failing `run_tests.py` assumes a non-existent `tests/` directory and doesn’t initialize Django. Update it to use Django’s test runner with `django.setup()`, and adjust CI to provide the external `.env` and parent directories. This will make `uv run ./run_tests.py` behave like `uv run ./manage.py test` locally and in GitHub CI.

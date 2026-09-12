# Python — uv

The Python stack is a `uv` project rooted at `backend/`. Never install into system Python,
never hand-edit dependencies in `pyproject.toml`, never bypass `uv.lock`.

## Daily use

```bash
cd backend
uv sync                 # create/update .venv and install
uv run pytest           # run anything through uv
uv run uvicorn app.main:create_app --factory --reload
```

CI and Render consume `uv.lock` via `uv sync --frozen`, so the lock file is authoritative
and must be committed with any dependency change.

## Adding or removing dependencies

```bash
uv add <pkg>
uv remove <pkg>
```

These update `pyproject.toml` and `uv.lock` together. Editing `pyproject.toml` by hand
desynchronises them and CI fails on `uv lock --check`.

## Python version

3.12, pinned in `requires-python`. Match it in CI and in the Render blueprint.

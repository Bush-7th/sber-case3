FROM python:3.13.5-slim-bookworm@sha256:4c2cf9917bd1cbacc5e9b07320025bdb7cdf2df7b0ceaccb55e9dd7e30987419 AS build

WORKDIR /opt/app
ENV UV_PROJECT_ENVIRONMENT=/opt/app/.venv UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
RUN python -m pip install --no-cache-dir uv==0.11.26
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13.5-slim-bookworm@sha256:4c2cf9917bd1cbacc5e9b07320025bdb7cdf2df7b0ceaccb55e9dd7e30987419
WORKDIR /opt/app
ENV PATH="/opt/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /opt/app/.venv ./.venv
# Keep migration path resolution independent of an editable source install.
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
ENV PYTHONPATH=/opt/app/src
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

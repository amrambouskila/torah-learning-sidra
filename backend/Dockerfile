FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
COPY data ./data
RUN uv sync --frozen --no-dev

EXPOSE 8285
# Root on purpose, and narrowly: this container is bound to localhost, has no auth surface, and
# writes ./backend/data through a bind mount whose files belong to the host user. A non-root UID
# inside the container cannot write that directory, which would break the ledger export and the
# correction safety copy -- the two things the mount exists for.
CMD ["uv", "run", "sidra-api"]

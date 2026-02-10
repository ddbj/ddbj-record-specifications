FROM python:3.12-bookworm

LABEL org.opencontainers.image.authors="Bioinformatics and DDBJ Center"
LABEL org.opencontainers.image.url="https://github.com/ddbj/ddbj-record-specifications"
LABEL org.opencontainers.image.source="https://github.com/ddbj/ddbj-record-specifications/blob/main/Dockerfile"
LABEL org.opencontainers.image.version="0.1.5"
LABEL org.opencontainers.image.description="The ddbj-record package provides tools for parsing, validating, and converting DDBJ record specifications."
LABEL org.opencontainers.image.licenses="Apache-2.0"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY . .
RUN uv sync --extra tests

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT [""]
CMD ["sleep", "infinity"]

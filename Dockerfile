FROM python:3.12.10-bookworm

LABEL org.opencontainers.image.authors="Bioinformatics and DDBJ Center"
LABEL org.opencontainers.image.url="https://github.com/ddbj/ddbj-record-specifications"
LABEL org.opencontainers.image.source="https://github.com/ddbj/ddbj-record-specifications/blob/main/Dockerfile"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.description="The ddbj-record package provides tools for parsing, validating, and converting DDBJ record specifications."
LABEL org.opencontainers.image.licenses="Apache2.0"

WORKDIR /app
COPY . .
RUN python3 -m pip install --no-cache-dir --progress-bar off -U pip && \
    python3 -m pip install --no-cache-dir --progress-bar off -e .[tests]

CMD ["sleep", "infinity"]

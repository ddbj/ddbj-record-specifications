FROM ghcr.io/astral-sh/uv:0.12.19-python3.12-trixie

# The venv lives outside the bind-mounted /app, so the host never gets a .venv directory.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked && \
    chmod -R a+rwX /opt/venv

# compose runs the container as the host user, which has no home directory in the image.
ENV HOME=/home/app
RUN mkdir -p /home/app && chmod 777 /home/app

CMD ["sleep", "infinity"]

FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

# The venv lives outside the bind-mounted /app, so the host never gets a .venv directory.
# uv uses the Python of the base image. If .python-version does not match it, uv fails instead of downloading another Python.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"

# uv installs every package, so the system Python does not need pip.
# The base image adds the pip symlink outside the pip package, so uv does not remove it.
RUN uv pip uninstall --system pip && \
    rm /usr/local/bin/pip

WORKDIR /app
COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked && \
    chmod -R a+rwX /opt/venv

# compose runs the container as the host user, which has no home directory in the image.
ENV HOME=/home/app
RUN mkdir -p /home/app && chmod 777 /home/app

CMD ["sleep", "infinity"]

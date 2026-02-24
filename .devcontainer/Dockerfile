FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    ca-certificates \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash vscode && \
    mkdir -p /workspace && \
    chown -R vscode:vscode /workspace

USER vscode
WORKDIR /home/vscode

# Install uv and Bun for vscode user
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN curl -fsSL https://bun.sh/install | bash

ENV PATH="/home/vscode/.bun/bin:/home/vscode/.local/bin:/home/vscode/.cargo/bin:$PATH"

WORKDIR /workspace
CMD ["/bin/bash"]

FROM python:3.10.12-slim

# Systemabhängige Tools und Konfigurationsschritte
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis setzen
WORKDIR /workspace

# Upgrade pip
RUN pip install --upgrade pip
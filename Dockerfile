FROM python:3.12-slim

RUN useradd -u 1000 -m agent

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

USER agent

CMD ["sleep", "infinity"]

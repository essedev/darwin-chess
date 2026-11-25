# Trusted reference engines: the random player (first anchor, python-chess), Stockfish at
# limited strength (absolute Elo), and the base the referee tests build faulty engines on.
FROM python:3.13-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends stockfish \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.10.2 /uv /usr/local/bin/uv
RUN uv pip install --system --no-cache chess==1.11.2
COPY random_engine.py /anchors/random_engine.py
ENV PYTHONPATH=/anchors PYTHONUNBUFFERED=1
CMD ["python3", "/anchors/random_engine.py"]

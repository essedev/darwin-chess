# Sandbox where the agent works and where every engine binary runs.
# Untrusted by design: started with no network and only genome/ mounted.
FROM rust:1.99-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git python3 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 agent
USER agent
WORKDIR /genome

# The agent has no network at runtime: crates must be vendored or absent.
ENV CARGO_NET_OFFLINE=true

CMD ["sleep", "infinity"]
